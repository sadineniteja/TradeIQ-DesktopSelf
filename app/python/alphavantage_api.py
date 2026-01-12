"""
Alpha Vantage API Integration - Real-time stock price data
"""

import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AlphaVantageAPI:
    """Interface for Alpha Vantage Stock Market Data API"""
    
    def __init__(self, db=None):
        """Initialize Alpha Vantage API client"""
        self.db = db
        self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"
        self.is_configured = False
        
        # Load configuration if database available
        if self.db:
            self._load_config()
    
    def _load_config(self):
        """Load Alpha Vantage API configuration from database"""
        try:
            self.api_key = self.db.get_setting("alphavantage_api_key", "")
            self.is_configured = bool(self.api_key)
            
            if self.is_configured:
                logger.info("[OK] Alpha Vantage API configured")
            else:
                logger.info("[WARN] Alpha Vantage API not configured")
                
        except Exception as e:
            logger.error(f"Error loading Alpha Vantage API config: {e}")
            self.is_configured = False
    
    def save_config(self, api_key: str = None) -> bool:
        """
        Save Alpha Vantage API configuration
        """
        try:
            if not api_key or not api_key.strip():
                return False
            
            # Save to database
            if self.db:
                self.db.save_setting("alphavantage_api_key", api_key.strip())
            
            # Update instance
            self.api_key = api_key.strip()
            self.is_configured = True
            
            logger.info("[OK] Alpha Vantage API configuration saved")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Alpha Vantage API config: {e}")
            return False
    
    def get_config(self) -> Dict:
        """Get current Alpha Vantage API configuration (masked)"""
        return {
            "api_key": "***" if self.api_key else "",
            "is_configured": self.is_configured
        }
    
    def is_enabled(self) -> bool:
        """Check if Alpha Vantage API is enabled"""
        return self.is_configured
    
    def test_connection(self) -> Dict:
        """
        Test Alpha Vantage API connectivity
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Alpha Vantage API not configured. Please add your API key."
            }
        
        try:
            # Test with a well-known symbol (AAPL)
            result = self.get_stock_price("AAPL")
            
            if result.get("success"):
                return {
                    "success": True,
                    "message": "Alpha Vantage API connection successful!",
                    "test_symbol": "AAPL",
                    "test_price": result.get("price")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to retrieve test data")
                }
                
        except Exception as e:
            logger.error(f"Alpha Vantage API connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_stock_price(self, symbol: str) -> Dict:
        """
        Get real-time stock price for a symbol
        
        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            
        Returns:
            Dict with success status, price, and other quote data
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Alpha Vantage API not configured"
            }
        
        if not symbol or not symbol.strip():
            return {
                "success": False,
                "error": "Symbol cannot be empty"
            }
        
        symbol = symbol.strip().upper()
        
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API request failed with status code {response.status_code}"
                }
            
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data:
                return {
                    "success": False,
                    "error": data["Error Message"]
                }
            
            if "Note" in data:
                return {
                    "success": False,
                    "error": "API call frequency limit reached. Please wait a moment."
                }
            
            # Extract quote data
            if "Global Quote" in data and data["Global Quote"]:
                quote = data["Global Quote"]
                
                return {
                    "success": True,
                    "symbol": quote.get("01. symbol", symbol),
                    "price": float(quote.get("05. price", 0)),
                    "open": float(quote.get("02. open", 0)),
                    "high": float(quote.get("03. high", 0)),
                    "low": float(quote.get("04. low", 0)),
                    "volume": int(quote.get("06. volume", 0)),
                    "latest_trading_day": quote.get("07. latest trading day", ""),
                    "previous_close": float(quote.get("08. previous close", 0)),
                    "change": float(quote.get("09. change", 0)),
                    "change_percent": quote.get("10. change percent", "0%")
                }
            else:
                return {
                    "success": False,
                    "error": f"No quote data found for symbol {symbol}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout - Alpha Vantage API did not respond in time"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Alpha Vantage API request error: {e}")
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing Alpha Vantage response: {e}")
            return {
                "success": False,
                "error": f"Error parsing API response: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error getting stock price: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_multiple_stock_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get stock prices for multiple symbols
        
        Args:
            symbols: List of stock ticker symbols
            
        Returns:
            Dict mapping symbol to price data
        """
        results = {}
        
        for symbol in symbols:
            if symbol and symbol.strip():
                results[symbol.upper()] = self.get_stock_price(symbol)
            # Add small delay to respect rate limits (free tier: 5 calls/min, 500/day)
            import time
            time.sleep(0.2)  # 200ms delay between calls
        
        return results
    
    def format_price_data_for_prompt(self, price_data: Dict) -> str:
        """
        Format stock price data for inclusion in Grok prompts
        
        Args:
            price_data: Result from get_stock_price()
            
        Returns:
            Formatted string with price information
        """
        if not price_data.get("success"):
            return f"Price data unavailable: {price_data.get('error', 'Unknown error')}"
        
        symbol = price_data.get("symbol", "")
        price = price_data.get("price", 0)
        change = price_data.get("change", 0)
        change_percent = price_data.get("change_percent", "0%")
        volume = price_data.get("volume", 0)
        
        return f"{symbol}: ${price:.2f} ({change:+.2f}, {change_percent}) | Volume: {volume:,}"

