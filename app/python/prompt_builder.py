"""
Prompt Builder module that uses AI to create and update channel-specific prompts.
This module analyzes training data (historical trade signals) and generates
optimized prompts that help the execution model understand channel-specific signal formats.

New conversational approach: AI analyzes signals, asks clarifying questions,
and generates optimal prompts based on the conversation.
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from openai import OpenAI
import json
import uuid
import re


class PromptBuilder:
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """
        Initialize the PromptBuilder with OpenAI API credentials.

        Args:
            api_key: OpenAI API key
            model: Model to use for prompt building (separate from execution model)
        """
        self.api_key = api_key
        self.model = model
        self._client = None  # Lazy initialization - create client only when needed
    
    def _get_client(self):
        """
        Get OpenAI client, creating it lazily if needed.
        This avoids initialization errors during config save.
        """
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key is required")
            # httpx==0.25.2 is pinned in build.gradle for compatibility
            self._client = OpenAI(api_key=self.api_key)
        return self._client
    
    def _requires_default_temperature(self) -> bool:
        """
        Check if the model only supports default temperature (1).
        Models like o1, o3 series only support temperature=1.
        
        Returns:
            True if model requires default temperature, False otherwise
        """
        model_lower = self.model.lower()
        return 'o1' in model_lower or 'o3' in model_lower
    
    def _create_with_token_param(self, token_count: int, temperature: float = 1.0, **kwargs):
        """
        Create a chat completion without token limit parameters.
        Removed max_tokens and max_completion_tokens to avoid parameter compatibility issues.
        Uses model default token limits instead.
        
        Args:
            token_count: Ignored (kept for backward compatibility, but not used)
            temperature: Temperature value (defaults to 1.0 for all models)
            **kwargs: Other parameters for chat.completions.create
            
        Returns:
            Response from OpenAI API
        """
        # Build request parameters without token limits
        request_params = {**kwargs}
        
        # Use temperature 1.0 (default) for all models - works with all model types
        request_params["temperature"] = temperature
        
        # Removed max_tokens and max_completion_tokens - using model defaults
        # This avoids parameter compatibility issues between different models and library versions
        
        try:
            return self._get_client().chat.completions.create(**request_params)
        except Exception as e:
            # Handle temperature errors if needed
            error_str = str(e).lower()
            if 'temperature' in error_str and ('not supported' in error_str or 'unsupported value' in error_str):
                # Remove temperature and retry (will use default 1.0)
                request_params.pop("temperature", None)
                try:
                    return self._get_client().chat.completions.create(**request_params)
                except Exception as retry_error:
                    raise ValueError(f"API call failed even after removing temperature. Error: {str(retry_error)}") from retry_error
            else:
                # Re-raise with error details
                raise ValueError(f"API call failed: {str(e)}") from e
    
    def calculate_weights(self, training_data: List[Dict]) -> List[Dict]:
        """
        Calculate weights for training data based on recency.
        More recent signals get higher weights.
        
        Args:
            training_data: List of training signals with dates
            
        Returns:
            Training data with calculated weights
        """
        # Separate signals with dates from those without
        dated_signals = [s for s in training_data if s.get('date')]
        undated_signals = [s for s in training_data if not s.get('date')]
        
        # Sort dated signals by date (most recent first)
        if dated_signals:
            dated_signals.sort(key=lambda x: x['date'], reverse=True)
            
            # Assign weights: most recent = 1.0, exponentially decreasing
            for i, signal in enumerate(dated_signals):
                # Weight formula: starts at 1.0 and decays exponentially
                signal['weight'] = max(0.3, 1.0 * (0.85 ** i))
        
        # Undated signals get equal moderate weight
        for signal in undated_signals:
            signal['weight'] = 0.6
        
        return dated_signals + undated_signals
    
    def build_prompt(self, channel_name: str, training_data: List[Dict]) -> str:
        """
        Build a new channel-specific prompt using AI analysis of training data.
        
        Args:
            channel_name: Name of the channel
            training_data: List of training signals with format:
                          [{"signal": "...", "date": "2025-12-01"}, ...]
        
        Returns:
            Generated channel prompt string
        """
        # Calculate weights based on recency
        weighted_data = self.calculate_weights(training_data)
        
        # Prepare training examples for the prompt
        training_examples = ""
        for i, item in enumerate(weighted_data):
            weight_indicator = "🔥" if item['weight'] > 0.8 else "⭐" if item['weight'] > 0.5 else "•"
            date_info = f" (Date: {item.get('date', 'N/A')})" if item.get('date') else ""
            training_examples += f"{weight_indicator} Example {i+1}{date_info} [Weight: {item['weight']:.2f}]:\n{item['signal']}\n\n"
        
        # System prompt for the builder model
        system_prompt = """You are an expert at analyzing trade signal patterns and creating 
precise prompts that help AI models understand and parse trade signals.

Your task is to analyze the provided trade signal examples from a specific channel and create 
a comprehensive prompt that:
1. Identifies the signal format and structure
2. Explains what each component means (action, symbol, price, stop loss, take profit, etc.)
3. Handles variations and edge cases in the format
4. Provides clear instructions for parsing into a structured format

The prompt you create will be used by another AI model to parse incoming signals from this 
channel and convert them to Webull API calls.

Focus on:
- Signal format patterns
- How to identify: action (BUY/SELL), symbol, entry price, stop loss, take profit
- Common abbreviations or variations
- Position sizing if mentioned
- Time frames if specified

Output ONLY the prompt text that will be used by the execution model. Do NOT include 
explanations, notes, or meta-commentary."""
        
        # User prompt with training data
        user_prompt = f"""Channel Name: {channel_name}

Training Data (signals are weighted by recency - more recent signals are more important):

{training_examples}

Create a comprehensive prompt that will help an AI model understand and parse signals from 
this channel. The output should be in JSON format with fields: symbol, action (BUY/SELL), 
entry_price, stop_loss, take_profit, quantity (if specified), notes (for additional context).

Generate the channel-specific parsing prompt now:"""
        
        try:
            # Call the builder model to generate the prompt
            response = self._create_with_token_param(
                10000,
                temperature=1.0,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            generated_prompt = response.choices[0].message.content.strip()
            
            # Add metadata to the prompt
            metadata = f"""[Channel: {channel_name}]
[Generated: {datetime.now().isoformat()}]
[Training Samples: {len(training_data)}]

"""
            
            return metadata + generated_prompt
            
        except Exception as e:
            raise Exception(f"Error generating prompt: {str(e)}")
    
    def update_prompt(self, channel_name: str, existing_prompt: str, 
                     new_training_data: List[Dict]) -> str:
        """
        Update an existing channel prompt with new training data.
        
        Args:
            channel_name: Name of the channel
            existing_prompt: Current channel prompt
            new_training_data: New training signals to incorporate
        
        Returns:
            Updated channel prompt string
        """
        # Calculate weights for new data
        weighted_data = self.calculate_weights(new_training_data)
        
        # Prepare new examples
        new_examples = ""
        for i, item in enumerate(weighted_data):
            weight_indicator = "🔥" if item['weight'] > 0.8 else "⭐" if item['weight'] > 0.5 else "•"
            date_info = f" (Date: {item.get('date', 'N/A')})" if item.get('date') else ""
            new_examples += f"{weight_indicator} New Example {i+1}{date_info} [Weight: {item['weight']:.2f}]:\n{item['signal']}\n\n"
        
        # System prompt for updating - APPEND new data, don't replace
        system_prompt = """You are an expert at analyzing trade signal patterns and extending 
existing prompts to handle new signal formats or variations.

Your task is to EXTEND an existing channel prompt by ADDING new information about new trade signal examples. 
The extended prompt should:
1. KEEP ALL of the existing prompt content intact
2. ADD new sections or append to existing sections to cover new patterns or variations
3. Clearly mark new additions (e.g., "ADDITIONAL PATTERNS:", "NEW FORMATS:", etc.)
4. Ensure the model can understand BOTH old and new signal formats
5. Maintain clarity and precision

CRITICAL: Do NOT remove or replace any existing content. Only ADD new information to handle the new patterns.

Output the COMPLETE prompt (existing + new additions). Do NOT include explanations or meta-commentary."""
        
        # User prompt with existing prompt and new data
        user_prompt = f"""Channel Name: {channel_name}

EXISTING PROMPT (DO NOT REMOVE OR REPLACE THIS):
{existing_prompt}

NEW TRAINING DATA (weighted by recency):
{new_examples}

EXTEND the existing prompt by ADDING new sections or information to handle these new examples. 
The final prompt should contain:
1. ALL of the existing prompt content (unchanged)
2. NEW sections or additions that explain how to parse the new signal formats
3. Clear instructions that the model should handle BOTH old and new formats

Generate the EXTENDED channel-specific parsing prompt now (existing content + new additions):"""
        
        try:
            # Call the builder model to update the prompt
            response = self._create_with_token_param(
                10000,
                temperature=1.0,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            updated_prompt = response.choices[0].message.content.strip()
            
            # Add metadata to the prompt
            metadata = f"""[Channel: {channel_name}]
[Updated: {datetime.now().isoformat()}]
[New Training Samples: {len(new_training_data)}]

"""
            
            return metadata + updated_prompt
            
        except Exception as e:
            raise Exception(f"Error updating prompt: {str(e)}")
    
    def validate_prompt(self, prompt: str, test_signal: str) -> Dict:
        """
        Validate a prompt by testing it with a sample signal.
        
        Args:
            prompt: The channel prompt to validate
            test_signal: A test signal to parse
        
        Returns:
            Dictionary with validation results
        """
        try:
            response = self._create_with_token_param(
                10000,
                temperature=1.0,
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Parse this signal:\n{test_signal}"}
                ]
            )
            
            result = response.choices[0].message.content
            
            return {
                "success": True,
                "parsed_output": result,
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "parsed_output": None,
                "error": str(e)
            }
    
    def start_conversation(self, channel_name: str, signals_dump: str, 
                          existing_prompt: Optional[str] = None, 
                          is_update: bool = False) -> Dict:
        """
        Start a conversational prompt building session by analyzing signals.
        
        Args:
            channel_name: Name of the channel
            signals_dump: Raw dump of all signals
            existing_prompt: Existing prompt if updating
            is_update: Whether this is an update or new creation
        
        Returns:
            Dictionary with AI analysis and questions
        """
        conversation_id = str(uuid.uuid4())
        
        # System prompt for the conversational builder
        system_prompt = """You are an expert AI assistant specializing in analyzing trade signal patterns for automated trading systems. 
Your goal is to deeply understand the signal format to generate a highly robust execution prompt.

YOUR ANALYSIS PROCESS:
1. **Initial Pattern Recognition:**
   - Identify if signals are for STOCKS, OPTIONS, or BOTH
   - Recognize action indicators (BUY/SELL/LONG/SHORT/CALL/PUT)
   - Map out the signal structure and component ordering
   - Identify consistent vs variable elements

2. **Deep Component Analysis:**
   - **Symbol Format:** How are tickers presented? Any prefixes/suffixes?
   - **Action Type:** What words indicate buy/sell? Any synonyms used?
   - **Price Components:** How are entry, stop loss, and take profit indicated?
     * Look for abbreviations (SL, TP, Entry, Tgt, Stop, etc.)
     * Check for implicit vs explicit price labels
   - **Options Signals (if applicable):**
     * Strike price format and location
     * Option type indicators (C/CALL, P/PUT)
     * Expiration date format (MM/DD/YY, YYYY-MM-DD, Dec 20, etc.)
     * Premium/purchase price indicators
   - **Position Size:** How is size indicated? (lots, shares, contracts, number)
   - **Fraction (Partial Position Closing):** How does this channel indicate position fraction or partial positions?
     * Look for phrases like: "sell half", "50%", "partial close", "trim 25%", "close 1/3"
     * Fraction represents the percentage of position to trade (0.0-1.0, e.g., 0.5 = 50%)
     * Typically used when SELLING an already bought position
     * If not specified or for full positions, fraction should be null
   - **Time Elements:** Expiration dates, entry timing, duration holds
   - **Confidence/Risk Levels:** Any indicators of signal strength or risk rating?

3. **Edge Case & Ambiguity Detection:**
   - What happens if some fields are missing? (e.g., no stop loss mentioned)
   - Are there signals with partial information?
   - How to handle ranges vs single values? (e.g., "240-250")
   - What about multi-leg or spread strategies?
   - How to distinguish between similar abbreviations? (e.g., "C" = call or close?)
   - Any special notation for urgent vs casual signals?
   - How are updates or cancellations indicated?

4. **Contextual Rules:**
   - Do emojis or special characters carry meaning?
   - Is there implicit information based on context? (e.g., all signals default to day orders)
   - Are there channel-specific conventions or jargon?
   - Any prefix/suffix patterns that modify meaning?

5. **Question Strategy:**
   - Ask SPECIFIC questions about ambiguities found
   - Request examples for unclear patterns
   - Clarify abbreviation meanings
   - Confirm implicit assumptions
   - Ask about rare/edge case scenarios

WHEN TO ASK QUESTIONS:
- If multiple interpretations are possible for any component
- If abbreviations could have different meanings
- If date/time formats are ambiguous
- If there's inconsistency in the pattern
- If options-specific fields are unclear or missing
- If price format could be confused (decimal vs strike, etc.)
- If fraction/partial position indicators are present, ask how to determine the fraction value
- If position sizing uses percentages or fractions, clarify how to interpret them

WHEN YOU'RE READY TO BUILD:
- All patterns are clear and unambiguous
- Edge cases and variations are understood
- You have explicit rules for handling missing/partial data
- You know how to distinguish between similar-looking elements

Be thorough and systematic. Ask intelligent, specific questions. The execution prompt you'll eventually create must be bulletproof.

CRITICAL FORMATTING REQUIREMENT FOR ANALYSIS:
Your "analysis" field must be WELL-FORMATTED with:
- Clear section headings using markdown-style headers (##, ###)
- Proper line breaks between sections
- Bullet points or numbered lists for clarity
- Organized subsections for each component type
- Adequate spacing for readability
- Use consistent formatting throughout

Structure your analysis like this:
## Overall Pattern Summary
[Brief overview of signal type and structure]

## Component Analysis
### Symbol Format
[Details about ticker format]

### Action Type
[Details about buy/sell indicators]

### Price Components
[Details about entry, stop loss, take profit]

### Options-Specific Fields (if applicable)
[Details about strike, option type, expiration, premium]

### Quantity/Position Size
[Details about sizing indicators]

### Time Elements
[Details about dates, timing, duration]

## Edge Cases & Ambiguities
[Documented edge cases and potential issues]

## Contextual Rules
[Channel-specific conventions and implicit rules]

Respond in a JSON format:
{
    "analysis": "Your well-formatted, structured analysis with clear headings and proper spacing",
    "questions": ["Specific question 1?", "Specific question 2?"],  // Empty if no questions needed
    "ready_to_build": true/false,
    "observations": ["Key observation 1", "Key observation 2", "Identified edge case 1", etc.]
}"""
        
        # User prompt with context
        if is_update:
            user_prompt = f"""I need to EXTEND the existing prompt for channel: {channel_name} by ADDING new information.

EXISTING PROMPT (DO NOT REMOVE OR REPLACE - KEEP ALL OF THIS):
{existing_prompt}

NEW SIGNALS DUMP:
{signals_dump}

Please analyze these new signals and determine:
1. Are there new patterns or formats not covered by the existing prompt?
2. What NEW information needs to be ADDED to handle these new patterns?
3. How can we EXTEND the prompt to handle BOTH old and new formats?

IMPORTANT: The goal is to ADD new sections or information to the existing prompt, NOT to replace it.
The final prompt should contain ALL existing content PLUS new additions for the new patterns.

Provide your analysis and ask any clarifying questions."""
        else:
            user_prompt = f"""I need to CREATE a new prompt for channel: {channel_name}

SIGNALS DUMP:
{signals_dump}

Please analyze these signals thoroughly and determine:
1. What are the patterns and formats used?
2. Do you need any clarifications about the format?
3. Are there ambiguities that need clarification?

Provide your analysis and ask any clarifying questions."""
        
        try:
            # Try with JSON format first
            try:
                # Increased token limit to 10000 for all models
                token_limit = 10000
                
                response = self._create_with_token_param(
                    token_limit,
                    temperature=1.0,
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                # Check finish_reason first
                finish_reason = None
                if hasattr(response, 'choices') and response.choices:
                    finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
                    if finish_reason == 'length':
                        # Get usage info if available
                        usage_info = {}
                        if hasattr(response, 'usage'):
                            usage_info = {
                                "completion_tokens": getattr(response.usage, 'completion_tokens', None),
                                "prompt_tokens": getattr(response.usage, 'prompt_tokens', None),
                                "total_tokens": getattr(response.usage, 'total_tokens', None)
                            }
                        error_details = {
                            "error": f"Response was truncated due to token limit ({token_limit})",
                            "finish_reason": finish_reason,
                            "usage": usage_info,
                            "model": self.model,
                            "suggestion": "The model needs more tokens to complete the response. Consider increasing max_completion_tokens or simplifying the request."
                        }
                        raise ValueError(f"Response was truncated due to token limit ({token_limit}). Debug info: {json.dumps(error_details, indent=2)}")
                
                # Detailed response logging
                response_debug = {
                    "model": self.model,
                    "has_choices": hasattr(response, 'choices') and response.choices is not None,
                    "choices_count": len(response.choices) if hasattr(response, 'choices') and response.choices else 0,
                    "response_type": type(response).__name__,
                    "finish_reason": finish_reason,
                    "response_str": str(response)[:500] if response else "None"
                }
                
                # Validate response structure
                if not hasattr(response, 'choices') or not response.choices:
                    error_details = {
                        "error": "Response has no choices",
                        "response_debug": response_debug,
                        "full_response": str(response)
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                if len(response.choices) == 0:
                    error_details = {
                        "error": "Response choices array is empty",
                        "response_debug": response_debug,
                        "full_response": str(response)
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                # Validate response content before parsing
                response_content = response.choices[0].message.content if hasattr(response.choices[0].message, 'content') else None
                
                if not response_content or not response_content.strip():
                    # Check if it's due to length truncation
                    if finish_reason == 'length':
                        error_details = {
                            "error": "Response content is empty due to token limit truncation",
                            "finish_reason": finish_reason,
                            "response_debug": response_debug,
                            "response_content": response_content,
                            "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Response was truncated and content is empty. The model used all {token_limit} tokens. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    error_details = {
                        "error": "Response content is empty or None",
                        "finish_reason": finish_reason,
                        "response_debug": response_debug,
                        "response_content": response_content,
                        "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                        "full_response": str(response)[:1000]
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                result = json.loads(response_content)
            except (ValueError, json.JSONDecodeError) as e:
                # If JSON format fails, try without it and parse manually
                try:
                    # Use same increased token limit
                    token_limit = 10000
                    
                    response = self._create_with_token_param(
                        token_limit,
                        temperature=1.0,
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    )
                    
                    # Check finish_reason for fallback attempt
                    finish_reason = None
                    if hasattr(response, 'choices') and response.choices:
                        finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
                        if finish_reason == 'length':
                            usage_info = {}
                            if hasattr(response, 'usage'):
                                usage_info = {
                                    "completion_tokens": getattr(response.usage, 'completion_tokens', None),
                                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', None),
                                    "total_tokens": getattr(response.usage, 'total_tokens', None)
                                }
                            error_details = {
                                "error": f"Fallback attempt - response truncated due to token limit ({token_limit})",
                                "finish_reason": finish_reason,
                                "usage": usage_info,
                                "original_error": str(e),
                                "model": self.model
                            }
                            raise ValueError(f"Response was truncated in fallback attempt. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    # Detailed response logging for fallback
                    response_debug = {
                        "model": self.model,
                        "has_choices": hasattr(response, 'choices') and response.choices is not None,
                        "choices_count": len(response.choices) if hasattr(response, 'choices') and response.choices else 0,
                        "response_type": type(response).__name__,
                        "finish_reason": finish_reason,
                        "fallback_attempt": True
                    }
                    
                    if not hasattr(response, 'choices') or not response.choices or len(response.choices) == 0:
                        error_details = {
                            "error": "Fallback attempt also failed - no choices in response",
                            "original_error": str(e),
                            "response_debug": response_debug,
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Empty response received from AI model after fallback. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    response_content = response.choices[0].message.content if hasattr(response.choices[0].message, 'content') else None
                    
                    if not response_content or not response_content.strip():
                        if finish_reason == 'length':
                            error_details = {
                                "error": "Fallback attempt - response content empty due to token limit truncation",
                                "finish_reason": finish_reason,
                                "original_error": str(e),
                                "response_debug": response_debug,
                                "response_content": response_content,
                                "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                                "full_response": str(response)[:1000]
                            }
                            raise ValueError(f"Response was truncated in fallback attempt and content is empty. Debug info: {json.dumps(error_details, indent=2)}")
                        
                        error_details = {
                            "error": "Fallback attempt - response content is empty",
                            "finish_reason": finish_reason,
                            "original_error": str(e),
                            "response_debug": response_debug,
                            "response_content": response_content,
                            "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Empty response received from AI model. The model may not support JSON format or the request timed out. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    # Try to extract JSON from the response (might be wrapped in markdown)
                    content_to_parse = response_content.strip()
                    if content_to_parse.startswith("```"):
                        # Remove markdown code blocks
                        parts = content_to_parse.split("```")
                        if len(parts) > 1:
                            json_part = parts[1]
                            if json_part.startswith("json"):
                                json_part = json_part[4:]
                            content_to_parse = json_part.strip()
                    
                    try:
                        result = json.loads(content_to_parse)
                    except json.JSONDecodeError as je:
                        error_details = {
                            "error": "Failed to parse JSON response",
                            "json_error": str(je),
                            "original_error": str(e),
                            "response_content": response_content[:1000],
                            "content_to_parse": content_to_parse[:1000],
                            "response_debug": response_debug
                        }
                        error_msg = f"Failed to parse JSON response: {str(je)}\nDebug info: {json.dumps(error_details, indent=2)}"
                        raise ValueError(error_msg)
                except Exception as fallback_error:
                    # If fallback also fails, include both errors
                    error_details = {
                        "error": "Both primary and fallback attempts failed",
                        "primary_error": str(e),
                        "fallback_error": str(fallback_error),
                        "model": self.model,
                        "response_debug": response_debug if 'response_debug' in locals() else "Not available"
                    }
                    raise ValueError(f"Failed to get valid response from AI model. Debug info: {json.dumps(error_details, indent=2)}")
            
            # Build conversation context
            context = {
                "channel_name": channel_name,
                "signals_dump": signals_dump,
                "existing_prompt": existing_prompt,
                "is_update": is_update,
                "conversation_history": [
                    {"role": "user", "content": signals_dump},
                    {"role": "assistant", "content": json.dumps(result)}
                ],
                "analysis": result.get("analysis", ""),
                "observations": result.get("observations", [])
            }
            
            questions = result.get("questions", [])
            ready_to_build = result.get("ready_to_build", False)
            
            # Format response for user
            response_text = f"**Analysis:**\n{result.get('analysis', '')}\n\n"
            
            if result.get("observations"):
                response_text += "**Key Observations:**\n"
                for obs in result["observations"]:
                    response_text += f"• {obs}\n"
                response_text += "\n"
            
            if questions and not ready_to_build:
                response_text += "**I need some clarifications:**\n"
                for i, q in enumerate(questions, 1):
                    response_text += f"{i}. {q}\n"
            elif ready_to_build:
                response_text += "✅ **I have enough information to build the prompt!**\n\nClick 'Generate Prompt' to proceed."
            
            # Store the builder prompts for transparency
            context["builder_system_prompt"] = system_prompt
            context["builder_user_prompt"] = user_prompt
            
            return {
                "success": True,
                "response": response_text,
                "has_questions": len(questions) > 0 and not ready_to_build,
                "ready_to_build": ready_to_build,
                "conversation_id": conversation_id,
                "context": context
            }
            
        except Exception as e:
            # Include full error details in the response
            error_message = str(e)
            error_details = {
                "error": error_message,
                "error_type": type(e).__name__,
                "model": self.model,
                "conversation_id": conversation_id
            }
            
            # Try to extract JSON from error message if it contains debug info
            if "Debug info:" in error_message:
                try:
                    debug_start = error_message.find("Debug info:")
                    debug_json = error_message[debug_start + len("Debug info:"):].strip()
                    error_details["debug_info"] = json.loads(debug_json)
                except:
                    error_details["raw_error_message"] = error_message
            
            return {
                "success": False,
                "error": f"Error analyzing signals: {error_message}",
                "error_details": error_details,
                "response": f"❌ Error: {error_message}",
                "has_questions": False,
                "ready_to_build": False,
                "conversation_id": conversation_id,
                "context": {}
            }
    
    def continue_conversation(self, conversation_id: str, user_response: str, 
                             context: Dict) -> Dict:
        """
        Continue the conversational prompt building with user's response.
        
        Args:
            conversation_id: Unique conversation identifier
            user_response: User's answer to questions
            context: Conversation context from previous interaction
        
        Returns:
            Dictionary with AI response and updated context
        """
        conversation_history = context.get("conversation_history", [])
        
        # Add user's response to history
        conversation_history.append({"role": "user", "content": user_response})
        
        system_prompt = """You are continuing to analyze trade signals to build a robust parsing prompt for automated trading.

The user has provided answers to your previous questions. Based on their clarifications:

1. **Acknowledge & Integrate:**
   - Thank the user for their clarification
   - Summarize what you now understand
   - Update your mental model of the signal pattern

2. **Deep Follow-up Analysis:**
   - If their answer revealed new edge cases, explore them
   - If still ambiguous, ask more specific follow-up questions
   - Probe for implicit rules or conventions you might have missed
   - Verify your understanding with specific examples if needed

3. **Readiness Assessment:**
   - You're ready to build when:
     * All ambiguities are resolved
     * Edge cases are understood
     * You have clear rules for every component extraction
     * Date/price/abbreviation handling is crystal clear
     * You know how to handle missing/partial data
   - You need more info if:
     * Multiple interpretations still possible
     * Critical edge cases undefined
     * Abbreviations or patterns could be confused

4. **Build Comprehensive Understanding:**
   - For each answer, consider: "Could this be misinterpreted?"
   - Think about: "What if this field is missing?"
   - Ask yourself: "Are there similar-looking patterns that need disambiguation?"

Remember: The execution prompt you'll create must be bulletproof. When in doubt, ask one more clarifying question.

Respond in JSON format:
{
    "acknowledgment": "Thank the user and summarize their clarification with your updated understanding",
    "questions": ["Specific follow-up question 1?", "Specific follow-up question 2?"],  // Empty if no more questions needed
    "ready_to_build": true/false,
    "updated_observations": ["New insight 1", "New edge case identified", "Clarified rule", etc.]
}"""
        
        try:
            # Build message history for context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Try with JSON format first
            try:
                # Increased token limit to 10000 for all models
                token_limit = 10000
                
                response = self._create_with_token_param(
                    token_limit,
                    temperature=1.0,
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                
                # Check finish_reason first
                finish_reason = None
                if hasattr(response, 'choices') and response.choices:
                    finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
                    if finish_reason == 'length':
                        # Get usage info if available
                        usage_info = {}
                        if hasattr(response, 'usage'):
                            usage_info = {
                                "completion_tokens": getattr(response.usage, 'completion_tokens', None),
                                "prompt_tokens": getattr(response.usage, 'prompt_tokens', None),
                                "total_tokens": getattr(response.usage, 'total_tokens', None)
                            }
                        error_details = {
                            "error": f"Response was truncated due to token limit ({token_limit})",
                            "finish_reason": finish_reason,
                            "usage": usage_info,
                            "model": self.model,
                            "suggestion": "The model needs more tokens to complete the response. Consider increasing max_completion_tokens or simplifying the request."
                        }
                        raise ValueError(f"Response was truncated due to token limit ({token_limit}). Debug info: {json.dumps(error_details, indent=2)}")
                
                # Detailed response logging
                response_debug = {
                    "model": self.model,
                    "has_choices": hasattr(response, 'choices') and response.choices is not None,
                    "choices_count": len(response.choices) if hasattr(response, 'choices') and response.choices else 0,
                    "response_type": type(response).__name__,
                    "finish_reason": finish_reason,
                    "response_str": str(response)[:500] if response else "None"
                }
                
                # Validate response structure
                if not hasattr(response, 'choices') or not response.choices:
                    error_details = {
                        "error": "Response has no choices",
                        "response_debug": response_debug,
                        "full_response": str(response)
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                if len(response.choices) == 0:
                    error_details = {
                        "error": "Response choices array is empty",
                        "response_debug": response_debug,
                        "full_response": str(response)
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                # Validate response content before parsing
                response_content = response.choices[0].message.content if hasattr(response.choices[0].message, 'content') else None
                
                if not response_content or not response_content.strip():
                    # Check if it's due to length truncation
                    if finish_reason == 'length':
                        error_details = {
                            "error": "Response content is empty due to token limit truncation",
                            "finish_reason": finish_reason,
                            "response_debug": response_debug,
                            "response_content": response_content,
                            "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Response was truncated and content is empty. The model used all {token_limit} tokens. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    error_details = {
                        "error": "Response content is empty or None",
                        "finish_reason": finish_reason,
                        "response_debug": response_debug,
                        "response_content": response_content,
                        "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                        "full_response": str(response)[:1000]
                    }
                    raise ValueError(f"Empty response received from AI model. Debug info: {json.dumps(error_details, indent=2)}")
                
                result = json.loads(response_content)
            except (ValueError, json.JSONDecodeError) as e:
                # If JSON format fails, try without it and parse manually
                try:
                    # Use same increased token limit
                    token_limit = 10000
                    
                    response = self._create_with_token_param(
                        token_limit,
                        temperature=1.0,
                        model=self.model,
                        messages=messages
                    )
                    
                    # Check finish_reason for fallback attempt
                    finish_reason = None
                    if hasattr(response, 'choices') and response.choices:
                        finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
                        if finish_reason == 'length':
                            usage_info = {}
                            if hasattr(response, 'usage'):
                                usage_info = {
                                    "completion_tokens": getattr(response.usage, 'completion_tokens', None),
                                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', None),
                                    "total_tokens": getattr(response.usage, 'total_tokens', None)
                                }
                            error_details = {
                                "error": f"Fallback attempt - response truncated due to token limit ({token_limit})",
                                "finish_reason": finish_reason,
                                "usage": usage_info,
                                "original_error": str(e),
                                "model": self.model
                            }
                            raise ValueError(f"Response was truncated in fallback attempt. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    # Detailed response logging for fallback
                    response_debug = {
                        "model": self.model,
                        "has_choices": hasattr(response, 'choices') and response.choices is not None,
                        "choices_count": len(response.choices) if hasattr(response, 'choices') and response.choices else 0,
                        "response_type": type(response).__name__,
                        "finish_reason": finish_reason,
                        "fallback_attempt": True
                    }
                    
                    if not hasattr(response, 'choices') or not response.choices or len(response.choices) == 0:
                        error_details = {
                            "error": "Fallback attempt also failed - no choices in response",
                            "original_error": str(e),
                            "response_debug": response_debug,
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Empty response received from AI model after fallback. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    response_content = response.choices[0].message.content if hasattr(response.choices[0].message, 'content') else None
                    
                    if not response_content or not response_content.strip():
                        if finish_reason == 'length':
                            error_details = {
                                "error": "Fallback attempt - response content empty due to token limit truncation",
                                "finish_reason": finish_reason,
                                "original_error": str(e),
                                "response_debug": response_debug,
                                "response_content": response_content,
                                "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                                "full_response": str(response)[:1000]
                            }
                            raise ValueError(f"Response was truncated in fallback attempt and content is empty. Debug info: {json.dumps(error_details, indent=2)}")
                        
                        error_details = {
                            "error": "Fallback attempt - response content is empty",
                            "finish_reason": finish_reason,
                            "original_error": str(e),
                            "response_debug": response_debug,
                            "response_content": response_content,
                            "message_object": str(response.choices[0].message) if response.choices[0].message else "None",
                            "full_response": str(response)[:1000]
                        }
                        raise ValueError(f"Empty response received from AI model. The model may not support JSON format or the request timed out. Debug info: {json.dumps(error_details, indent=2)}")
                    
                    # Try to extract JSON from the response (might be wrapped in markdown)
                    content_to_parse = response_content.strip()
                    if content_to_parse.startswith("```"):
                        # Remove markdown code blocks
                        parts = content_to_parse.split("```")
                        if len(parts) > 1:
                            json_part = parts[1]
                            if json_part.startswith("json"):
                                json_part = json_part[4:]
                            content_to_parse = json_part.strip()
                    
                    try:
                        result = json.loads(content_to_parse)
                    except json.JSONDecodeError as je:
                        error_details = {
                            "error": "Failed to parse JSON response",
                            "json_error": str(je),
                            "original_error": str(e),
                            "response_content": response_content[:1000],
                            "content_to_parse": content_to_parse[:1000],
                            "response_debug": response_debug
                        }
                        error_msg = f"Failed to parse JSON response: {str(je)}\nDebug info: {json.dumps(error_details, indent=2)}"
                        raise ValueError(error_msg)
                except Exception as fallback_error:
                    # If fallback also fails, include both errors
                    error_details = {
                        "error": "Both primary and fallback attempts failed",
                        "primary_error": str(e),
                        "fallback_error": str(fallback_error),
                        "model": self.model,
                        "response_debug": response_debug if 'response_debug' in locals() else "Not available"
                    }
                    raise ValueError(f"Failed to get valid response from AI model. Debug info: {json.dumps(error_details, indent=2)}")
            
            # Update context
            conversation_history.append({"role": "assistant", "content": json.dumps(result)})
            context["conversation_history"] = conversation_history
            
            # Update observations
            if result.get("updated_observations"):
                context["observations"].extend(result["updated_observations"])
            
            questions = result.get("questions", [])
            ready_to_build = result.get("ready_to_build", False)
            
            # Format response
            response_text = f"{result.get('acknowledgment', '')}\n\n"
            
            if questions and not ready_to_build:
                response_text += "**Additional questions:**\n"
                for i, q in enumerate(questions, 1):
                    response_text += f"{i}. {q}\n"
            elif ready_to_build:
                response_text += "\n✅ **Perfect! I now have all the information needed to build an optimal prompt!**\n\nClick 'Generate Prompt' to create your channel-specific parsing prompt."
            
            # Update builder prompts in context for transparency
            if not context.get("builder_system_prompt"):
                context["builder_system_prompt"] = system_prompt
            
            return {
                "success": True,
                "response": response_text,
                "has_questions": len(questions) > 0 and not ready_to_build,
                "ready_to_build": ready_to_build,
                "context": context
            }
            
        except Exception as e:
            # Include full error details in the response
            error_message = str(e)
            error_details = {
                "error": error_message,
                "error_type": type(e).__name__,
                "model": self.model,
                "conversation_id": conversation_id
            }
            
            # Try to extract JSON from error message if it contains debug info
            if "Debug info:" in error_message:
                try:
                    debug_start = error_message.find("Debug info:")
                    debug_json = error_message[debug_start + len("Debug info:"):].strip()
                    error_details["debug_info"] = json.loads(debug_json)
                except:
                    error_details["raw_error_message"] = error_message
            
            return {
                "success": False,
                "error": f"Error processing response: {error_message}",
                "error_details": error_details,
                "response": f"❌ Error: {error_message}",
                "has_questions": False,
                "ready_to_build": False,
                "context": context
            }
    
    def finalize_prompt(self, conversation_id: str, context: Dict) -> Dict:
        """
        Generate the final channel-specific prompt based on the conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            context: Full conversation context
        
        Returns:
            Dictionary with generated prompt
        """
        channel_name = context.get("channel_name", "")
        signals_dump = context.get("signals_dump", "")
        observations = context.get("observations", [])
        conversation_history = context.get("conversation_history", [])
        is_update = context.get("is_update", False)
        existing_prompt = context.get("existing_prompt")
        
        # System prompt for final generation
        if is_update:
            system_prompt = f"""Based on the conversation and analysis, EXTEND the existing prompt for parsing trade signals by ADDING new information.

EXISTING PROMPT (DO NOT REMOVE OR REPLACE):
{existing_prompt}

Create an EXTENDED prompt that:
1. KEEPS ALL existing prompt content intact
2. ADDS new sections or information to handle new patterns from the conversation
3. Clearly marks new additions (e.g., "ADDITIONAL PATTERNS:", "NEW FORMATS:", "EXTENDED RULES:", etc.)
4. Ensures the model can understand BOTH old and new signal formats
5. Provides clear, unambiguous parsing instructions for both formats
6. Includes robust error handling for edge cases

CRITICAL INSTRUCTIONS:
- DO NOT remove, replace, or modify the existing prompt content
- ONLY ADD new sections or append to existing sections
- The final prompt should be: [EXISTING PROMPT] + [NEW ADDITIONS]
- Make it clear that the model should handle both old and new formats

The prompt should instruct an AI to parse signals into this COMPLETE JSON format:
{{
    "symbol": "TICKER",
    "action": "BUY" or "SELL",
    "entry_price": float or null,
    "stop_loss": float or null,
    "take_profit": float or null,
    "position_size": int or null,
    "strike": float or null,
    "option_type": "CALL" or "PUT" or null,
    "purchase_price": float or null,
    "expiration_date": "YYYY-MM-DD" or {{"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null}} or null,
    "fraction": float or null,
    "notes": "additional context"
}}

CRITICAL: The prompt MUST ensure ALL of these 8 REQUIRED fields are extracted from every signal:
1. symbol (Stock Ticker) - REQUIRED
2. action (Direction: BUY/SELL) - REQUIRED
3. expiration_date (Expiry Date) - null if not found
4. option_type (Option Type: CALL/PUT) - null if not found
5. strike (Strike Price) - null if not found
6. purchase_price (Purchase Price) - null if not found
7. fraction (Fraction) - null if not found
8. position_size (Position Size) - null if not found

If any field cannot be extracted, it MUST be set to null. Do not guess or assume values.

REQUIREMENTS FOR THE UPDATED PROMPT:
- Be extremely specific about how each field is identified and extracted
- Provide explicit rules for abbreviations and variations
- Include disambiguation rules when patterns could be confused
- Specify how to handle missing or partial information
- Define clear fallback behaviors
- Include examples of correct parsing for complex cases
- Address all edge cases discovered in the conversation
- For options: emphasize date normalization to YYYY-MM-DD format
- For prices: clarify which number corresponds to which field when multiple prices exist
- For fraction: specify how to determine position fraction from phrases like "sell half", "50%", "partial close", "trim 25%"
- For position_size: clarify how many shares/contracts to trade

Output ONLY the updated prompt text (not JSON, not wrapped in quotes)."""
        else:
            system_prompt = """Based on the conversation and analysis, create a COMPREHENSIVE and ROBUST prompt for parsing trade signals.

The prompt you create will be used by another AI model (the execution model) to parse incoming signals from this channel in real-time. The execution model needs crystal-clear, unambiguous instructions to correctly extract trading information.

YOUR TASK: Create a parsing prompt that is:

1. **HIGHLY SPECIFIC** - Leave no room for interpretation
   - Explicitly state how to identify each component
   - Define what each abbreviation means
   - Provide exact extraction rules

2. **PATTERN-AWARE** - Document the signal structure
   - Explain the typical signal format/template
   - Describe component ordering and positioning
   - Note any consistent prefixes/suffixes or markers

3. **COMPREHENSIVE** - Cover ALL REQUIRED fields completely
   You MUST extract these fields from every signal. If a field cannot be extracted, set it to null:
   - **Stock Ticker (symbol)**: The stock symbol/ticker (e.g., "AAPL", "TSLA")
   - **Direction (action)**: "BUY" or "SELL" (uppercase)
   - **Expiry Date (expiration_date)**: Option expiration date. Can be full date "YYYY-MM-DD" or partial date {"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null}. Extract whatever date components are available. Set to null for stocks or if no date information found.
   - **Option Type (option_type)**: "CALL" or "PUT" (null for stocks)
   - **Strike Price (strike)**: Strike price for options (null for stocks)
   - **Purchase Price (purchase_price)**: Price paid for option contract/premium (null for stocks)
   - **Fraction (fraction)**: Percentage of position (0.0-1.0, e.g., 0.5 = 50%) - null if not specified
   - **Position Size (position_size)**: Number of shares/contracts to trade
   - Additional fields: entry_price, stop_loss, take_profit, notes (optional)

4. **EDGE-CASE READY** - Handle variations and problems
   - What to do when fields are missing?
   - How to handle ambiguous abbreviations?
   - Rules for distinguishing similar patterns
   - Date format normalization strategies
   - Multi-value scenarios (ranges, multiple targets)

5. **ERROR-RESISTANT** - Build in validation
   - Sanity checks (e.g., stop loss should be below entry for buys)
   - Required vs optional fields
   - Default values when information is implicit
   - How to handle conflicting information

6. **EXAMPLE-DRIVEN** - Show correct parsing
   - Include 2-3 example signals with their correct JSON output
   - Demonstrate edge case handling
   - Show date normalization examples for options

The execution model must parse signals into this COMPLETE JSON format:
{
    "symbol": "TICKER",
    "action": "BUY" or "SELL",
    "entry_price": float or null,
    "stop_loss": float or null,
    "take_profit": float or null,
    "position_size": int or null,
    "strike": float or null,
    "option_type": "CALL" or "PUT" or null,
    "purchase_price": float or null,
    "expiration_date": "YYYY-MM-DD" or {{"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null}} or null,
    "fraction": float or null,
    "notes": "additional context"
}

CRITICAL REQUIREMENTS - ALL FIELDS MUST BE EXTRACTED:
The prompt MUST instruct the AI to extract ALL of these fields from every signal. If a field cannot be found, it MUST be set to null:

1. **Stock Ticker (symbol)**: REQUIRED - Extract the stock symbol/ticker
2. **Direction (action)**: REQUIRED - Extract "BUY" or "SELL"
3. **Expiry Date (expiration_date)**: Extract option expiration date. Can be full date "YYYY-MM-DD" or partial date {"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null}. Extract whatever date components are available (e.g., "Mar 22" → {"year": null, "month": "03", "day": "22"}). Set to null for stocks or if no date information found.
4. **Option Type (option_type)**: Extract "CALL" or "PUT", set to null for stocks
5. **Strike Price (strike)**: Extract strike price for options, set to null for stocks
6. **Purchase Price (purchase_price)**: Extract option premium/contract price, set to null for stocks
7. **Fraction (fraction)**: Extract position fraction (0.0-1.0) from phrases like "sell half" (0.5), "trim 25%" (0.25), set to null if not specified
8. **Position Size (position_size)**: Extract number of shares/contracts to trade

ADDITIONAL REQUIREMENTS:
- For OPTIONS signals: Extract expiration_date as full date "YYYY-MM-DD" if available, or as partial date {"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null} if only partial date information is available (e.g., "Mar 22" without year)
- For OPTIONS signals: Clearly distinguish between entry_price (for stocks) and purchase_price (option premium)
- For OPTIONS signals: Specify how to identify strike price vs other prices
- Be explicit about disambiguation rules (e.g., "C" = Call vs Close)
- Define handling of implicit information - if field is missing, set to null
- Provide clear rules for edge cases discussed in the conversation
- The prompt must emphasize: "If you cannot extract a field, set it to null. Do not guess or assume values."

STRUCTURE YOUR PROMPT:
1. Start with: "You are parsing trade signals from [channel]. These signals follow this format..."
2. Describe the overall structure and pattern
3. Detail each field extraction with specific rules
4. Address variations and edge cases
5. Provide 2-3 parsing examples
6. End with validation rules and error handling guidance

Output ONLY the execution prompt text (not JSON, not wrapped in quotes). Make it thorough, clear, and bulletproof."""
        
        # Compile everything learned
        if is_update:
            user_prompt = f"""Channel: {channel_name}

EXISTING PROMPT (DO NOT REMOVE OR REPLACE - KEEP ALL OF THIS):
{existing_prompt}

Key Observations from New Signals:
{chr(10).join(['- ' + obs for obs in observations])}

New Sample Signals:
{signals_dump[:1000]}...

EXTEND the existing prompt by ADDING new sections or information to handle these new patterns.
The final prompt should be: [ALL EXISTING PROMPT CONTENT] + [NEW ADDITIONS FOR NEW PATTERNS]
Make it clear the model should handle BOTH old and new formats."""
        else:
            user_prompt = f"""Channel: {channel_name}

Key Observations:
{chr(10).join(['- ' + obs for obs in observations])}

Sample Signals:
{signals_dump[:1000]}...

Based on our conversation and analysis, generate the optimal parsing prompt now."""
        
        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add relevant parts of conversation for context
            if len(conversation_history) > 0:
                # Add first and last parts of conversation
                messages.append(conversation_history[0])
                if len(conversation_history) > 2:
                    messages.append(conversation_history[-1])
            
            messages.append({"role": "user", "content": user_prompt})
            
            response = self._create_with_token_param(
                10000,
                temperature=1.0,
                model=self.model,
                messages=messages
            )
            
            generated_prompt = response.choices[0].message.content.strip()
            
            # Add metadata
            metadata = f"""[Channel: {channel_name}]
[{'Updated' if is_update else 'Generated'}: {datetime.now().isoformat()}]
[Conversational Build - AI Analyzed]

"""
            
            # Compile the full builder prompt for transparency
            full_builder_prompt = f"""=== SYSTEM PROMPT ===
{system_prompt}

=== USER PROMPT ===
{user_prompt}

=== CONVERSATION CONTEXT ===
Observations: {', '.join(observations)}
Conversation turns: {len(conversation_history)}"""
            
            # Update context with finalize prompts for transparency
            context["finalize_system_prompt"] = system_prompt
            context["finalize_user_prompt"] = user_prompt
            
            return {
                "success": True,
                "prompt": metadata + generated_prompt,
                "builder_prompt_used": full_builder_prompt,
                "context": context,  # Return updated context with finalize prompts
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "prompt": None,
                "error": f"Error generating final prompt: {str(e)}"
            }

