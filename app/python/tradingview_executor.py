"""
TradingView Executor Module
Handles automated execution of TradingView signals with incremental price adjustment.
Supports both SnapTrade and E*TRADE platforms.
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradingViewExecutor:
    def __init__(self, snaptrade_api, etrade_api, db):
        """
        Initialize TradingView Executor with API connections and database
        
        Args:
            snaptrade_api: SnapTrade API proxy instance (or None)
            etrade_api: EtradeAPI instance
            db: Database instance
        """
        self.snaptrade_api = snaptrade_api
        self.etrade_api = etrade_api
        self.db = db
        self.execution_log = []
    
    def get_config(self) -> Dict:
        """Get TradingView executor configuration from database"""
        return {
            "platform": self.db.get_setting("tradingview_platform", "snaptrade"),
            "position_size": float(self.db.get_setting("tradingview_position_size", "1.0")),
            "bid_delta": float(self.db.get_setting("tradingview_bid_delta", "0.01")),
            "ask_delta": float(self.db.get_setting("tradingview_ask_delta", "0.01")),
            "increments": float(self.db.get_setting("tradingview_increments", "0.01")),
            "enabled": self.db.get_setting("tradingview_executor_enabled", "true").lower() == "true",
        }
    
    def is_enabled(self) -> bool:
        """Check if TradingView executor is enabled"""
        return self.db.get_setting("tradingview_executor_enabled", "true").lower() == "true"
    
    def save_config(self, config: Dict) -> bool:
        """Save TradingView executor configuration to database"""
        try:
            self.db.save_setting("tradingview_platform", config.get("platform", "snaptrade"))
            self.db.save_setting("tradingview_position_size", str(config.get("position_size", 1.0)))
            self.db.save_setting("tradingview_bid_delta", str(config.get("bid_delta", 0.01)))
            self.db.save_setting("tradingview_ask_delta", str(config.get("ask_delta", 0.01)))
            self.db.save_setting("tradingview_increments", str(config.get("increments", 0.01)))
            return True
        except Exception as e:
            logger.error(f"Error saving TradingView executor config: {e}")
            return False
    
    def log_execution(self, signal_data: Dict, result: Dict, config: Dict, signal_id: int = None):
        """Log execution attempt to database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            execution_log_str = "\n".join(self.execution_log) if self.execution_log else ""
            
            # Extract PreviewId from execution log if present
            preview_id = None
            for line in self.execution_log:
                if "PreviewId:" in line:
                    try:
                        preview_id = line.split("PreviewId:")[1].strip()
                    except:
                        pass
            
            # Check if preview_id column exists
            cursor.execute("PRAGMA table_info(tradingview_execution_history)")
            columns = [col[1] for col in cursor.fetchall()]
            has_preview_id = 'preview_id' in columns
            
            if has_preview_id:
                cursor.execute("""
                    INSERT INTO tradingview_execution_history
                    (signal_id, platform, symbol, action, signal_price, position_size,
                     bid_delta, ask_delta, increments, status, order_id, filled_price,
                     quantity, attempts, preview_id, error_message, execution_log, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    config.get("platform"),
                    signal_data.get("symbol"),
                    signal_data.get("action"),
                    signal_data.get("price"),
                    config.get("position_size"),
                    config.get("bid_delta"),
                    config.get("ask_delta"),
                    config.get("increments"),
                    "success" if result.get("success") else "failed",
                    result.get("order_id"),
                    result.get("filled_price"),
                    result.get("quantity"),
                    result.get("attempts", 0),
                    preview_id,
                    result.get("error"),
                    execution_log_str,
                    now
                ))
            else:
                # Fallback without preview_id column
                cursor.execute("""
                    INSERT INTO tradingview_execution_history
                    (signal_id, platform, symbol, action, signal_price, position_size,
                     bid_delta, ask_delta, increments, status, order_id, filled_price,
                     quantity, attempts, error_message, execution_log, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    config.get("platform"),
                    signal_data.get("symbol"),
                    signal_data.get("action"),
                    signal_data.get("price"),
                    config.get("position_size"),
                    config.get("bid_delta"),
                    config.get("ask_delta"),
                    config.get("increments"),
                    "success" if result.get("success") else "failed",
                    result.get("order_id"),
                    result.get("filled_price"),
                    result.get("quantity"),
                    result.get("attempts", 0),
                    result.get("error"),
                    execution_log_str,
                    now
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging execution: {e}")
            import traceback
            traceback.print_exc()
    
    def get_execution_history(self, limit: int = 20) -> list:
        """Get execution history from database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Check if preview_id column exists
            cursor.execute("PRAGMA table_info(tradingview_execution_history)")
            columns = [col[1] for col in cursor.fetchall()]
            has_preview_id = 'preview_id' in columns
            
            if has_preview_id:
                cursor.execute("""
                    SELECT id, signal_id, platform, symbol, action, signal_price, position_size,
                           bid_delta, ask_delta, increments, status, order_id, filled_price,
                           quantity, attempts, preview_id, error_message, execution_log, created_at
                    FROM tradingview_execution_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT id, signal_id, platform, symbol, action, signal_price, position_size,
                           bid_delta, ask_delta, increments, status, order_id, filled_price,
                           quantity, attempts, error_message, execution_log, created_at
                    FROM tradingview_execution_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                if has_preview_id:
                    history.append({
                        "id": row[0],
                        "signal_id": row[1],
                        "platform": row[2],
                        "symbol": row[3],
                        "action": row[4],
                        "signal_price": row[5],
                        "position_size": row[6],
                        "bid_delta": row[7],
                        "ask_delta": row[8],
                        "increments": row[9],
                        "status": row[10],
                        "order_id": row[11],
                        "filled_price": row[12],
                        "quantity": row[13],
                        "attempts": row[14],
                        "preview_id": row[15],
                        "error_message": row[16],
                        "execution_log": row[17],
                        "created_at": row[18]
                    })
                else:
                    history.append({
                        "id": row[0],
                        "signal_id": row[1],
                        "platform": row[2],
                        "symbol": row[3],
                        "action": row[4],
                        "signal_price": row[5],
                        "position_size": row[6],
                        "bid_delta": row[7],
                        "ask_delta": row[8],
                        "increments": row[9],
                        "status": row[10],
                        "order_id": row[11],
                        "filled_price": row[12],
                        "quantity": row[13],
                        "attempts": row[14],
                        "error_message": row[15],
                        "execution_log": row[16],
                        "created_at": row[17]
                    })
            
            conn.close()
            return history
        except Exception as e:
            logger.error(f"Error getting execution history: {e}")
            return []
    
    def clear_execution_history(self) -> bool:
        """Clear all execution history"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tradingview_execution_history")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error clearing execution history: {e}")
            return False
    
    def execute_signal(self, signal_data: Dict, account_id: str = None, signal_id: int = None) -> Dict:
        """
        Execute a TradingView signal with incremental price adjustment
        
        Args:
            signal_data: Parsed TradingView signal with symbol, action, price
            account_id: Account ID (optional, will use default if not provided)
        
        Returns:
            Dict with execution results and log
        """
        self.execution_log = []
        
        # Check if executor is enabled
        if not self.is_enabled():
            self.execution_log.append("❌ TradingView Executor is DISABLED")
            result = {
                "success": False,
                "error": "TradingView Executor module is disabled",
                "log": self.execution_log,
                "attempts": 0
            }
            # Still log to database
            config = self.get_config()
            self.log_execution(signal_data, result, config, signal_id)
            return result
        
        # Get configuration
        config = self.get_config()
        platform = config["platform"].lower()
        position_size = config["position_size"]
        bid_delta = config["bid_delta"]
        ask_delta = config["ask_delta"]
        increments = config["increments"]
        
        symbol = signal_data.get("symbol", "").upper()
        action = signal_data.get("action", "").upper()
        signal_price = float(signal_data.get("price", 0))
        
        if not symbol or not action or signal_price <= 0:
            return {
                "success": False,
                "error": "Invalid signal data: symbol, action, and price are required",
                "log": self.execution_log
            }
        
        self.execution_log.append(f"🚀 TradingView Executor - {action} {position_size} {symbol} @ ${signal_price:.2f}")
        self.execution_log.append(f"📊 Platform: {platform.upper()}")
        self.execution_log.append(f"⚙️  Config: Position={position_size}, Bid Δ={bid_delta}, Ask Δ={ask_delta}, Increments={increments}")
        
        # Select API based on platform
        if platform == "etrade":
            if not self.etrade_api or not self.etrade_api.is_authenticated:
                err = "E*TRADE not authenticated" if self.etrade_api else "E*TRADE API not available"
                self.execution_log.append(f"❌ {err}")
                result = {"success": False, "error": err, "log": self.execution_log, "attempts": 0}
                # Log to database even if auth failed
                self.log_execution(signal_data, result, config, signal_id)
                return result
            api = self.etrade_api
        elif platform == "snaptrade":
            if not self.snaptrade_api:
                err = "SnapTrade not configured - please set up SnapTrade proxy first"
                self.execution_log.append(f"❌ {err}")
                result = {"success": False, "error": err, "log": self.execution_log, "attempts": 0}
                # Log to database even if auth failed
                self.log_execution(signal_data, result, config, signal_id)
                return result
            api = self.snaptrade_api
        else:
            self.execution_log.append(f"❌ Unsupported platform: {platform}")
            result = {"success": False, "error": f"Unsupported platform: {platform}", "log": self.execution_log, "attempts": 0}
            # Log to database
            self.log_execution(signal_data, result, config, signal_id)
            return result
        
        # Get account ID
        if not account_id:
            if platform == "snaptrade":
                # SnapTrade account IDs come from the proxy
                accounts_result = self.snaptrade_api.get_accounts() if self.snaptrade_api else {}
                if accounts_result.get("success"):
                    accounts = accounts_result.get("accounts", [])
                    if accounts and len(accounts) > 0:
                        account_id = accounts[0].get("id") or accounts[0].get("account_id")
        
        if not account_id:
            err = f"No account ID available for {platform}"
            self.execution_log.append(f"❌ {err}")
            result = {"success": False, "error": err, "log": self.execution_log, "attempts": 0}
            # Log to database
            self.log_execution(signal_data, result, config, signal_id)
            return result
        
        self.execution_log.append(f"📝 Account: {account_id}")
        
        # Execute based on action
        if action == "BUY":
            result = self._execute_buy(api, platform, account_id, symbol, signal_price,
                                    position_size, bid_delta, ask_delta, increments)
        elif action == "SELL":
            result = self._execute_sell(api, platform, account_id, symbol, signal_price,
                                     position_size, bid_delta, ask_delta, increments)
        else:
            result = {"success": False, "error": f"Unsupported action: {action}", "log": self.execution_log}
        
        # Log execution to database
        self.log_execution(signal_data, result, config, signal_id)
        
        return result
    
    def _execute_buy(self, api, platform: str, account_id: str, symbol: str,
                     signal_price: float, position_size: float, bid_delta: float,
                     ask_delta: float, increments: float) -> Dict:
        """
        Execute BUY order with incremental price adjustment
        Strategy: Start at (Price - Bid Delta), increment until (Price + Ask Delta)
        """
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("BUY ORDER EXECUTION")
        self.execution_log.append("="*60)
        
        start_price = signal_price - bid_delta
        end_price = signal_price + ask_delta
        current_price = start_price
        
        self.execution_log.append(f"💰 Price Range: ${start_price:.2f} → ${end_price:.2f}")
        self.execution_log.append(f"📈 Starting at: ${current_price:.2f}")
        
        attempt = 1
        max_attempts = int((end_price - start_price) / increments) + 1
        
        while current_price <= end_price and attempt <= max_attempts:
            self.execution_log.append(f"\n🔄 Attempt {attempt}: Limit Buy @ ${current_price:.2f}")
            
            order_result = self._place_limit_order(api, platform, account_id, symbol, "BUY",
                                                   current_price, position_size)
            
            # Check if order was filled (not just placed)
            if order_result.get("success") and order_result.get("order_status") == "EXECUTED":
                filled_price = order_result.get("filled_price", current_price)
                self.execution_log.append(f"✅ Order FILLED at ${filled_price:.2f}")
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "filled_price": filled_price,
                    "quantity": position_size,
                    "attempts": attempt,
                    "log": self.execution_log
                }
            else:
                error_msg = order_result.get('error', 'Unknown error')
                order_status = order_result.get('order_status', 'UNKNOWN')
                self.execution_log.append(f"❌ Not filled: {error_msg} (Status: {order_status})")
            
            current_price += increments
            current_price = round(current_price, 2)
            attempt += 1
        
        self.execution_log.append(f"\n❌ All {attempt-1} attempts failed")
        return {"success": False, "error": f"Failed after {attempt-1} attempts", "attempts": attempt - 1, "log": self.execution_log}
    
    def _execute_sell(self, api, platform: str, account_id: str, symbol: str,
                      signal_price: float, position_size: float, bid_delta: float,
                      ask_delta: float, increments: float) -> Dict:
        """
        Execute SELL order with incremental price adjustment
        Strategy: Start at (Price + Ask Delta), decrement until (Price - Bid Delta)
        """
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("SELL ORDER EXECUTION")
        self.execution_log.append("="*60)
        
        start_price = signal_price + ask_delta
        end_price = signal_price - bid_delta
        current_price = start_price
        
        self.execution_log.append(f"💰 Price Range: ${start_price:.2f} → ${end_price:.2f}")
        self.execution_log.append(f"📉 Starting at: ${current_price:.2f}")
        
        attempt = 1
        max_attempts = int((start_price - end_price) / increments) + 1
        
        while current_price >= end_price and attempt <= max_attempts:
            self.execution_log.append(f"\n🔄 Attempt {attempt}: Limit Sell @ ${current_price:.2f}")
            
            order_result = self._place_limit_order(api, platform, account_id, symbol, "SELL",
                                                   current_price, position_size)
            
            # Check if order was filled (not just placed)
            if order_result.get("success") and order_result.get("order_status") == "EXECUTED":
                filled_price = order_result.get("filled_price", current_price)
                self.execution_log.append(f"✅ Order FILLED at ${filled_price:.2f}")
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "filled_price": filled_price,
                    "quantity": position_size,
                    "attempts": attempt,
                    "log": self.execution_log
                }
            else:
                error_msg = order_result.get('error', 'Unknown error')
                order_status = order_result.get('order_status', 'UNKNOWN')
                self.execution_log.append(f"❌ Not filled: {error_msg} (Status: {order_status})")
            
            current_price -= increments
            current_price = round(current_price, 2)
            attempt += 1
        
        self.execution_log.append(f"\n❌ All {attempt-1} attempts failed")
        return {"success": False, "error": f"Failed after {attempt-1} attempts", "attempts": attempt - 1, "log": self.execution_log}
    
    def _check_order_fill_status(self, api, account_id: str, order_id: str, limit_price: float, quantity: float) -> Dict:
        """
        Check if an order was filled by querying order status with retry loop
        Returns: Dict with filled_price, filled_quantity, order_status
        """
        try:
            # Initial wait reduced to 0.25 seconds
            time.sleep(0.25)
            
            # Retry loop: check status up to 5 times
            max_retries = 5
            filled_price = limit_price
            filled_quantity = quantity
            
            for retry in range(1, max_retries + 1):
                self.execution_log.append(f"   🔄 Status check attempt {retry}/{max_retries}")
                
                # Check order status across all relevant statuses
                statuses_to_check = ["EXPIRED", "EXECUTED", "OPEN", "CANCELLED", "REJECTED"]
                order_found = False
                order_status = None
                order_detail = None
                
                for status in statuses_to_check:
                    status_result = api.get_orders(account_id, status=status)
                    if status_result.get("success"):
                        orders = status_result.get("orders", {})
                        order_list = orders.get("Order", [])
                        if not isinstance(order_list, list):
                            order_list = [order_list] if order_list else []
                        
                        for order in order_list:
                            if str(order.get("orderId")) == str(order_id):
                                order_found = True
                                order_details = order.get("OrderDetail", [])
                                if not isinstance(order_details, list):
                                    order_details = [order_details] if order_details else []
                                
                                if order_details:
                                    order_detail = order_details[0]
                                    order_status = order_detail.get("status", "").upper()
                                break
                        
                        if order_found:
                            break
                
                if not order_found:
                    # Order not found yet, wait and retry
                    if retry < max_retries:
                        self.execution_log.append(f"   ⏳ Order not found yet, waiting...")
                        time.sleep(0.25)
                        continue
                    else:
                        self.execution_log.append(f"   ❌ Cannot confirm order status after {max_retries} attempts")
                        return {
                            "filled": False,
                            "order_status": "UNKNOWN",
                            "error": "Cannot confirm order status"
                        }
                
                # Order found - check status
                if order_status == "EXPIRED":
                    self.execution_log.append(f"   ⏰ Order EXPIRED")
                    return {
                        "filled": False,
                        "order_status": "EXPIRED"
                    }
                
                elif order_status == "EXECUTED":
                    # Extract filled price and quantity
                    if order_detail:
                        instruments = order_detail.get("Instrument", [])
                        if instruments and not isinstance(instruments, list):
                            instruments = [instruments]
                        
                        if instruments:
                            inst = instruments[0]
                            filled_price = inst.get("averageExecutionPrice") or inst.get("price") or inst.get("limitPrice") or limit_price
                            filled_quantity = inst.get("filledQuantity") or inst.get("quantity") or quantity
                    
                    self.execution_log.append(f"   ✅ Order FILLED - Status: EXECUTED")
                    return {
                        "filled": True,
                        "filled_price": float(filled_price),
                        "filled_quantity": float(filled_quantity),
                        "order_status": "EXECUTED"
                    }
                
                elif order_status == "CANCELLED":
                    self.execution_log.append(f"   ⚠️ Order CANCELLED")
                    return {
                        "filled": False,
                        "order_status": "CANCELLED"
                    }
                
                elif order_status == "REJECTED":
                    self.execution_log.append(f"   ❌ Order REJECTED")
                    return {
                        "filled": False,
                        "order_status": "REJECTED"
                    }
                
                else:
                    # Order found but status is not EXPIRED, EXECUTED, CANCELLED, or REJECTED
                    # Check again after a short wait
                    if retry < max_retries:
                        self.execution_log.append(f"   ⏳ Order Status: {order_status} (checking again...)")
                        time.sleep(0.25)
                        continue
                    else:
                        self.execution_log.append(f"   ❌ Cannot confirm order status after {max_retries} attempts (Status: {order_status})")
                        return {
                            "filled": False,
                            "order_status": order_status,
                            "error": f"Cannot confirm order status (Status: {order_status})"
                        }
            
            # Should not reach here, but just in case
            self.execution_log.append(f"   ❌ Cannot confirm order status after {max_retries} attempts")
            return {
                "filled": False,
                "order_status": "UNKNOWN",
                "error": "Cannot confirm order status"
            }
        except Exception as e:
            logger.error(f"Error checking order fill status: {e}")
            self.execution_log.append(f"   ❌ Exception checking order status: {str(e)}")
            return {
                "filled": False,
                "order_status": "ERROR",
                "error": str(e)
            }
    
    def _place_limit_order(self, api, platform: str, account_id: str, symbol: str,
                          action: str, limit_price: float, quantity: float) -> Dict:
        """Place a limit order with Fill-or-Kill - Preview first, then Place"""
        try:
            if platform == "snaptrade":
                # SnapTrade equity order
                self.execution_log.append(f"   📤 Placing order (SnapTrade)...")
                order_data = {
                    "account_id": account_id,
                    "symbol": symbol,
                    "action": action,
                    "order_type": "LMT",
                    "quantity": quantity,
                    "price": limit_price,
                    "time_in_force": "IOC",  # Immediate or Cancel (closest to FOK)
                }
                
                result = api.place_order(account_id, order_data)
                
                if result.get("success"):
                    self.execution_log.append(f"   ✅ Order placed successfully")
                else:
                    self.execution_log.append(f"   ❌ Place failed: {result.get('error', 'Unknown')}")
                
                return result
            else:
                self.execution_log.append(f"   ❌ Unsupported platform: {platform}")
                return {"success": False, "error": f"Unsupported platform: {platform}"}
                
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return {"success": False, "error": f"Exception: {str(e)}"}

