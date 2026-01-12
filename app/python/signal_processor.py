"""
Signal Processor module that uses AI to parse trade signals using channel-specific prompts.
This module takes incoming signals, applies the appropriate channel prompt,
and converts them into structured data for Webull API execution.
"""

import json
import re
from datetime import datetime
from typing import Dict, Optional
from openai import OpenAI


class SignalProcessor:
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """
        Initialize the SignalProcessor with OpenAI API credentials.

        Args:
            api_key: OpenAI API key
            model: Model to use for signal processing (execution model)
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
    
    def _normalize_expiration_date(self, date_str: str) -> Optional[Dict]:
        """
        Normalize expiration date, handling both full and partial dates.
        
        Args:
            date_str: Date string in various formats (can be partial)
            
        Returns:
            - Full date: String in "YYYY-MM-DD" format
            - Partial date: Dictionary with format {"year": "YYYY" or None, "month": "MM" or None, "day": "DD" or None}
            - None if no date information found
        """
        if not date_str:
            return None
        
        # If already a dictionary (partial date from AI), return as-is
        if isinstance(date_str, dict):
            return date_str
        
        date_str = str(date_str).strip()
        
        # Month name mapping
        month_map = {
            'jan': '01', 'january': '01',
            'feb': '02', 'february': '02',
            'mar': '03', 'march': '03',
            'apr': '04', 'april': '04',
            'may': '05',
            'jun': '06', 'june': '06',
            'jul': '07', 'july': '07',
            'aug': '08', 'august': '08',
            'sep': '09', 'september': '09',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12'
        }
        
        # Try full date formats first (YYYY-MM-DD)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str  # Return as full date string
            except:
                pass
        
        # Try various full date formats
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%b %d, %Y',
            '%B %d, %Y',
            '%m/%d/%y',  # 2-digit year
            '%d/%m/%y',
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If 2-digit year, assume 20xx
                if fmt.endswith('%y') and dt.year < 2000:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime('%Y-%m-%d')  # Return as full date string
            except:
                continue
        
        # Try to extract full date from text patterns (e.g., "expires 12/20/2025")
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        if len(groups[0]) == 4:  # YYYY-MM-DD or YYYY/MM/DD
                            year, month, day = groups[0], groups[1], groups[2]
                        else:  # MM/DD/YYYY or MM-DD-YYYY
                            month, day, year = groups[0], groups[1], groups[2]
                        
                        year = int(year)
                        if year < 100:
                            year += 2000
                        
                        dt = datetime(year, int(month), int(day))
                        return dt.strftime('%Y-%m-%d')  # Return as full date string
                    except:
                        continue
        
        # NEW: Handle partial dates - Month and Day only (no year)
        # Pattern: "Mar 22" or "March 22" or "03/22" or "3/22"
        month_day_patterns = [
            # Month name + day: "Mar 22", "March 22", "Mar 22nd", "March 22nd"
            r'(Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)\s+(\d{1,2})(?:st|nd|rd|th)?',
            # Numeric month/day: "03/22", "3/22", "03-22", "3-22" (without year)
            r'^(\d{1,2})[/-](\d{1,2})(?![/-]\d)',  # MM/DD or DD/MM without year (not followed by another number)
        ]
        
        for pattern in month_day_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Check if first group is month name
                    if groups[0].isalpha():
                        month_name = groups[0].lower()
                        month = month_map.get(month_name)
                        day = groups[1].zfill(2)  # Pad with zero
                        if month:
                            return {"year": None, "month": month, "day": day}
                    else:
                        # Could be MM/DD or DD/MM - assume MM/DD for US format
                        # But we need to validate: month should be 01-12, day should be 01-31
                        first = int(groups[0])
                        second = int(groups[1])
                        if 1 <= first <= 12 and 1 <= second <= 31:
                            # Likely MM/DD format
                            month = str(first).zfill(2)
                            day = str(second).zfill(2)
                            return {"year": None, "month": month, "day": day}
                        elif 1 <= first <= 31 and 1 <= second <= 12:
                            # Likely DD/MM format
                            day = str(first).zfill(2)
                            month = str(second).zfill(2)
                            return {"year": None, "month": month, "day": day}
        
        # NEW: Handle partial dates - Month only (no day or year)
        # Pattern: "March" or "Mar" or "03"
        month_only_patterns = [
            r'^(Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)$',
            r'^(\d{1,2})$',  # Just a number - could be month
        ]
        
        for pattern in month_only_patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if match:
                if match.group(1).isalpha():
                    month_name = match.group(1).lower()
                    month = month_map.get(month_name)
                    if month:
                        return {"year": None, "month": month, "day": None}
                else:
                    # Just a number - validate it's a valid month
                    num = int(match.group(1))
                    if 1 <= num <= 12:
                        return {"year": None, "month": str(num).zfill(2), "day": None}
        
        # NEW: Handle partial dates - Year and Month only (no day)
        # Pattern: "2025-03" or "03/2025" or "March 2025"
        year_month_patterns = [
            r'(\d{4})[/-](\d{1,2})$',  # YYYY/MM or YYYY-MM
            r'(\d{1,2})[/-](\d{4})$',  # MM/YYYY or MM-YYYY
            r'(Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)\s+(\d{4})',  # Month Year
        ]
        
        for pattern in year_month_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    if groups[0].isalpha():
                        # Month name + year
                        month_name = groups[0].lower()
                        month = month_map.get(month_name)
                        year = groups[1]
                        if month:
                            return {"year": year, "month": month, "day": None}
                    else:
                        # Numeric format
                        if len(groups[0]) == 4:  # YYYY/MM
                            year = groups[0]
                            month = groups[1].zfill(2)
                            return {"year": year, "month": month, "day": None}
                        else:  # MM/YYYY
                            month = groups[0].zfill(2)
                            year = groups[1]
                            return {"year": year, "month": month, "day": None}
        
        return None
    
    def parse_signal(self, signal_content: str, channel_prompt: str) -> Dict:
        """
        Parse a trade signal using the channel-specific prompt.
        
        Args:
            signal_content: The raw signal content
            channel_prompt: The channel-specific parsing prompt
        
        Returns:
            Dictionary with parsed signal data in Webull-compatible format
        """
        # System message that includes the channel prompt
        system_message = f"""{channel_prompt}

CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no markdown, no code blocks, no additional text. Just the raw JSON object.

REQUIRED JSON FORMAT:
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
    "notes": "any additional context"
}}

CRITICAL FIELD DESCRIPTIONS - ALL FIELDS MUST BE EXTRACTED:
You MUST extract ALL of these fields from every signal. If a field cannot be extracted, set it to null:

1. **symbol (Stock Ticker)**: REQUIRED - The stock symbol/ticker (e.g., "AAPL", "TSLA"). If not found, set to null.
2. **action (Direction)**: REQUIRED - "BUY" or "SELL" (uppercase). If not found, set to null.
3. **expiration_date (Expiry Date)**: Option expiration date. Can be:
   - Full date: "YYYY-MM-DD" format (e.g., "2025-12-20")
   - Partial date: Object with format {{"year": "YYYY" or null, "month": "MM" or null, "day": "DD" or null}}
   - Examples:
     * "Mar 22" (no year) → {{"year": null, "month": "03", "day": "22"}}
     * "12/20" (no year) → {{"year": null, "month": "12", "day": "20"}}
     * "March 2025" (no day) → {{"year": "2025", "month": "03", "day": null}}
     * "2025-12-20" (full date) → "2025-12-20" (full date string)
     * "Mar" (only month) → {{"year": null, "month": "03", "day": null}}
   - Set to null for stocks or if no date information found.
   - IMPORTANT: Extract whatever date components are available. If year is missing, set year to null. If day is missing, set day to null. Extract partial dates when full date is not available.
4. **option_type (Option Type)**: "CALL" or "PUT" for options. Set to null for stocks or if not found.
5. **strike (Strike Price)**: Strike price for options. Set to null for stocks or if not found.
6. **purchase_price (Purchase Price)**: Price paid for option contract/premium. Set to null for stocks or if not found.
7. **fraction (Fraction)**: Percentage of position to trade (0.0-1.0, e.g., 0.5 = 50%). Set to null if not specified.
8. **position_size (Position Size)**: Number of shares/contracts to trade. Set to null if not found.

ADDITIONAL OPTIONAL FIELDS:
- entry_price: Entry price for the trade (set to null if not found)
- stop_loss: Stop loss price (set to null if not found)
- take_profit: Take profit price (set to null if not found)
- notes: Any additional context or notes

IMPORTANT: If you cannot extract a field, you MUST set it to null. Do not guess, assume, or leave fields undefined.

CRITICAL INSTRUCTIONS FOR OPTIONS TRADES:
- For options trades, you MUST extract and include ALL of these fields:
  * strike: The strike price as a number (e.g., 250.0)
  * option_type: Either "CALL" or "PUT" (uppercase)
  * purchase_price: The price paid for the option contract (e.g., 5.50)
  * expiration_date: MUST be in "YYYY-MM-DD" format (e.g., "2025-12-20")
  
- For expiration_date, extract ALL available date components:
  * Full dates: "expires 12/20/2025" -> "2025-12-20"
  * Full dates: "expiring Dec 20, 2025" -> "2025-12-20"
  * Full dates: "exp 2025-12-20" -> "2025-12-20"
  * Full dates: "12/20/25" -> "2025-12-20" (assume 20xx if 2-digit year)
  * Partial dates: "Mar 22" -> {{"year": null, "month": "03", "day": "22"}}
  * Partial dates: "12/20" -> {{"year": null, "month": "12", "day": "20"}}
  * Partial dates: "March 2025" -> {{"year": "2025", "month": "03", "day": null}}
  * Partial dates: "Mar" -> {{"year": null, "month": "03", "day": null}}
  * Extract whatever components are available - don't guess missing parts

CRITICAL INSTRUCTIONS FOR FRACTION:
- Fraction represents the percentage of the position to trade (0.0 to 1.0)
- Look for indicators like: "sell half", "50%", "partial close", "trim 25%", etc.
- Examples:
  * "sell half the position" -> fraction: 0.5
  * "close 25% of position" -> fraction: 0.25
  * "take profits on 1/3" -> fraction: 0.33
  * "sell all" or no fraction mentioned -> fraction: null (or 1.0 for 100%)
- If no fraction is specified, set to null
- Fraction is typically used with SELL actions for partial position closing

- For stock trades (non-options), set strike, option_type, purchase_price, and expiration_date to null.

REMINDER: Output ONLY the JSON object. Start with {{ and end with }}. No markdown, no code blocks, no explanations."""
        
        # User message with the signal to parse
        user_message = f"Parse this trade signal:\n\n{signal_content}"
        
        try:
            # Removed max_tokens and max_completion_tokens to avoid parameter compatibility issues
            # Using model default token limits instead
            model_lower = self.model.lower()
            
            # Build request parameters
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            }
            
            # Use temperature 1.0 (default) for all models for consistency
            # This works with all models including o1, o3 that only support default temperature
            request_params["temperature"] = 1.0
            
            # Try to use JSON format for better reliability (not all models support this)
            # Models that support response_format: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
            # Models that don't: o1, o3 series
            supports_json_format = 'o1' not in model_lower and 'o3' not in model_lower
            if supports_json_format:
                try:
                    request_params["response_format"] = {"type": "json_object"}
                except:
                    pass  # If it fails, we'll continue without it
            
            # Removed max_tokens and max_completion_tokens - using model defaults
            # This avoids parameter compatibility issues between different models and library versions
            response = None
            try:
                # Call the execution model to parse the signal
                print(f"\n🔵 Calling OpenAI API with model: {self.model}")
                print(f"   Using model default token limit (no max_tokens/max_completion_tokens)")
                response = self._get_client().chat.completions.create(**request_params)
                print(f"✅ OpenAI API call successful")
            except Exception as api_error:
                # Handle various API errors with fallbacks
                error_str = str(api_error).lower()
                
                # If JSON format is not supported, remove it and retry
                if 'response_format' in error_str or 'json_object' in error_str:
                    request_params.pop("response_format", None)
                    try:
                        response = self._get_client().chat.completions.create(**request_params)
                    except Exception as retry_error:
                        error_str = str(retry_error).lower()
                        # Continue with other error handling
                
                # Only retry if we don't have a response yet
                if response is None:
                    if 'temperature' in error_str and ('not supported' in error_str or 'unsupported value' in error_str):
                        # Remove temperature and retry (will use default)
                        request_params.pop("temperature", None)
                        response = self._get_client().chat.completions.create(**request_params)
                    else:
                        # Re-raise if we haven't gotten a response yet and can't retry
                        raise
            
            # Validate response structure
            if not hasattr(response, 'choices') or not response.choices:
                return {
                    "success": False,
                    "data": None,
                    "error": "Empty response from AI model - no choices returned",
                    "raw_response": None
                }
            
            if len(response.choices) == 0:
                return {
                    "success": False,
                    "data": None,
                    "error": "Empty response from AI model - choices array is empty",
                    "raw_response": None
                }
            
            # Extract the response content
            if not hasattr(response.choices[0].message, 'content'):
                return {
                    "success": False,
                    "data": None,
                    "error": "Empty response from AI model - message has no content",
                    "raw_response": None
                }
            
            parsed_text = response.choices[0].message.content
            
            # Check finish_reason to see if response was truncated
            finish_reason = getattr(response.choices[0], 'finish_reason', None)
            was_truncated = (finish_reason == 'length')
            
            # Check if response is empty
            if not parsed_text or not parsed_text.strip():
                error_msg = f"Empty response from AI model"
                if finish_reason:
                    error_msg += f" (finish_reason: {finish_reason})"
                if was_truncated:
                    error_msg += f" - Response was truncated (hit model's default token limit). The model may be generating a very long response. This could indicate an issue with the channel prompt or the signal format."
                
                return {
                    "success": False,
                    "data": None,
                    "error": error_msg,
                    "raw_response": None
                }
            
            parsed_text = parsed_text.strip()
            
            # Try to parse as JSON
            try:
                # Remove markdown code blocks if present
                original_text = parsed_text
                if parsed_text.startswith("```"):
                    # Extract content from markdown code block
                    parts = parsed_text.split("```")
                    if len(parts) > 1:
                        json_part = parts[1]
                        if json_part.startswith("json"):
                            json_part = json_part[4:]
                        parsed_text = json_part.strip()
                    else:
                        # If parsing fails, try the original
                        parsed_text = original_text.strip()
                
                # If still empty after processing, return error
                if not parsed_text or not parsed_text.strip():
                    return {
                        "success": False,
                        "data": None,
                        "error": "Empty response after processing - AI model returned no content",
                        "raw_response": original_text
                    }
                
                # Try to parse JSON
                parsed_data = json.loads(parsed_text)
                
                # Validate required fields
                if "symbol" not in parsed_data or "action" not in parsed_data:
                    raise ValueError("Missing required fields: symbol or action")
                
                # Normalize action to uppercase
                if parsed_data["action"]:
                    parsed_data["action"] = parsed_data["action"].upper()
                    
                # Validate action
                if parsed_data["action"] not in ["BUY", "SELL"]:
                    raise ValueError(f"Invalid action: {parsed_data['action']}")
                
                # Normalize expiration_date format if present
                if parsed_data.get("expiration_date"):
                    expiration_date = parsed_data["expiration_date"]
                    
                    # Check if it's already a dict (partial date from AI)
                    if isinstance(expiration_date, dict):
                        # Validate partial date structure
                        if "year" in expiration_date or "month" in expiration_date or "day" in expiration_date:
                            # Ensure all keys are present (set to None if missing)
                            normalized_partial = {
                                "year": expiration_date.get("year"),
                                "month": expiration_date.get("month"),
                                "day": expiration_date.get("day")
                            }
                            # Format month and day with leading zeros if present
                            if normalized_partial["month"]:
                                try:
                                    month_num = int(normalized_partial["month"])
                                    normalized_partial["month"] = str(month_num).zfill(2)
                                except:
                                    pass
                            if normalized_partial["day"]:
                                try:
                                    day_num = int(normalized_partial["day"])
                                    normalized_partial["day"] = str(day_num).zfill(2)
                                except:
                                    pass
                            parsed_data["expiration_date"] = normalized_partial
                        else:
                            # Invalid dict structure, try to normalize
                            expiration_date = self._normalize_expiration_date(str(expiration_date))
                            parsed_data["expiration_date"] = expiration_date if expiration_date else None
                    else:
                        # Try to normalize - may return full date string or partial date dict
                        normalized = self._normalize_expiration_date(expiration_date)
                        if normalized:
                            parsed_data["expiration_date"] = normalized
                        else:
                            # If normalization failed, set to null
                            parsed_data["expiration_date"] = None
                
                # Normalize option_type to uppercase if present
                if parsed_data.get("option_type"):
                    parsed_data["option_type"] = parsed_data["option_type"].upper()
                    if parsed_data["option_type"] not in ["CALL", "PUT"]:
                        parsed_data["option_type"] = None
                
                # Log successful parsing for debugging
                print("\n" + "="*80)
                print("✅ SIGNAL PARSED SUCCESSFULLY")
                print("="*80)
                print(f"Response length: {len(parsed_text)} characters")
                print(f"Finish reason: {finish_reason}")
                print(f"Was truncated: {was_truncated}")
                print("\n--- RAW OPENAI RESPONSE ---")
                print(parsed_text)
                print("--- END RAW RESPONSE ---")
                print("\n--- PARSED DATA ---")
                print(json.dumps(parsed_data, indent=2, default=str))
                print("--- END PARSED DATA ---")
                print("="*80 + "\n")
                
                return {
                    "success": True,
                    "data": parsed_data,
                    "error": None,
                    "raw_response": parsed_text
                }
                
            except json.JSONDecodeError as je:
                # Provide more helpful error message
                error_msg = f"Failed to parse JSON response: {str(je)}"
                if was_truncated:
                    error_msg += f" - Response was truncated (hit model's default token limit), which may have caused invalid JSON. The model may be generating a very long response."
                elif not parsed_text or len(parsed_text) == 0:
                    error_msg += " - Response was empty"
                else:
                    # Show first 200 chars of response for debugging
                    preview = parsed_text[:200] + ("..." if len(parsed_text) > 200 else "")
                    error_msg += f"\n\nRaw response preview: {preview}"
                
                # Log the FULL raw response for debugging
                print("\n" + "="*80)
                print("❌ JSON PARSING FAILED - FULL RAW RESPONSE")
                print("="*80)
                print(f"JSON Error: {str(je)}")
                print(f"Response length: {len(parsed_text) if parsed_text else 0} characters")
                print(f"Was truncated: {was_truncated}")
                print(f"Finish reason: {finish_reason}")
                print("\n--- FULL RAW RESPONSE FROM OPENAI ---")
                print(parsed_text if parsed_text else "(empty)")
                print("--- END RAW RESPONSE ---")
                print("="*80 + "\n")
                
                return {
                    "success": False,
                    "data": None,
                    "error": error_msg,
                    "raw_response": parsed_text
                }
            except ValueError as ve:
                # Log validation errors with full response
                print("\n" + "="*80)
                print("❌ SIGNAL VALIDATION FAILED - FULL RAW RESPONSE")
                print("="*80)
                print(f"Validation Error: {str(ve)}")
                print(f"Response length: {len(parsed_text) if parsed_text else 0} characters")
                print("\n--- FULL RAW RESPONSE FROM OPENAI ---")
                print(parsed_text if parsed_text else "(empty)")
                print("--- END RAW RESPONSE ---")
                print("="*80 + "\n")
                
                return {
                    "success": False,
                    "data": None,
                    "error": str(ve),
                    "raw_response": parsed_text
                }
                
        except Exception as e:
            # Log API errors with full exception details
            print("\n" + "="*80)
            print("❌ OPENAI API ERROR")
            print("="*80)
            print(f"Exception Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            import traceback
            print("\n--- FULL TRACEBACK ---")
            print(traceback.format_exc())
            print("--- END TRACEBACK ---")
            print("="*80 + "\n")
            
            return {
                "success": False,
                "data": None,
                "error": f"Error calling OpenAI API: {str(e)}",
                "raw_response": None
            }
    
    def validate_signal(self, parsed_signal: Dict) -> Dict:
        """
        Validate a parsed signal before execution.
        
        Args:
            parsed_signal: The parsed signal data
        
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        # Check required fields
        if not parsed_signal.get("symbol"):
            errors.append("Symbol is required")
        
        if not parsed_signal.get("action"):
            errors.append("Action (BUY/SELL) is required")
        elif parsed_signal["action"] not in ["BUY", "SELL"]:
            errors.append(f"Invalid action: {parsed_signal['action']}")
        
        # Check optional but important fields
        if not parsed_signal.get("entry_price") and not parsed_signal.get("purchase_price"):
            warnings.append("No entry price or purchase price specified - will use market price")
        
        if not parsed_signal.get("stop_loss"):
            warnings.append("No stop loss specified - trade will not have risk protection")
        
        # Check for position_size (new field name) or quantity (old field name for backward compatibility)
        position_size = parsed_signal.get("position_size") or parsed_signal.get("quantity")
        if not position_size:
            warnings.append("No position size specified - will need to calculate position size")
        
        # Validate fraction if present
        fraction = parsed_signal.get("fraction")
        if fraction is not None:
            try:
                fraction_val = float(fraction)
                if fraction_val < 0 or fraction_val > 1:
                    warnings.append(f"Fraction value {fraction_val} is outside valid range (0.0-1.0)")
            except (ValueError, TypeError):
                warnings.append(f"Invalid fraction value: {fraction}")
        
        # Price validation
        if parsed_signal.get("entry_price") and parsed_signal.get("stop_loss"):
            entry = float(parsed_signal["entry_price"])
            stop = float(parsed_signal["stop_loss"])
            
            if parsed_signal["action"] == "BUY" and stop >= entry:
                errors.append(f"Stop loss ({stop}) must be below entry price ({entry}) for BUY orders")
            elif parsed_signal["action"] == "SELL" and stop <= entry:
                errors.append(f"Stop loss ({stop}) must be above entry price ({entry}) for SELL orders")
        
        if parsed_signal.get("entry_price") and parsed_signal.get("take_profit"):
            entry = float(parsed_signal["entry_price"])
            tp = float(parsed_signal["take_profit"])
            
            if parsed_signal["action"] == "BUY" and tp <= entry:
                errors.append(f"Take profit ({tp}) must be above entry price ({entry}) for BUY orders")
            elif parsed_signal["action"] == "SELL" and tp >= entry:
                errors.append(f"Take profit ({tp}) must be below entry price ({entry}) for SELL orders")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def validate_options_signal(self, parsed_signal: Dict) -> Dict:
        """
        Validate that an options signal has all required fields before execution.
        
        Required fields for options:
        - symbol
        - action
        - strike
        - option_type
        - purchase_price
        - expiration_date
        
        Args:
            parsed_signal: The parsed signal data
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        missing_fields = []
        
        # Check required fields
        if not parsed_signal.get("symbol"):
            missing_fields.append("Symbol")
        
        if not parsed_signal.get("action"):
            missing_fields.append("Action")
        elif parsed_signal["action"] not in ["BUY", "SELL"]:
            errors.append(f"Invalid action: {parsed_signal['action']}. Must be BUY or SELL.")
        
        if not parsed_signal.get("strike"):
            missing_fields.append("Strike")
        
        if not parsed_signal.get("option_type"):
            missing_fields.append("Option Type")
        elif parsed_signal["option_type"] not in ["CALL", "PUT"]:
            errors.append(f"Invalid option type: {parsed_signal['option_type']}. Must be CALL or PUT.")
        
        if not parsed_signal.get("purchase_price"):
            missing_fields.append("Purchase Price")
        
        # Check expiration_date - OPTIONAL (Smart Executor will find nearest if missing)
        # Only validate format if provided, but don't require it
        expiration_date = parsed_signal.get("expiration_date")
        if expiration_date:
            # If expiration_date is provided, validate its format
            if isinstance(expiration_date, dict):
                # Partial date - if provided, should have at least month for it to be useful
                # But we won't fail validation if it's missing - Smart Executor will handle it
                if not expiration_date.get("month") and not expiration_date.get("day"):
                    # If dict is provided but has no useful data, that's okay - Smart Executor will search
                    pass
        # If expiration_date is not provided at all, that's fine - Smart Executor will find nearest date
        
        # Build error message
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            errors.insert(0, error_msg)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "missing_fields": missing_fields
        }
    
    def format_for_webull(self, parsed_signal: Dict) -> Dict:
        """
        Format a parsed signal for Webull API execution.
        
        Args:
            parsed_signal: The parsed and validated signal data
        
        Returns:
            Dictionary formatted for Webull API
        """
        # Get position size (supports both new field name and legacy)
        position_size = parsed_signal.get("position_size") or parsed_signal.get("quantity")
        
        # Calculate actual quantity based on fraction if present
        actual_quantity = position_size
        if parsed_signal.get("fraction") is not None and position_size:
            actual_quantity = int(position_size * parsed_signal["fraction"])
        
        webull_format = {
            "symbol": parsed_signal["symbol"],
            "action": parsed_signal["action"],
            "orderType": "MKT" if not parsed_signal.get("entry_price") else "LMT",
            "price": parsed_signal.get("entry_price") or parsed_signal.get("purchase_price"),
            "quantity": actual_quantity,
            "timeInForce": "DAY",
            "outsideRegularTradingHour": False
        }
        
        # Add options-specific fields if present
        if parsed_signal.get("strike"):
            webull_format["strike"] = parsed_signal["strike"]
        
        if parsed_signal.get("option_type"):
            webull_format["option_type"] = parsed_signal["option_type"].upper()  # Ensure CALL/PUT
        
        if parsed_signal.get("expiration_date"):
            expiration_date = parsed_signal["expiration_date"]
            # Handle partial dates - convert to string format for Webull API
            if isinstance(expiration_date, dict):
                # Partial date - format as MM/DD/YYYY or best available format
                # For Webull API, we need a full date, so we'll use current year if year is null
                # or format as MM/DD if only month/day available
                year = expiration_date.get("year")
                month = expiration_date.get("month")
                day = expiration_date.get("day")
                
                if year and month and day:
                    # Full date available
                    webull_format["expiration_date"] = f"{year}-{month}-{day}"
                elif month and day:
                    # Partial date - use current year as fallback
                    from datetime import datetime
                    current_year = datetime.now().year
                    webull_format["expiration_date"] = f"{current_year}-{month}-{day}"
                else:
                    # Incomplete date - store as JSON string for reference
                    webull_format["expiration_date"] = json.dumps(expiration_date)
            else:
                # Full date string
                webull_format["expiration_date"] = expiration_date
        
        # Use purchase_price if provided and entry_price is not
        if not webull_format.get("price") and parsed_signal.get("purchase_price"):
            webull_format["price"] = parsed_signal["purchase_price"]
        
        # Add stop loss and take profit as separate bracket orders if specified
        brackets = []
        
        if parsed_signal.get("stop_loss"):
            brackets.append({
                "type": "STOP",
                "price": parsed_signal["stop_loss"],
                "action": "SELL" if parsed_signal["action"] == "BUY" else "BUY"
            })
        
        if parsed_signal.get("take_profit"):
            brackets.append({
                "type": "LIMIT",
                "price": parsed_signal["take_profit"],
                "action": "SELL" if parsed_signal["action"] == "BUY" else "BUY"
            })
        
        if brackets:
            webull_format["brackets"] = brackets
        
        return webull_format


