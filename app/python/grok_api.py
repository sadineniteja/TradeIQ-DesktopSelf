"""
Grok API Integration - xAI's Grok for engagement prediction and trend analysis
"""

import requests
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GrokAPI:
    """Interface for xAI Grok API"""
    
    def __init__(self, db=None, alphavantage_api=None):
        """Initialize Grok API client"""
        self.db = db
        self.alphavantage_api = alphavantage_api  # Alpha Vantage API for stock prices
        self.api_key = None
        self.base_url = "https://api.x.ai/v1"  # xAI API endpoint
        self.model = "grok-2-1212"  # Default model (grok-2-1212, grok-3, or grok-4)
        self.is_configured = False
        self.is_available = True
        
        # Load configuration if database available
        if self.db:
            self._load_config()
    
    def _load_config(self):
        """Load Grok API configuration from database"""
        try:
            self.api_key = self.db.get_setting("grok_api_key", "")
            self.model = self.db.get_setting("grok_model", "grok-2-1212")
            self.is_configured = bool(self.api_key)
            
            if self.is_configured:
                logger.info(f"[OK] Grok API configured (model: {self.model})")
            else:
                logger.info("[WARN] Grok API not configured")
                
        except Exception as e:
            logger.error(f"Error loading Grok API config: {e}")
            self.is_configured = False
    
    def save_config(self, api_key: str = None, model: str = None) -> bool:
        """
        Save Grok API configuration
        """
        try:
            if not api_key or not api_key.strip():
                return False
            
            # Use default model if not provided
            if not model:
                model = "grok-2-1212"
            
            # Save to database
            if self.db:
                self.db.save_setting("grok_api_key", api_key.strip())
                self.db.save_setting("grok_model", model.strip())
            
            # Update instance
            self.api_key = api_key.strip()
            self.model = model.strip()
            self.is_configured = True
            
            logger.info(f"[OK] Grok API configuration saved (model: {model})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Grok API config: {e}")
            return False
    
    def get_config(self) -> Dict:
        """Get current Grok API configuration (masked)"""
        return {
            "api_key": "***" if self.api_key else "",
            "model": self.model,
            "is_configured": self.is_configured,
            "is_available": self.is_available
        }
    
    def is_enabled(self) -> bool:
        """Check if Grok API is enabled"""
        try:
            enabled = self.db.get_setting("grok_enabled", "true").lower() == "true"
            return enabled and self.is_configured
        except:
            return False
    
    def test_connection(self) -> Dict:
        """
        Test Grok API connectivity
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Grok API not configured. Please add your API key."
            }
        
        try:
            # Test with a simple chat completion
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say 'Connection successful' if you can read this."}
                    ],
                    "max_tokens": 50,
                    "temperature": 0.3
                }
            )
            
            if response and "choices" in response:
                return {
                    "success": True,
                    "message": "Grok API connection successful!",
                    "model": self.model,
                    "response": response["choices"][0]["message"]["content"]
                }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected response format from Grok API. Response: {response}"
                }
                
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = f"HTTP {e.response.status_code}: {error_data.get('error', {}).get('message', str(e))}"
                except:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            
            logger.error(f"Grok API connection test failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            logger.error(f"Grok API connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _make_request(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Make API request to Grok"""
        if not self.api_key:
            raise ValueError("Grok API key not configured")
        
        url = f"{self.base_url}/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Making Grok API request to: {url}")
        logger.info(f"Model: {data.get('model')}")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            # Log response for debugging
            logger.info(f"Grok API response status: {response.status_code}")
            
            if response.status_code == 404:
                error_msg = "404 Not Found - The Grok API endpoint or model may not be available. "
                error_msg += f"Tried URL: {url}, Model: {data.get('model')}. "
                error_msg += "This could mean: (1) Your API key doesn't have access to this model, "
                error_msg += "(2) The model name is incorrect, or (3) Your xAI account needs to be upgraded. "
                error_msg += "Visit https://console.x.ai/ to check your account status and available models."
                raise ValueError(error_msg)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                if 'error' in error_data:
                    error_msg += f": {error_data['error'].get('message', str(error_data['error']))}"
                else:
                    error_msg += f": {e.response.text[:200]}"
            except:
                error_msg += f": {e.response.text[:200]}"
            
            logger.error(f"Grok API HTTP error: {error_msg}")
            raise ValueError(error_msg)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Grok API request error: {e}")
            raise
    
    def parse_signal(self, signal_content: str, channel_prompt: str) -> Dict:
        """
        Parse a trade signal using Grok model with the channel-specific prompt.
        Compatible with SignalProcessor interface.
        
        Args:
            signal_content: The raw signal text to parse
            channel_prompt: The channel-specific parsing prompt
            
        Returns:
            Dict with format: {"success": bool, "data": dict or None, "error": str or None, "raw_response": str}
        """
        if not self.is_enabled():
            return {
                "success": False,
                "data": None,
                "error": "Grok API not configured or not enabled",
                "raw_response": None
            }
        
        try:
            # Build the messages for Grok
            messages = [
                {"role": "system", "content": channel_prompt},
                {"role": "user", "content": f"Parse this trade signal:\n\n{signal_content}"}
            ]
            
            print(f"\n🔵 Calling Grok API with model: {self.model}")
            
            # Make the API call
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 1.0
                }
            )
            
            print(f"✅ Grok API call successful")
            
            if not response or "choices" not in response or not response["choices"]:
                return {
                    "success": False,
                    "data": None,
                    "error": "Empty response from Grok model",
                    "raw_response": None
                }
            
            parsed_text = response["choices"][0]["message"]["content"]
            
            if not parsed_text or not parsed_text.strip():
                return {
                    "success": False,
                    "data": None,
                    "error": "Empty response from Grok model",
                    "raw_response": None
                }
            
            parsed_text = parsed_text.strip()
            
            # Try to extract JSON from the response
            try:
                original_text = parsed_text
                if parsed_text.startswith("```"):
                    parts = parsed_text.split("```")
                    if len(parts) > 1:
                        json_part = parts[1]
                        if json_part.startswith("json"):
                            json_part = json_part[4:]
                        parsed_text = json_part.strip()
                
                parsed_data = json.loads(parsed_text)
                
                print("\n" + "="*80)
                print("✅ GROK API CALL SUCCESS - RAW RESPONSE & PARSED DATA")
                print("="*80)
                print(f"Response length: {len(parsed_text)} characters")
                print("\n--- RAW GROK RESPONSE ---")
                print(parsed_text)
                print("--- END RAW RESPONSE ---")
                print("\n--- PARSED DATA ---")
                print(json.dumps(parsed_data, indent=2, default=str))
                print("="*80 + "\n")
                
                # Validate required fields
                if "symbol" not in parsed_data or "action" not in parsed_data:
                    raise ValueError("Missing required fields: symbol or action")
                
                # Normalize action to uppercase
                if parsed_data["action"]:
                    parsed_data["action"] = parsed_data["action"].upper()
                
                if parsed_data["action"] not in ["BUY", "SELL"]:
                    raise ValueError(f"Invalid action: {parsed_data['action']}")
                
                # Normalize option_type if present
                if parsed_data.get("option_type"):
                    parsed_data["option_type"] = parsed_data["option_type"].upper()
                    if parsed_data["option_type"] not in ["CALL", "PUT"]:
                        parsed_data["option_type"] = None
                
                return {
                    "success": True,
                    "data": parsed_data,
                    "error": None,
                    "raw_response": parsed_text
                }
                
            except json.JSONDecodeError as je:
                error_msg = f"Failed to parse JSON response: {str(je)}"
                
                print("\n" + "="*80)
                print("❌ GROK JSON PARSING FAILED - FULL RAW RESPONSE")
                print("="*80)
                print(f"JSON Error: {str(je)}")
                print(f"Response length: {len(parsed_text) if parsed_text else 0} characters")
                print("\n--- FULL RAW RESPONSE FROM GROK ---")
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
                print("\n" + "="*80)
                print("❌ GROK SIGNAL VALIDATION FAILED - RAW RESPONSE")
                print("="*80)
                print(f"Validation Error: {str(ve)}")
                print(f"Response length: {len(parsed_text) if parsed_text else 0} characters")
                print("\n--- FULL RAW RESPONSE FROM GROK ---")
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
            print("\n" + "="*80)
            print("❌ GROK API ERROR")
            print("="*80)
            print(f"Exception Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            print("="*80 + "\n")
            
            logger.error(f"Grok signal parsing error: {e}")
            return {
                "success": False,
                "data": None,
                "error": f"Error calling Grok API: {str(e)}",
                "raw_response": None
            }
    
    def predict_engagement(self, tweet_text: str, entities: Dict, 
                          base_score: float) -> Dict:
        """
        Use Grok to predict engagement for a tweet
        Analyzes similar content and provides prediction
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "Grok API not enabled",
                "predicted_engagement": int(base_score * 1000),  # Fallback calculation
                "confidence": 0.0
            }
        
        try:
            # Build prompt for Grok
            tickers_str = ", ".join(entities.get('tickers', [])[:5])
            keywords_str = ", ".join(entities.get('keywords', [])[:10])
            
            prompt = f"""Analyze this tweet and predict its engagement on X (Twitter):

Tweet: "{tweet_text}"

Context:
- Tickers mentioned: {tickers_str if tickers_str else 'None'}
- Keywords: {keywords_str if keywords_str else 'None'}
- Base engagement score: {base_score}/1.0

Based on current trends and similar content performance, provide:
1. Predicted total engagement (likes + retweets + replies)
2. Confidence level (0-100%)
3. Brief reasoning (1 sentence)
4. Optimal posting time (if relevant)

Format response as JSON:
{{
    "predicted_engagement": <number>,
    "confidence": <0-100>,
    "reasoning": "<sentence>",
    "optimal_time": "<time or 'now'>"
}}"""
            
            response = self._make_request(
                "chat/completions",
                {
                    "model": "grok-beta",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert in social media engagement prediction, specializing in financial and market content on X (Twitter)."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3
                }
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                
                # Try to parse JSON from response
                try:
                    # Extract JSON if wrapped in markdown code blocks
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content
                    
                    prediction = json.loads(json_str)
                    
                    return {
                        "success": True,
                        "predicted_engagement": prediction.get("predicted_engagement", int(base_score * 1000)),
                        "confidence": prediction.get("confidence", 70),
                        "reasoning": prediction.get("reasoning", "Based on similar content patterns"),
                        "optimal_time": prediction.get("optimal_time", "now")
                    }
                    
                except json.JSONDecodeError:
                    logger.warning("Could not parse Grok JSON response, using text analysis")
                    # Fallback: extract numbers from text
                    import re
                    engagement_match = re.search(r'(\d{1,6})\s*(?:likes|engagement|total)', content, re.IGNORECASE)
                    predicted = int(engagement_match.group(1)) if engagement_match else int(base_score * 1000)
                    
                    return {
                        "success": True,
                        "predicted_engagement": predicted,
                        "confidence": 60,
                        "reasoning": content[:100],
                        "optimal_time": "now"
                    }
            
            # Fallback if no valid response
            return {
                "success": False,
                "error": "Invalid response from Grok",
                "predicted_engagement": int(base_score * 1000),
                "confidence": 0
            }
            
        except Exception as e:
            logger.error(f"Grok engagement prediction error: {e}")
            return {
                "success": False,
                "error": str(e),
                "predicted_engagement": int(base_score * 1000),
                "confidence": 0
            }
    
    def analyze_trends(self, tickers: List[str], keywords: List[str]) -> Dict:
        """
        Use Grok to analyze current trends for given tickers/keywords
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "Grok API not enabled"
            }
        
        try:
            tickers_str = ", ".join(tickers[:5]) if tickers else "general market"
            keywords_str = ", ".join(keywords[:10]) if keywords else "none"
            
            prompt = f"""Analyze current X (Twitter) trends for:
- Tickers: {tickers_str}
- Keywords: {keywords_str}

Provide:
1. Are these topics currently trending? (Yes/No)
2. Sentiment (Bullish/Bearish/Neutral, with %)
3. Tweet volume estimate (High/Medium/Low)
4. Best time to post about this (Now/Later, with reason)

Format as JSON:
{{
    "is_trending": <true/false>,
    "sentiment": "<sentiment>",
    "sentiment_score": <-100 to 100>,
    "tweet_volume": "<High/Medium/Low>",
    "best_time": "<now/later>",
    "reasoning": "<brief reason>"
}}"""
            
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert in social media trend analysis for financial markets. Stock prices should be obtained from Alpha Vantage API. Work with the information provided in the prompt. Do not search X or web."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 400,
                    "temperature": 0.3
                }
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                
                # Try to parse JSON
                try:
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content
                    
                    trends = json.loads(json_str)
                    trends["success"] = True
                    return trends
                    
                except json.JSONDecodeError:
                    # Return raw text analysis
                    return {
                        "success": True,
                        "is_trending": "trend" in content.lower(),
                        "sentiment": "Neutral",
                        "sentiment_score": 0,
                        "tweet_volume": "Medium",
                        "best_time": "now",
                        "reasoning": content[:200],
                        "raw_response": content
                    }
            
            return {
                "success": False,
                "error": "No valid response from Grok"
            }
            
        except Exception as e:
            logger.error(f"Grok trend analysis error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def analyze_signal_complete(self, signal_text: str, signal_title: str, 
                                 signal_time: str) -> Dict:
        """
        Complete signal analysis using ONLY Grok model - no hard-coded logic
        Returns: classification, entities, score, breakdown, tweet
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "Grok API must be enabled for signal analysis"
            }
        
        try:
            # Extract tickers from signal text for Alpha Vantage lookup
            import re
            ticker_pattern = r'\$([A-Z]{1,5})\b|([A-Z]{1,5})\s+(?:stock|shares|options|call|put)'
            tickers_found = list(set(re.findall(ticker_pattern, signal_text, re.IGNORECASE)))
            # Flatten tuples and filter
            tickers = [t[0] or t[1] for t in tickers_found if t[0] or t[1]]
            tickers = [t.upper() for t in tickers if len(t) <= 5][:5]  # Limit to 5 tickers
            
            # Get stock prices from Alpha Vantage if available
            stock_prices_info = ""
            if self.alphavantage_api and self.alphavantage_api.is_enabled() and tickers:
                price_data_list = []
                for ticker in tickers:
                    price_data = self.alphavantage_api.get_stock_price(ticker)
                    if price_data.get("success"):
                        price_info = self.alphavantage_api.format_price_data_for_prompt(price_data)
                        price_data_list.append(price_info)
                    # Small delay to respect rate limits
                    import time
                    time.sleep(0.2)
                
                if price_data_list:
                    stock_prices_info = "\n\nCURRENT STOCK PRICES (from Alpha Vantage API):\n" + "\n".join(price_data_list)
            
            prompt = f"""You are an expert financial analyst and X (Twitter) content strategist.

SIGNAL TO ANALYZE:
Title: {signal_title}
Content: {signal_text}
Received: {signal_time}{stock_prices_info}

YOUR TASK - Complete in ONE comprehensive analysis:

STEP 1: ANALYZE THE SIGNAL
- Review the signal content and extract key information
- Use the stock prices provided above (from Alpha Vantage API) - use those exact prices
- Analyze the signal based on the content provided
- DO NOT search X or web - work with the information provided

STEP 2: CLASSIFY SIGNAL
- Type: 'market-news', 'company-news', 'economic-data', 'options-flow', or 'other'
- Source bot: 'uwhale-news-bot', 'x-news-bot', 'flow-bot', or 'unknown'

STEP 3: EXTRACT ENTITIES
- Stock tickers mentioned (e.g., NVDA, TSLA, SPY)
- Keywords (BREAKING, ALERT, RECORD, etc.)
- Financial numbers ($1.2B, 15%, etc.)
- Companies mentioned

STEP 4: CALCULATE ENGAGEMENT SCORE (0.0 to 1.0)
Based on:
- Ticker importance (high-priority tickers like NVDA, TSLA score higher)
- Drama/urgency level (BREAKING, ALERT, etc.)
- Financial magnitude (billions > millions)
- Timeliness (fresher = higher score)
- Market relevance (trending topics score higher)

Provide detailed breakdown with weights and reasoning.

STEP 5: GENERATE ONE TWEET AS PERSONAL OPINION
- Write as YOUR personal opinion/analysis, not as a news report
- Use the signal content and stock prices provided
- If information is incomplete, feel free to add context/analysis based on available data
- Personal, engaging, opinionated tone (like a trader sharing their take)
- Maximizes engagement potential
- NOT verbatim - rephrase and add your perspective
- 1-2 strategic emojis
- Under 280 characters

STEP 6: RECOMMENDATION
- POST_IMMEDIATELY (score 0.9+)
- POST_HIGH_TRAFFIC (score 0.7-0.89)
- CONSIDER_POSTING (score 0.5-0.69)
- PROBABLY_SKIP (score 0.3-0.49)
- REJECT (score <0.3)

Format response as JSON:
{{
    "classification": {{
        "signal_type": "<type>",
        "source_bot": "<bot>",
        "confidence": <0-100>
    }},
    "entities": {{
        "tickers": ["TICKER1", "TICKER2"],
        "keywords": ["KEYWORD1", "KEYWORD2"],
        "financial_numbers": ["$1.2B", "15%"],
        "companies": ["Company1"]
    }},
    "analysis": {{
        "key_facts": ["fact 1", "fact 2", "fact 3"],
        "current_sentiment": "bullish|bearish|neutral",
        "context_summary": "<summary of the signal analysis>"
    }},
    "engagement_score": {{
        "total_score": <0.0-1.0>,
        "breakdown": {{
            "ticker_impact": {{"score": <0-1>, "weight": 0.30, "reasoning": "<why>"}},
            "drama_urgency": {{"score": <0-1>, "weight": 0.25, "reasoning": "<why>"}},
            "financial_impact": {{"score": <0-1>, "weight": 0.20, "reasoning": "<why>"}},
            "timeliness": {{"score": <0-1>, "weight": 0.15, "reasoning": "<why>"}},
            "controversy": {{"score": <0-1>, "weight": 0.10, "reasoning": "<why>"}}
        }},
        "star_rating": "⭐⭐⭐⭐⭐"
    }},
    "tweet": {{
        "text": "<personal opinion tweet based on signal content>",
        "character_count": <number>,
        "predicted_engagement": <estimated likes+retweets+replies>,
        "relevant_facts_used": ["fact1", "fact2", "fact3"],
        "context_incorporated": "<specific signal elements used>",
        "style": "Personal opinion, engaging, opinionated",
        "engagement_reasoning": "<why this will perform well>"
    }},
    "recommendation": "<POST_IMMEDIATELY|POST_HIGH_TRAFFIC|CONSIDER_POSTING|PROBABLY_SKIP|REJECT>",
    "recommendation_reasoning": "<why this recommendation>"
}}"""
            
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an advanced AI analyst and trader. Stock prices are provided in the prompt from Alpha Vantage API - use those exact prices. You analyze signals comprehensively: classify, extract entities, score engagement potential, and generate tweets as YOUR personal opinion/analysis. Write like a trader sharing their take, not a news report. If information is incomplete, feel free to add context/analysis based on available data. Do not search X or web - work with the information provided."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.6
                }
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                
                try:
                    # Extract JSON
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content
                    
                    result = json.loads(json_str)
                    
                    # Validate required fields
                    if not result.get("tweet") or not result.get("tweet", {}).get("text"):
                        return {
                            "success": False,
                            "error": "Model did not generate tweet text",
                            "raw_response": content
                        }
                    
                    return {
                        "success": True,
                        "analysis": result,
                        "raw_response": content
                    }
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Could not parse Grok analysis response: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to parse model response: {e}",
                        "raw_response": content
                    }
            
            return {
                "success": False,
                "error": "No valid response from Grok model"
            }
            
        except Exception as e:
            logger.error(f"Grok complete analysis error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_context_aware_tweets(self, signal_text: str, entities: Dict, 
                                     signal_type: str) -> Dict:
        """
        Use Grok to generate ONE personal opinion tweet
        Creates a tweet written as personal opinion/analysis, adding context if needed
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "Grok API not enabled",
                "variants": []
            }
        
        try:
            # Build context from entities
            tickers = entities.get('tickers', [])[:5]
            tickers_str = ", ".join(tickers) or "None"
            keywords_str = ", ".join(entities.get('keywords', [])[:10]) or "None"
            numbers_str = ", ".join(entities.get('financial_numbers', [])[:5]) or "None"
            
            # Get stock prices from Alpha Vantage if available
            stock_prices_info = ""
            if self.alphavantage_api and self.alphavantage_api.is_enabled() and tickers:
                price_data_list = []
                for ticker in tickers:
                    price_data = self.alphavantage_api.get_stock_price(ticker)
                    if price_data.get("success"):
                        price_info = self.alphavantage_api.format_price_data_for_prompt(price_data)
                        price_data_list.append(price_info)
                    # Small delay to respect rate limits
                    import time
                    time.sleep(0.2)
                
                if price_data_list:
                    stock_prices_info = "\n\nCURRENT STOCK PRICES (from Alpha Vantage API):\n" + "\n".join(price_data_list)
            
            prompt = f"""You are an expert at creating high-engagement X (Twitter) posts about financial markets and news.

ORIGINAL SIGNAL:
{signal_text}

EXTRACTED CONTEXT:
- Tickers: {tickers_str}
- Keywords: {keywords_str}
- Financial Numbers: {numbers_str}
- Signal Type: {signal_type}{stock_prices_info}

CRITICAL TASK:
Step 1: ANALYZE THE SIGNAL
   - Review the signal content and extract key information
   - Use the stock prices provided above (from Alpha Vantage API) - use those exact prices
   - Identify key facts and data points from the signal
   - DO NOT search X or web - work with the information provided

Step 2: IDENTIFY 3-5 KEY FACTS from the signal
   - Market movements, key numbers, important details
   - Current sentiment based on signal content
   - Key data points mentioned

Step 3: CREATE ONE tweet as YOUR PERSONAL OPINION that:
   - Uses the signal content and stock prices provided
   - Write as YOUR personal take/analysis, not as a news report
   - If information is incomplete, feel free to add context/analysis based on available data
   - Personal, engaging, opinionated tone (like a trader sharing their perspective)
   - Rephrases the signal and adds your perspective (NOT verbatim copy)
   - Maximizes engagement potential
   - Under 280 characters
   - 1-2 relevant emojis

EXAMPLE GOOD OUTPUT:
Original: "NVIDIA announces $1.2B acquisition"
Stock price: NVDA: $270.97 (+2.50, +0.93%)
Generated tweet: "NVDA up 0.93% on $1.2B acquisition news. This looks like a smart move to consolidate their AI lead. Market seems to agree - watching for follow-through. 📈"

STYLE GUIDELINES:
✅ DO: Personal opinion, engaging, uses provided stock prices, add context if needed
❌ DON'T: Sound like a news report, overly promotional, excessive emojis, verbatim copy

Format response as JSON:
{{
    "tweet_text": "<personal opinion tweet based on signal content>",
    "relevant_facts": ["<fact from signal 1>", "<fact from signal 2>", "<fact from signal 3>"],
    "context_used": "<specific signal elements incorporated>",
    "engagement_factors": "<why this drives engagement>"
}}"""
            
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert trader and financial content creator. Stock prices are provided in the prompt from Alpha Vantage API - use those exact prices. Your tweets are YOUR personal opinions/analysis based on the signal content. Write like a trader sharing their take, not a news report. If information is incomplete, feel free to add context/analysis based on available data. You never copy verbatim - you synthesize the information into engaging personal opinion posts. Do not search X or web - work with the information provided."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.5  # Balanced for professional but engaging tone
                }
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                
                try:
                    # Extract JSON
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content
                    
                    result = json.loads(json_str)
                    
                    # Get the single tweet
                    tweet_text = result.get("tweet_text", "")
                    
                    if tweet_text and len(tweet_text) <= 280:
                        return {
                            "success": True,
                            "variants": [{
                                "type": "professional",
                                "text": tweet_text,
                                "style": "Professional, factual, engaging",
                                "context_used": result.get("context_used", ""),
                                "relevant_facts": result.get("relevant_facts", []),
                                "engagement_factors": result.get("engagement_factors", "")
                            }],
                            "raw_response": content
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Generated tweet is too long or empty",
                            "variants": [],
                            "raw_response": content
                        }
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse Grok JSON response: {e}")
                    # Fallback: try to extract tweet from text
                    import re
                    tweet_pattern = r'["\']([^"\']{20,280})["\']'
                    found_tweets = re.findall(tweet_pattern, content)
                    
                    if found_tweets:
                        # Use the first/longest tweet found
                        best_tweet = max(found_tweets, key=len) if len(found_tweets) > 1 else found_tweets[0]
                        return {
                            "success": True,
                            "variants": [{
                                "type": "professional",
                                "text": best_tweet[:280],
                                "style": "Professional, factual, engaging",
                                "context_used": "Extracted from response"
                            }],
                            "raw_response": content
                        }
                    
                    return {
                        "success": False,
                        "error": "Could not parse response or extract tweet",
                        "variants": [],
                        "raw_response": content
                    }
            
            return {
                "success": False,
                "error": "No valid response from Grok",
                "variants": []
            }
            
        except Exception as e:
            logger.error(f"Grok context-aware tweet generation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "variants": []
            }

    def search_similar_content(self, topic: str) -> Dict:
        """
        Use Grok to search for similar high-engagement content
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "Grok API not enabled"
            }
        
        try:
            prompt = f"""Analyze high-engagement tweet patterns for: {topic}

Based on general best practices for financial/market content, provide insights on:
1. What format/style typically gets the most engagement?
2. Optimal tweet length
3. Emoji usage patterns
4. Hashtag recommendations (if any)
5. Best posting time window

Format as JSON:
{{
    "best_format": "<format description>",
    "optimal_length": "<character range>",
    "emoji_count": "<recommended count>",
    "hashtags": ["<tag1>", "<tag2>"],
    "posting_window": "<time window>",
    "avg_engagement": <number>,
    "insights": "<key insight>"
}}"""
            
            response = self._make_request(
                "chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert at analyzing content patterns for financial and market topics. Provide general best practices based on your knowledge."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.4
                }
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                
                try:
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content
                    
                    insights = json.loads(json_str)
                    insights["success"] = True
                    return insights
                    
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "best_format": "Data-focused with bullet points",
                        "optimal_length": "150-200 characters",
                        "emoji_count": "2-3",
                        "hashtags": [],
                        "posting_window": "Market hours (9:30 AM - 4:00 PM ET)",
                        "avg_engagement": 1200,
                        "insights": content[:200],
                        "raw_response": content
                    }
            
            return {
                "success": False,
                "error": "No valid response from Grok"
            }
            
        except Exception as e:
            logger.error(f"Grok content search error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
