"""
Webull API integration module for TradeIQ.
Uses the official webull-openapi-python-sdk.
"""

import os
import sys
import logging
import uuid
from typing import Dict, Optional, List

# Add webull venv311 to path if webull is not available in current venv
try:
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    from webull.data.data_client import DataClient
    from webull.data.common.category import Category
except ImportError:
    # Try to use webull from the separate venv311
    webull_venv_path = '/Users/superadmin/Desktop/webull/venv311/lib/python3.11/site-packages'
    if os.path.exists(webull_venv_path) and webull_venv_path not in sys.path:
        sys.path.insert(0, webull_venv_path)
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    from webull.data.data_client import DataClient
    from webull.data.common.category import Category

# Configure logging
logger = logging.getLogger(__name__)


class WebullAPI:
    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        db: Optional[object] = None,
    ):
        """
        Initialize Webull API connection.
        """
        # Load from database if available
        if db:
            saved_key = db.get_setting("webull_app_key", "")
            saved_secret = db.get_setting("webull_app_secret", "")
            
            if saved_key:
                app_key = app_key or saved_key
            if saved_secret:
                app_secret = app_secret or saved_secret
        
        self.app_key = app_key or os.getenv("WEBULL_APP_KEY")
        self.app_secret = app_secret or os.getenv("WEBULL_APP_SECRET")
        self.db = db
        
        self.api_client = None
        self.trade_client = None
        self.data_client = None
        self.accounts = []
        self.default_account_id = None
        self.is_authenticated = False
        
        if self.app_key and self.app_secret:
            try:
                self._initialize_client()
                # Note: is_authenticated is set to True, but actual auth happens on first API call
                # A 401 error on API calls means credentials are invalid
            except Exception as e:
                logger.error(f"Failed to initialize Webull client: {e}")
                self.is_authenticated = False
    
    def _initialize_client(self):
        """Initialize Webull API client"""
        if not self.app_key or not self.app_secret:
            raise ValueError("App key and secret are required")
        
        self.api_client = ApiClient(self.app_key, self.app_secret, "us")
        self.trade_client = TradeClient(self.api_client)
        self.data_client = DataClient(self.api_client)
        self.is_authenticated = True
        logger.info("Webull API client initialized")
    
    def save_config(self, app_key: str, app_secret: str) -> Dict:
        """Save API credentials to database"""
        try:
            if self.db:
                self.db.save_setting("webull_app_key", app_key)
                self.db.save_setting("webull_app_secret", app_secret)
            
            self.app_key = app_key
            self.app_secret = app_secret
            self._initialize_client()
            
            return {"success": True, "message": "Configuration saved successfully"}
        except Exception as e:
            logger.error(f"Error saving Webull config: {e}")
            return {"success": False, "error": str(e)}
    
    def get_accounts(self) -> Dict:
        """Get list of accounts"""
        try:
            if not self.trade_client:
                # Try to initialize if we have credentials
                if self.app_key and self.app_secret:
                    try:
                        self._initialize_client()
                    except Exception as e:
                        return {"success": False, "error": f"Failed to initialize client: {str(e)}"}
                else:
                    return {"success": False, "error": "Not authenticated. Please save API keys first."}
            
            response = self.trade_client.account_v2.get_account_list()
            
            if response.status_code == 200:
                accounts_data = response.json()
                self.accounts = accounts_data if isinstance(accounts_data, list) else []
                
                # Set default account if none selected
                if self.accounts and not self.default_account_id:
                    self.default_account_id = self.accounts[0].get('account_id')
                
                self.is_authenticated = True
                return {
                    "success": True,
                    "accounts": self.accounts,
                    "default_account_id": self.default_account_id
                }
            elif response.status_code == 401:
                self.is_authenticated = False
                return {
                    "success": False,
                    "error": "Authentication failed. Please check your API keys (App Key and App Secret). The keys may be invalid or expired."
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get accounts: {response.status_code} - {response.text}"
                }
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            error_msg = str(e)
            if "401" in error_msg or "UNAUTHORIZED" in error_msg:
                self.is_authenticated = False
                return {"success": False, "error": "Authentication failed. Please check your API keys (App Key and App Secret)."}
            return {"success": False, "error": error_msg}
    
    def set_default_account(self, account_id: str):
        """Set the default account ID"""
        self.default_account_id = account_id
        if self.db:
            self.db.save_setting("webull_default_account_id", account_id)
    
    def get_account_balance(self, account_id: str) -> Dict:
        """Get account balance"""
        try:
            if not self.trade_client:
                return {"success": False, "error": "Not authenticated"}
            
            response = self.trade_client.account_v2.get_account_balance(account_id)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "balance": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get balance: {response.status_code} - {response.text}"
                }
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {"success": False, "error": str(e)}
    
    def get_order_status(self, account_id: str, client_order_id: str) -> Dict:
        """
        Get the status of an order by client_order_id.
        
        Webull Order Statuses:
        - SUBMITTED (1): Order placed, waiting to be filled
        - CANCELLED (2): Order was cancelled
        - FAILED (3): Order failed
        - FILLED (4): Order completely filled
        - PARTIAL_FILLED (5): Order partially filled
        
        Returns:
            Dict with 'success', 'status', 'filled_quantity', 'order_id', 'raw_response'
        """
        try:
            if not self.trade_client:
                return {"success": False, "error": "Not authenticated"}
            
            response = self.trade_client.order_v2.get_order_detail(
                account_id=account_id,
                client_order_id=client_order_id
            )
            
            if response.status_code == 200:
                order_data = response.json()
                
                # Log raw response for debugging
                logger.info(f"Order status raw response: {order_data}")
                
                # The response can be nested - status might be in orders[0]['status']
                # First, try to find the order details
                order_detail = order_data
                
                # Check if response has nested 'orders' array (option orders)
                if 'orders' in order_data and isinstance(order_data['orders'], list) and len(order_data['orders']) > 0:
                    order_detail = order_data['orders'][0]
                
                # Try multiple possible field names for status
                status = None
                for key in ['status', 'order_status', 'orderStatus', 'Status']:
                    if key in order_detail and order_detail[key]:
                        status = str(order_detail[key]).upper()
                        break
                
                # Also check top-level if not found in order_detail
                if not status:
                    for key in ['status', 'order_status', 'orderStatus', 'Status']:
                        if key in order_data and order_data[key]:
                            status = str(order_data[key]).upper()
                            break
                
                # Try multiple possible field names for filled quantity
                filled_qty = 0
                for key in ['filled_quantity', 'filledQuantity', 'filled_qty', 'filledQty']:
                    if key in order_detail and order_detail[key]:
                        try:
                            filled_qty = int(float(order_detail[key]))
                        except:
                            pass
                        break
                
                # Also check top-level if not found
                if filled_qty == 0:
                    for key in ['filled_quantity', 'filledQuantity', 'filled_qty', 'filledQty']:
                        if key in order_data and order_data[key]:
                            try:
                                filled_qty = int(float(order_data[key]))
                            except:
                                pass
                            break
                
                # Get order ID - try order_detail first, then top level
                order_id = None
                for key in ['order_id', 'orderId', 'id', 'combo_order_id']:
                    if key in order_detail and order_detail[key]:
                        order_id = str(order_detail[key])
                        break
                
                if not order_id:
                    for key in ['order_id', 'orderId', 'id', 'combo_order_id']:
                        if key in order_data and order_data[key]:
                            order_id = str(order_data[key])
                            break
                
                return {
                    "success": True,
                    "status": status,  # Can be None if not found
                    "filled_quantity": filled_qty,
                    "order_id": order_id,
                    "raw_response": order_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get order status: {response.status_code} - {response.text}"
                }
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            import traceback
            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    
    def cancel_option_order(self, account_id: str, client_order_id: str) -> Dict:
        """
        Cancel an option order by client_order_id.
        
        Returns:
            Dict with 'success' and optional 'error'
        """
        try:
            if not self.trade_client:
                return {"success": False, "error": "Not authenticated"}
            
            response = self.trade_client.order_v2.cancel_option(
                account_id=account_id,
                client_order_id=client_order_id
            )
            
            if response.status_code == 200:
                return {"success": True, "message": "Order cancelled successfully"}
            else:
                error_text = response.text
                # Some error codes mean the order is already filled/cancelled
                if "ALREADY_FILLED" in error_text or "ALREADY_CANCELLED" in error_text:
                    return {"success": True, "message": "Order already filled or cancelled"}
                return {
                    "success": False,
                    "error": f"Failed to cancel order: {response.status_code} - {error_text}"
                }
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"success": False, "error": str(e)}
    
    def place_option_order(
        self,
        account_id: str,
        symbol: str,
        strike_price: str,
        init_exp_date: str,
        option_type: str,
        side: str,
        quantity: int,
        order_type: str = "LIMIT",
        limit_price: str = None,
        time_in_force: str = "GTC"
    ) -> Dict:
        """Place an options order"""
        try:
            if not self.trade_client:
                return {"success": False, "error": "Not authenticated"}
            
            # Generate unique client order ID
            client_order_id = uuid.uuid4().hex
            
            # Build order structure
            new_orders = [
                {
                    "client_order_id": client_order_id,
                    "combo_type": "NORMAL",
                    "order_type": order_type,
                    "quantity": str(quantity),
                    "option_strategy": "SINGLE",
                    "side": side,
                    "time_in_force": time_in_force,
                    "entrust_type": "QTY",
                    "orders": [
                        {
                            "side": side,
                            "quantity": str(quantity),
                            "symbol": symbol,
                            "strike_price": str(strike_price),
                            "init_exp_date": init_exp_date,
                            "instrument_type": "OPTION",
                            "option_type": option_type.upper(),
                            "market": "US"
                        }
                    ]
                }
            ]
            
            # Add limit_price if provided
            if limit_price and order_type == "LIMIT":
                new_orders[0]["limit_price"] = str(limit_price)
            
            # Preview first
            preview_response = self.trade_client.order_v2.preview_option(
                account_id=account_id,
                new_orders=new_orders
            )
            
            if preview_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Preview failed: {preview_response.status_code} - {preview_response.text}"
                }
            
            preview_data = preview_response.json()
            
            # Place order
            place_response = self.trade_client.order_v2.place_option(
                account_id=account_id,
                new_orders=new_orders
            )
            
            if place_response.status_code == 200:
                return {
                    "success": True,
                    "order": place_response.json(),
                    "preview": preview_data,
                    "client_order_id": client_order_id
                }
            else:
                # Check if it's a trading hours restriction
                error_text = place_response.text
                if "OAUTH_OPENAPI_OPTION_ONLY_SUPPORT_MARKET_IN_CORE_TIME" in error_text or "417" in error_text:
                    return {
                        "success": False,
                        "error": "Trading hours restriction: Orders can only be placed during market hours (9:30 AM - 4:00 PM ET)",
                        "preview": preview_data,
                        "order_valid": True
                    }
                
                return {
                    "success": False,
                    "error": f"Failed to place order: {place_response.status_code} - {place_response.text}",
                    "preview": preview_data
                }
        except Exception as e:
            logger.error(f"Error placing option order: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def place_equity_order(
        self,
        account_id: str,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "LIMIT",
        limit_price: str = None,
        time_in_force: str = "GTC",
        extended_hours_trading: bool = False
    ) -> Dict:
        """
        Place an equity (stock) order.
        
        Args:
            extended_hours_trading: If True, order can execute during pre-market (4 AM - 9:30 AM ET)
                                   and after-hours (4 PM - 8 PM ET). Only LIMIT orders allowed.
        """
        try:
            if not self.trade_client:
                return {"success": False, "error": "Not authenticated"}
            
            # For equity orders, get instrument_id using the proper SDK method
            instrument_id = None
            
            try:
                if not self.data_client:
                    self.data_client = DataClient(self.api_client)
                
                # Use the proper SDK method: DataClient.instrument.get_instrument()
                response = self.data_client.instrument.get_instrument(
                    symbols=symbol,
                    category=Category.US_STOCK.name
                )
                
                if response.status_code == 200:
                    instruments = response.json()
                    if instruments and len(instruments) > 0:
                        # Handle both list and dict responses
                        if isinstance(instruments, list):
                            instrument_id = instruments[0].get('instrument_id') or instruments[0].get('instrumentId')
                        elif isinstance(instruments, dict):
                            instrument_id = instruments.get('instrument_id') or instruments.get('instrumentId')
                
                if not instrument_id:
                    logger.warning(f"Could not find instrument_id for {symbol} in response: {instruments}")
            except Exception as e:
                logger.error(f"Error getting instrument_id: {e}")
                return {
                    "success": False,
                    "error": f"Failed to get instrument_id for {symbol}: {str(e)}"
                }
            
            if not instrument_id:
                return {
                    "success": False,
                    "error": f"Could not find instrument_id for symbol {symbol}. Please verify the symbol is correct."
                }
            
            # Generate unique client order ID
            client_order_id = uuid.uuid4().hex
            
            # Extended hours requires LIMIT orders only
            if extended_hours_trading and order_type != "LIMIT":
                return {
                    "success": False,
                    "error": "Extended hours trading only supports LIMIT orders. Please change order type to LIMIT."
                }
            
            # Use the simple SDK method: trade_client.order.place_order()
            # This method takes individual parameters directly
            place_response = self.trade_client.order.place_order(
                account_id=account_id,
                qty=str(quantity),
                instrument_id=str(instrument_id),
                side=side,
                client_order_id=client_order_id,
                order_type=order_type,
                extended_hours_trading=extended_hours_trading,  # True for pre-market/after-hours
                tif=time_in_force,
                limit_price=str(limit_price) if limit_price else None
            )
            
            if place_response.status_code == 200:
                return {
                    "success": True,
                    "order": place_response.json(),
                    "client_order_id": client_order_id
                }
            else:
                error_text = place_response.text
                # Check if it's a trading hours restriction
                if "ONLY_SUPPORT_MARKET_IN_CORE_TIME" in error_text or "ORDER_BEFORE_BROKER_TRADING_TIME" in error_text:
                    return {
                        "success": False,
                        "error": "Trading hours restriction: Webull requires orders to be submitted during market hours (9:30 AM - 4:00 PM ET). Your order structure is valid and will work during trading hours.",
                        "order_valid": True,
                        "client_order_id": client_order_id
                    }
                return {
                    "success": False,
                    "error": f"Failed to place order: {place_response.status_code} - {error_text}"
                }
        except Exception as e:
            logger.error(f"Error placing equity order: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
