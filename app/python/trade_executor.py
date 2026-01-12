"""
Smart Trade Executor Module
Handles intelligent order execution with validation, date inference, and incremental filling
Only processes BUY orders with 6-step sequential validation and execution
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import time

logger = logging.getLogger(__name__)


class TradeExecutor:
    def __init__(self, snaptrade_api, etrade_api, db):
        """
        Initialize Trade Executor with API connections and database
        
        Args:
            snaptrade_api: SnapTrade API proxy instance (or None)
            etrade_api: EtradeAPI instance
            db: Database instance
        """
        self.snaptrade_api = snaptrade_api
        self.etrade_api = etrade_api
        self.db = db
        self.execution_log = []
    
    def execute_trade(self, signal_data: Dict, platform: str = "snaptrade") -> Dict:
        """
        Main execution method that processes all steps sequentially.
        Only processes BUY orders.
        
        Steps:
        1. Validate required fields
        2. Validate/infer date with year
        3. Find nearest options chain (if no date)
        4. Verify strike price exists
        5. Calculate position size
        6. Fill order with incremental pricing
        
        Args:
            signal_data: Parsed signal with required fields
            platform: 'snaptrade'
        
        Returns:
            Dict with execution results and detailed log
        """
        self.execution_log = []
        
        # Check if executor is enabled
        enabled = self.db.get_setting("smart_executor_enabled", "true").lower() == "true"
        if not enabled:
            self.execution_log.append("❌ Smart Executor is DISABLED")
            execution_id = self.db.create_execution_attempt(signal_data, platform)
            return self._fail(
                "Smart Executor module is disabled",
                step=0,
                execution_id=execution_id
            )
        
        # Log start
        self.execution_log.append(f"🚀 Starting Smart Trade Executor on {platform.upper()}")
        self.execution_log.append(f"⏰ Timestamp: {datetime.now().isoformat()}")
        
        # Create execution attempt record
        execution_id = self.db.create_execution_attempt(signal_data, platform)
        
        # Select API
        api = self.snaptrade_api
        
        # Check if BUY order
        direction = signal_data.get("direction", "").upper()
        if direction != "BUY":
            return self._fail(
                f"Only BUY orders are supported. Got: {direction}",
                step=0,
                execution_id=execution_id
            )
        
        self.execution_log.append(f"✅ Direction verified: {direction}")
        
        # ==================== STEP 1: Validate Required Fields ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 1: Validating Required Fields")
        self.execution_log.append("="*60)
        
        step1_start = time.time()
        step1_result = self._step1_validate_required_fields(signal_data)
        step1_duration = time.time() - step1_start
        self.execution_log.append(f"⏱️ Step 1 completed in {step1_duration:.2f}s")
        
        if not step1_result["success"]:
            return self._fail(step1_result["error"], step=1, execution_id=execution_id)
        
        # ==================== STEP 2: Validate/Infer Date ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 2: Validating and Inferring Date")
        self.execution_log.append("="*60)
        
        step2_start = time.time()
        step2_result = self._step2_validate_and_infer_date(signal_data)
        step2_duration = time.time() - step2_start
        self.execution_log.append(f"⏱️ Step 2 completed in {step2_duration:.2f}s")
        
        if not step2_result["success"]:
            # No valid date, proceed to step 3
            self.execution_log.append("⚠️  No valid date provided, proceeding to Step 3...")
            
            # ==================== STEP 3: Find Nearest Options Chain ====================
            self.execution_log.append("\n" + "="*60)
            self.execution_log.append("STEP 3: Finding Nearest Options Chain")
            self.execution_log.append("="*60)
            
            step3_start = time.time()
            step3_result = self._step3_find_nearest_options_chain(
                signal_data["ticker"],
                signal_data["option_type"],
                api,
                platform
            )
            step3_duration = time.time() - step3_start
            self.execution_log.append(f"⏱️ Step 3 completed in {step3_duration:.2f}s")
            
            if not step3_result["success"]:
                return self._fail(step3_result["error"], step=3, execution_id=execution_id)
            
            final_date = step3_result["date"]
        else:
            final_date = step2_result["date"]
            self.execution_log.append(f"✅ STEP 2 Complete: Using date {final_date}")
        
        # ==================== STEP 4: Verify Strike Price ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 4: Verifying Strike Price Exists")
        self.execution_log.append("="*60)
        
        step4_start = time.time()
        step4_result = self._step4_verify_strike_price(
            signal_data["ticker"],
            final_date,
            signal_data["strike_price"],
            signal_data["option_type"],
            api,
            platform
        )
        step4_duration = time.time() - step4_start
        self.execution_log.append(f"⏱️ Step 4 completed in {step4_duration:.2f}s")
        
        if not step4_result["success"]:
            return self._fail(step4_result["error"], step=4, execution_id=execution_id)
        
        # ==================== STEP 5: Calculate Position Size ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 5: Calculating Position Size")
        self.execution_log.append("="*60)
        
        step5_start = time.time()
        signal_title = signal_data.get("signal_title", "") or signal_data.get("channel_name", "") or ""
        step5_result = self._step5_calculate_position_size(
            signal_data["purchase_price"],
            signal_data.get("input_position_size", 2),
            signal_title=signal_title
        )
        step5_duration = time.time() - step5_start
        self.execution_log.append(f"⏱️ Step 5 completed in {step5_duration:.2f}s")
        
        if not step5_result["success"]:
            return self._fail(step5_result["error"], step=5, execution_id=execution_id)
        
        # ==================== STEP 6: Fill Order with Incremental Pricing ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 6: Attempting to Fill Order")
        self.execution_log.append("="*60)
        
        step6_start = time.time()
        step6_result = self._step6_fill_order_incremental(
            api,
            platform,
            signal_data["ticker"],
            final_date,
            signal_data["option_type"],
            signal_data["strike_price"],
            signal_data["purchase_price"],
            step5_result["position_size"]
        )
        step6_duration = time.time() - step6_start
        self.execution_log.append(f"⏱️ Step 6 completed in {step6_duration:.2f}s")
        
        if not step6_result["success"]:
            return self._fail(step6_result["error"], step=6, execution_id=execution_id)
        
        # ==================== STEP 7: Place Take-Profit Sell Order ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("STEP 7: Placing Take-Profit Sell Order")
        self.execution_log.append("="*60)
        
        step7_start = time.time()
        step7_result = self._step7_place_take_profit_order(
            signal_data["ticker"],
            final_date,
            signal_data["option_type"],
            signal_data["strike_price"],
            step6_result["filled_price"],
            step5_result["position_size"],
            signal_title=signal_title
        )
        step7_duration = time.time() - step7_start
        self.execution_log.append(f"⏱️ Step 7 completed in {step7_duration:.2f}s")
        
        # Step 7 failure is not fatal - we still bought successfully
        if not step7_result["success"]:
            self.execution_log.append(f"⚠️ Take-profit order failed: {step7_result.get('error')}")
            self.execution_log.append("⚠️ BUY order was successful, but sell order needs manual placement")
        
        # ==================== SUCCESS ====================
        self.execution_log.append("\n" + "="*60)
        self.execution_log.append("🎉 EXECUTION SUCCESSFUL!")
        self.execution_log.append("="*60)
        
        return self._success(
            execution_id=execution_id,
            order_id=step6_result["order_id"],
            filled_price=step6_result["filled_price"],
            position_size=step5_result["position_size"],
            expiration_date=final_date,
            fill_attempts=step6_result.get("attempts", 1),
            sell_order_id=step7_result.get("order_id"),
            sell_quantity=step7_result.get("sell_quantity"),
            sell_price=step7_result.get("sell_price")
        )
    
    def _step1_validate_required_fields(self, signal_data: Dict) -> Dict:
        """
        STEP 1: Validate all required fields are present and not null
        Required: ticker, direction, option_type, strike_price, purchase_price
        """
        required = ["ticker", "direction", "option_type", "strike_price", "purchase_price"]
        missing = []
        null_fields = []
        
        for field in required:
            value = signal_data.get(field)
            if value is None:
                null_fields.append(field)
            elif value == "":
                null_fields.append(field)
            elif not value:
                null_fields.append(field)
        
        if null_fields:
            error_msg = f"Required fields have null/empty values: {', '.join(null_fields)}"
            self.execution_log.append(f"❌ {error_msg}")
            # Also print to console for debugging
            print(f"❌ EXECUTOR STEP 1 FAILED: {error_msg}")
            print(f"Signal data received: {signal_data}")
            return {"success": False, "error": error_msg}
        
        # Log all values
        self.execution_log.append(f"  • Ticker: {signal_data['ticker']}")
        self.execution_log.append(f"  • Direction: {signal_data['direction']}")
        self.execution_log.append(f"  • Option Type: {signal_data['option_type']}")
        self.execution_log.append(f"  • Strike Price: ${signal_data['strike_price']}")
        self.execution_log.append(f"  • Purchase Price: ${signal_data['purchase_price']}")
        self.execution_log.append("✅ STEP 1 Complete: All required fields validated")
        
        return {"success": True}
    
    def _step2_validate_and_infer_date(self, signal_data: Dict) -> Dict:
        """
        STEP 2: Validate date and infer year if needed
        If month and day exist but no year, infer based on current date
        If the date has passed this year, use next year
        Returns date in YYYY-MM-DD format
        """
        exp_date = signal_data.get("expiration_date")
        
        # Check if it's a dict (partial date)
        if isinstance(exp_date, dict):
            year = exp_date.get("year")
            month = exp_date.get("month")
            day = exp_date.get("day")
            
            self.execution_log.append(f"  • Input: Year={year}, Month={month}, Day={day}")
            
            if not month or not day:
                self.execution_log.append("  • No month or day provided")
                return {"success": False, "error": "No month or day provided"}
            
            # Infer year if not provided
            today = datetime.now()
            current_year = today.year
            
            try:
                # Create date with current year
                month_int = int(month)
                day_int = int(day)
                test_date = datetime(current_year, month_int, day_int)
                
                # Compare only dates (not time) - if date has passed, use next year
                if test_date.date() < today.date():
                    inferred_year = current_year + 1
                    self.execution_log.append(f"  • Date {month}/{day} has passed in {current_year}")
                    self.execution_log.append(f"  • Using next year: {inferred_year}")
                else:
                    inferred_year = current_year
                    self.execution_log.append(f"  • Date {month}/{day} is upcoming or today in {current_year}")
                
                final_date = f"{inferred_year}-{month.zfill(2)}-{day.zfill(2)}"
                self.execution_log.append(f"✅ Inferred full date: {final_date}")
                return {"success": True, "date": final_date}
            except ValueError as e:
                error_msg = f"Invalid month/day values: {e}"
                self.execution_log.append(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
        
        # Full date string provided
        elif isinstance(exp_date, str) and exp_date:
            self.execution_log.append(f"  • Full date provided: {exp_date}")
            self.execution_log.append(f"✅ Using provided date: {exp_date}")
            return {"success": True, "date": exp_date}
        
        # No date at all
        self.execution_log.append("  • No expiration date provided")
        return {"success": False, "error": "No date provided"}
    
    def _step3_find_nearest_options_chain(
        self,
        ticker: str,
        option_type: str,
        api,
        platform: str
    ) -> Dict:
        """
        STEP 3: Get all available expiration dates from yfinance and select the nearest one
        This is much faster than checking each day individually (1 API call vs 31)
        """
        today = datetime.now()
        self.execution_log.append(f"  • Searching for nearest options chain")
        self.execution_log.append(f"  • Ticker: {ticker}, Type: {option_type}")
        
        try:
            import requests
            
            # Get proxy URL from database
            proxy_url = self.db.get_setting("snaptrade_proxy_url", "")
            
            if not proxy_url:
                self.execution_log.append(f"  ❌ SnapTrade proxy URL not configured")
                return {"success": False, "error": "SnapTrade proxy URL not configured"}
            
            # Call proxy endpoint WITHOUT expiry_date to get ALL available dates in one call
            self.execution_log.append(f"  • Fetching all available expiration dates from yfinance...")
            params = {"symbol": ticker.upper()}
            response = requests.get(f"{proxy_url}/api/options-chain", params=params, timeout=30)
            
            if response.status_code != 200:
                self.execution_log.append(f"  ❌ Proxy request failed: {response.status_code}")
                return {"success": False, "error": f"Proxy request failed: {response.status_code}"}
            
            data = response.json()
            
            if not data.get("success"):
                self.execution_log.append(f"  ❌ {data.get('error', 'Unknown error')}")
                return {"success": False, "error": data.get("error", "Unknown error")}
            
            # Get available expiration dates (already sorted by yfinance)
            available_dates = data.get("available_dates", [])
            
            if not available_dates:
                error_msg = f"No options expiration dates available for {ticker}"
                self.execution_log.append(f"  ❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            self.execution_log.append(f"  ✅ Found {len(available_dates)} available expiration dates")
            self.execution_log.append(f"  • Dates: {', '.join(available_dates[:5])}{'...' if len(available_dates) > 5 else ''}")
            
            # Find the nearest date that is today or in the future
            today_str = today.strftime("%Y-%m-%d")
            nearest_date = None
            
            for exp_date in available_dates:
                # Dates from yfinance are already in YYYY-MM-DD format
                if exp_date >= today_str:
                    nearest_date = exp_date
                    break
            
            if not nearest_date:
                # All dates are in the past, use the last (most recent) one
                nearest_date = available_dates[-1]
                self.execution_log.append(f"  ⚠️ All dates are in the past, using most recent: {nearest_date}")
            
            # Verify the selected date has data for the option type
            chain = data.get("chain", [])
            chain_for_date = None
            
            for chain_item in chain:
                if chain_item.get("expiryDate") == nearest_date:
                    chain_for_date = chain_item
                    break
            
            if chain_for_date:
                calls = chain_for_date.get("calls", [])
                puts = chain_for_date.get("puts", [])
                
                has_data = False
                if option_type.upper() == "CALL":
                    has_data = len(calls) > 0
                elif option_type.upper() == "PUT":
                    has_data = len(puts) > 0
                else:
                    has_data = len(calls) > 0 or len(puts) > 0
                
                if has_data:
                    self.execution_log.append(f"  ✅ Chain verified: {len(calls)} calls, {len(puts)} puts")
                else:
                    self.execution_log.append(f"  ⚠️ Chain exists but no {option_type} data found")
                
            self.execution_log.append(f"  ✅ Selected nearest expiration date: {nearest_date}")
            return {"success": True, "date": nearest_date}
            
        except Exception as e:
            self.execution_log.append(f"  ❌ Error: {str(e)}")
            import traceback
            self.execution_log.append(f"  Traceback: {traceback.format_exc()}")
            return {"success": False, "error": f"Error: {str(e)}"}
    
    def _step4_verify_strike_price(
        self,
        ticker: str,
        expiry_date: str,
        strike_price: float,
        option_type: str,
        api,
        platform: str
    ) -> Dict:
        """
        STEP 4: Verify strike price exists in options chain
        """
        self.execution_log.append(f"  • Verifying strike ${strike_price} for {ticker}")
        self.execution_log.append(f"  • Expiry: {expiry_date}, Type: {option_type}")
        
        # Initialize result to ensure it's always defined
        result = {"success": False, "error": "Unknown error"}
        
        try:
            import requests
            
            # Get proxy URL from database
            proxy_url = self.db.get_setting("snaptrade_proxy_url", "")
            
            if not proxy_url:
                error_msg = "SnapTrade proxy URL not configured"
                self.execution_log.append(f"  ❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            self.execution_log.append(f"  • Proxy URL: {proxy_url}")
            self.execution_log.append(f"  • Fetching options chain from proxy...")
            
            # Call proxy endpoint to verify strike
            params = {
                "symbol": ticker.upper(),
                "expiry_date": expiry_date
            }
            
            try:
                response = requests.get(f"{proxy_url}/api/options-chain", params=params, timeout=30)
                self.execution_log.append(f"  • Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    self.execution_log.append(f"  • Response success: {data.get('success', False)}")
                    
                    if data.get("success") and data.get("chain"):
                        chain = data["chain"]
                        self.execution_log.append(f"  • Chain length: {len(chain)}")
                        
                        if len(chain) > 0:
                            chain_item = chain[0]
                            calls = chain_item.get("calls", [])
                            puts = chain_item.get("puts", [])
                            
                            self.execution_log.append(f"  • Found {len(calls)} calls, {len(puts)} puts")
                            
                            # Check if strike exists in the chain
                            strike_found = False
                            if option_type.upper() == "CALL":
                                strike_found = any(call.get("strike") == strike_price for call in calls)
                                self.execution_log.append(f"  • Checking CALL strikes for ${strike_price}...")
                            elif option_type.upper() == "PUT":
                                strike_found = any(put.get("strike") == strike_price for put in puts)
                                self.execution_log.append(f"  • Checking PUT strikes for ${strike_price}...")
                            else:
                                strike_found = any(call.get("strike") == strike_price for call in calls) or \
                                              any(put.get("strike") == strike_price for put in puts)
                                self.execution_log.append(f"  • Checking both CALL and PUT strikes for ${strike_price}...")
                            
                            if strike_found:
                                self.execution_log.append(f"  ✅ Strike ${strike_price} found in chain")
                                
                                # Store the option contract data for use in Step 6
                                # Find the specific contract to extract its data
                                option_contract = None
                                if option_type.upper() == "CALL":
                                    option_contract = next((c for c in calls if c.get("strike") == strike_price), None)
                                elif option_type.upper() == "PUT":
                                    option_contract = next((p for p in puts if p.get("strike") == strike_price), None)
                                
                                # Store contract data for later use
                                result = {
                                    "success": True,
                                    "option_contract": option_contract,  # Store the contract data
                                    "expiry_date": expiry_date,
                                    "strike": strike_price,
                                    "option_type": option_type.upper()
                                }
                            else:
                                # Log available strikes for debugging
                                available_call_strikes = sorted(set([c.get("strike") for c in calls if c.get("strike")]))
                                available_put_strikes = sorted(set([p.get("strike") for p in puts if p.get("strike")]))
                                self.execution_log.append(f"  ⚠️ Available CALL strikes: {available_call_strikes[:10]}{'...' if len(available_call_strikes) > 10 else ''}")
                                self.execution_log.append(f"  ⚠️ Available PUT strikes: {available_put_strikes[:10]}{'...' if len(available_put_strikes) > 10 else ''}")
                                error_msg = f"Strike ${strike_price} not found in chain"
                                result = {"success": False, "error": error_msg}
                        else:
                            error_msg = "No chain data returned (empty chain array)"
                            self.execution_log.append(f"  ❌ {error_msg}")
                            result = {"success": False, "error": error_msg}
                    else:
                        error_msg = data.get("error", "Unknown error from proxy")
                        self.execution_log.append(f"  ❌ Proxy returned error: {error_msg}")
                        result = {"success": False, "error": error_msg}
                else:
                    # Try to parse error response
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", f"Proxy request failed with status {response.status_code}")
                    except:
                        error_msg = f"Proxy request failed with status {response.status_code}: {response.text[:200]}"
                    self.execution_log.append(f"  ❌ {error_msg}")
                    result = {"success": False, "error": error_msg}
                    
            except requests.exceptions.Timeout:
                error_msg = "Request to proxy timed out after 30 seconds"
                self.execution_log.append(f"  ❌ {error_msg}")
                result = {"success": False, "error": error_msg}
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Cannot connect to proxy server: {str(e)}"
                self.execution_log.append(f"  ❌ {error_msg}")
                result = {"success": False, "error": error_msg}
            except Exception as e:
                error_msg = f"Proxy request error: {str(e)}"
                self.execution_log.append(f"  ❌ {error_msg}")
                import traceback
                self.execution_log.append(f"  • Traceback: {traceback.format_exc()}")
                result = {"success": False, "error": error_msg}
            
            if not result.get("success"):
                error_msg = f"Could not fetch options chain: {result.get('error', 'Unknown error')}"
                self.execution_log.append(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            self.execution_log.append(f"✅ STEP 4 Complete: Strike price ${strike_price} verified")
            return {"success": True}
            
        except Exception as e:
            error_msg = f"Exception verifying strike: {str(e)}"
            self.execution_log.append(f"❌ {error_msg}")
            import traceback
            self.execution_log.append(f"  • Traceback: {traceback.format_exc()}")
            return {"success": False, "error": error_msg}
    
    def _step5_calculate_position_size(
        self,
        purchase_price: float,
        input_position_size,  # Can be int or string like "lotto"
        signal_title: str = ""
    ) -> Dict:
        """
        STEP 5: Calculate position size based on budget
        
        Budget determination (in order of priority):
        1. If signal_title matches a budget filter, use that filter's budget
           - If input_position_size is "lotto", use lottoBudget from filter
        2. If no filter matches, use defaults: $350 if input_position_size == 2, else $700
        
        Special case: input_position_size == 9999 → Testing mode, always 1 contract
        """
        import json
        
        # Convert input_position_size to string for comparison
        pos_size_str = str(input_position_size).lower().strip()
        is_lotto = pos_size_str == "lotto"
        
        # Testing mode: position size 9999 = always 1 contract
        if pos_size_str == "9999":
            self.execution_log.append(f"  • 🧪 TESTING MODE (position size = 9999)")
            self.execution_log.append(f"  • Defaulting to 1 contract for testing")
            self.execution_log.append(f"✅ STEP 5 Complete: Position size = 1 contract (testing)")
            return {"success": True, "position_size": 1}
        
        # Load budget filters from database
        budget_filters_json = self.db.get_setting("executor_budget_filters", "[]")
        try:
            budget_filters = json.loads(budget_filters_json)
        except:
            budget_filters = []
        
        # Try to match signal title against filters (case-insensitive)
        matched_filter = None
        signal_title_lower = signal_title.lower() if signal_title else ""
        
        for f in budget_filters:
            filter_keyword = f.get("signalFilter", "").lower().strip()
            if filter_keyword and filter_keyword in signal_title_lower:
                matched_filter = f
                self.execution_log.append(f"  • 🎯 Matched budget filter: '{filter_keyword}'")
                break
        
        # Determine budget
        if matched_filter:
            if is_lotto:
                budget = float(matched_filter.get("lottoBudget", 100))
                self.execution_log.append(f"  • 🎰 Using LOTTO budget from filter: ${budget:.2f}")
            else:
                budget = float(matched_filter.get("budget", 350))
                self.execution_log.append(f"  • 💰 Using budget from filter: ${budget:.2f}")
        else:
            # Default budget logic
            if is_lotto:
                budget = 100.0  # Default lotto budget
                self.execution_log.append(f"  • 🎰 Using default LOTTO budget: ${budget:.2f}")
            else:
                # Try to parse input_position_size as int for legacy logic
                try:
                    pos_size_int = int(input_position_size)
                    budget = 350.0 if pos_size_int == 2 else 700.0
                except (ValueError, TypeError):
                    budget = 700.0  # Default
                self.execution_log.append(f"  • 💰 Using default budget: ${budget:.2f}")
        
        contract_cost = purchase_price * 100  # Options are per 100 shares
        
        self.execution_log.append(f"  • Input position size: {input_position_size}")
        self.execution_log.append(f"  • Signal title: '{signal_title or '(none)'}'")
        self.execution_log.append(f"  • Budget: ${budget:.2f}")
        self.execution_log.append(f"  • Purchase price: ${purchase_price:.2f}")
        self.execution_log.append(f"  • Contract cost: ${contract_cost:.2f}")
        
        calculated_size = budget / contract_cost
        position_size = int(calculated_size)  # Round down
        
        self.execution_log.append(f"  • Calculated: {calculated_size:.2f}")
        self.execution_log.append(f"  • Position size (rounded down): {position_size}")
        
        if position_size == 0:
            error_msg = f"Position size calculated as 0 (budget ${budget:.2f}, cost ${contract_cost:.2f})"
            self.execution_log.append(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        
        self.execution_log.append(f"✅ STEP 5 Complete: Position size = {position_size} contracts")
        return {"success": True, "position_size": position_size}
    
    def _step6_fill_order_incremental(
        self,
        api,
        platform: str,
        ticker: str,
        expiry_date: str,
        option_type: str,
        strike_price: float,
        purchase_price: float,
        quantity: int
    ) -> Dict:
        """
        STEP 6: Attempt to fill order with incremental pricing using FILL_OR_KILL
        Increment logic based on purchase price:
        - <= $1.00: Start at -10%, increment by $0.03 until +15%
        - $1.01-$3.00: Start at -10%, increment by $0.05 until +15%
        - $3.01-$5.00: Start at -10%, increment by $0.20 until +15%
        - > $5.00: Start at -10%, increment by $0.40 until +15%
        """
        # Determine increment based on purchase price
        if purchase_price <= 1.00:
            increment = 0.03  # 3 cents
        elif purchase_price <= 3.00:
            increment = 0.05  # 5 cents
        elif purchase_price <= 5.00:
            increment = 0.20  # 20 cents
        else:
            increment = 0.40  # 40 cents
        
        # Price range: -10% to +15%
        start_price = purchase_price * 0.90  # -10%
        end_price = purchase_price * 1.15     # +15%
        
        self.execution_log.append(f"  • Base price: ${purchase_price:.2f}")
        self.execution_log.append(f"  • Price range: ${start_price:.2f} (-10%) to ${end_price:.2f} (+15%)")
        self.execution_log.append(f"  • Increment: ${increment:.2f} per attempt")
        self.execution_log.append(f"  • Order type: FILL_OR_KILL")
        self.execution_log.append(f"  • Quantity: {quantity} contracts")
        self.execution_log.append("")
        
        attempts = 0
        current_price = start_price
        
        while current_price <= end_price:
            attempts += 1
            # Round to 2 decimal places to avoid floating point issues
            limit_price = round(current_price, 2)
            
            price_diff = limit_price - purchase_price
            price_diff_pct = (price_diff / purchase_price) * 100
            
            self.execution_log.append(
                f"  🔄 Attempt {attempts}: Limit ${limit_price:.2f} "
                f"({price_diff_pct:+.1f}% from base)"
            )
            
            # Place FILL_OR_KILL order with timing
            attempt_start = time.time()
            order_result = self._place_order(
                api, platform, ticker, expiry_date,
                option_type, strike_price, limit_price, quantity,
                fill_or_kill=True
            )
            attempt_duration = time.time() - attempt_start
            
            if order_result.get("filled"):
                self.execution_log.append(f"  ✅ Order FILLED at ${limit_price:.2f}")
                self.execution_log.append(f"  ⏱️ Attempt {attempts} took {attempt_duration:.2f}s")
                self.execution_log.append(f"✅ STEP 6 Complete: Order filled on attempt {attempts}")
                return {
                    "success": True,
                    "order_id": order_result["order_id"],
                    "filled_price": limit_price,
                    "attempts": attempts
                }
            elif order_result.get("fatal_error"):
                # CRITICAL: Cannot confirm status - STOP IMMEDIATELY, no more retries
                error_detail = order_result.get("error", "Fatal error")
                self.execution_log.append(f"  ⛔ FATAL ERROR - STOPPING: {error_detail}")
                self.execution_log.append(f"  ⏱️ Attempt {attempts} took {attempt_duration:.2f}s")
                return {
                    "success": False,
                    "error": f"FATAL: {error_detail}",
                    "fatal_error": True,
                    "attempts": attempts
                }
            else:
                error_detail = order_result.get("error", "Not filled")
                self.execution_log.append(f"     Not filled: {error_detail}")
                self.execution_log.append(f"     ⏱️ Attempt {attempts} took {attempt_duration:.2f}s")
            
            # Increase price by increment
            current_price += increment
        
        error_msg = f"Order not filled after {attempts} attempts (reached +15% limit at ${end_price:.2f})"
        self.execution_log.append(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    
    def _place_order(
        self,
        api,
        platform: str,
        ticker: str,
        expiry_date: str,
        option_type: str,
        strike_price: float,
        limit_price: float,
        quantity: int,
        fill_or_kill: bool = False
    ) -> Dict:
        """
        Helper to place an options order via SnapTrade proxy
        Uses FOK (Fill or Kill) with --useLastAccount for fast execution
        
        Args:
            fill_or_kill: If True, use FOK time_in_force (proxy handles FOK simulation)
        
        Returns:
            Dict with 'filled' (bool), 'order_id', 'filled_price', 'error'
        """
        try:
            import requests
            
            # Get proxy URL from database
            proxy_url = self.db.get_setting("snaptrade_proxy_url", "")
            
            if not proxy_url:
                self.execution_log.append(f"  • ❌ SnapTrade proxy URL not configured")
                return {"filled": False, "error": "SnapTrade proxy URL not configured"}
                
            # Build payload for proxy's /api/trade/option endpoint
            # Use empty account_id to trigger --useLastAccount in proxy
            payload = {
                "ticker": ticker.upper(),
                "strike": strike_price,
                "exp": expiry_date,  # Format: YYYY-MM-DD
                "optionType": option_type.upper(),  # CALL or PUT
                        "action": "BUY",
                "contracts": quantity,
                "orderType": "Limit",
                "limitPrice": limit_price,
                "tif": "FOK" if fill_or_kill else "GTC",  # FOK triggers proxy's FOK simulation
                "account_id": ""  # Empty = use --useLastAccount
            }
            
            self.execution_log.append(f"  • 📤 Placing via proxy: {ticker} {strike_price} {option_type} @ ${limit_price:.2f}")
            self.execution_log.append(f"  • Using --useLastAccount, TIF: {'FOK' if fill_or_kill else 'GTC'}")
            
            # Call proxy endpoint
            response = requests.post(
                f"{proxy_url}/api/trade/option",
                json=payload,
                timeout=90  # Longer timeout for FOK (includes 3s wait + status check + cancel)
            )
            
            result = response.json()
            
            # Check response
            if response.status_code == 200 and result.get("success"):
                # Order placed and filled successfully
                order_id = result.get("order_id", "unknown")
                self.execution_log.append(f"  • ✅ Order FILLED - Order ID: {order_id}")
                return {
                    "filled": True,
                    "order_id": str(order_id),
                    "filled_price": limit_price
                }
            else:
                # Check if it's a FOK cancellation (expected behavior, not an error)
                error_msg = result.get("error", "Unknown error")
                order_id = result.get("order_id")
                
                if "fok" in error_msg.lower() and "cancel" in error_msg.lower():
                    # FOK order was placed but not filled, then cancelled - this is expected
                    self.execution_log.append(f"  • ⚠️ FOK not filled - cancelled (Order ID: {order_id})")
                    return {
                        "filled": False,
                        "error": "FOK order not filled",
                        "order_id": str(order_id) if order_id else None
                    }
                elif "buying power" in error_msg.lower() or "insufficient" in error_msg.lower():
                    # Insufficient funds
                    self.execution_log.append(f"  • ❌ Insufficient buying power")
                    return {"filled": False, "error": "Insufficient buying power"}
                elif "symbol" in error_msg.lower() and "invalid" in error_msg.lower():
                    # Invalid symbol
                    self.execution_log.append(f"  • ❌ Invalid symbol")
                    return {"filled": False, "error": f"Invalid symbol: {error_msg}"}
                elif "cannot confirm" in error_msg.lower():
                    # CRITICAL: Cannot confirm order status - MUST STOP all retries
                    self.execution_log.append(f"  • ⛔ FATAL: Cannot confirm order status - STOPPING ALL RETRIES")
                    self.execution_log.append(f"  • Check brokerage account manually!")
                    return {"filled": False, "error": error_msg, "fatal_error": True}
                else:
                    # Other error
                    self.execution_log.append(f"  • ❌ Order failed: {error_msg}")
                    return {"filled": False, "error": error_msg}
                
        except requests.exceptions.Timeout:
            self.execution_log.append(f"  • ❌ Request timed out")
            return {"filled": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.execution_log.append(f"  • ❌ Cannot connect to proxy")
            return {"filled": False, "error": "Cannot connect to proxy server"}
        except Exception as e:
            self.execution_log.append(f"  • ❌ Exception: {str(e)}")
            return {"filled": False, "error": str(e)}
    
    def _step7_place_take_profit_order(
        self,
        ticker: str,
        expiry_date: str,
        option_type: str,
        strike_price: float,
        filled_price: float,
        position_size: int,
        signal_title: str = ""
    ) -> Dict:
        """
        STEP 7: Place a take-profit limit SELL order after successful BUY
        
        Rules (defaults, can be customized via selling filters):
        - Sell at least 80% of position (rounded UP to whole number)
        - Limit price = 1.3x filled price (30% profit), rounded UP to nearest cent
        
        If a selling filter matches signal_title:
        - Use filter's sellPercentage (instead of 80%)
        - Use filter's profitMultiplier (instead of 1.3x)
        """
        import math
        import requests
        import json
        
        # Load selling filters from database
        selling_filters_json = self.db.get_setting("executor_selling_filters", "[]")
        try:
            selling_filters = json.loads(selling_filters_json)
        except:
            selling_filters = []
        
        # Try to match signal title against filters (case-insensitive)
        matched_filter = None
        signal_title_lower = signal_title.lower() if signal_title else ""
        
        for f in selling_filters:
            filter_keyword = f.get("signalFilter", "").lower().strip()
            if filter_keyword and filter_keyword in signal_title_lower:
                matched_filter = f
                self.execution_log.append(f"  • 🎯 Matched selling strategy filter: '{filter_keyword}'")
                break
        
        # Determine sell percentage and profit multiplier
        if matched_filter:
            sell_percentage = float(matched_filter.get("sellPercentage", 80)) / 100.0
            profit_multiplier = float(matched_filter.get("profitMultiplier", 1.3))
            self.execution_log.append(f"  • 📊 Using custom strategy: {sell_percentage*100:.0f}% @ {profit_multiplier}x")
        else:
            sell_percentage = 0.80  # Default: 80%
            profit_multiplier = 1.30  # Default: 1.3x (30% profit)
            self.execution_log.append(f"  • 📊 Using default strategy: 80% @ 1.3x")
        
        # Calculate sell quantity using configured percentage, rounded UP
        sell_quantity_raw = position_size * sell_percentage
        sell_quantity = math.ceil(sell_quantity_raw)
        
        self.execution_log.append(f"  • Position size: {position_size} contracts")
        self.execution_log.append(f"  • Signal title: '{signal_title or '(none)'}'")
        self.execution_log.append(f"  • {sell_percentage*100:.0f}% of position: {sell_quantity_raw:.1f}")
        self.execution_log.append(f"  • Sell quantity (rounded UP): {sell_quantity} contracts")
        
        # Calculate sell price using configured multiplier, rounded UP to nearest cent
        target_price_raw = filled_price * profit_multiplier
        # Round UP to nearest cent (0.01)
        sell_price = math.ceil(target_price_raw * 100) / 100
        
        self.execution_log.append(f"  • Filled price: ${filled_price:.2f}")
        self.execution_log.append(f"  • Target ({profit_multiplier}x): ${target_price_raw:.4f}")
        self.execution_log.append(f"  • Sell price (rounded UP): ${sell_price:.2f}")
        self.execution_log.append(f"  • Expected profit: {((sell_price / filled_price) - 1) * 100:.1f}%")
        
        # Get proxy URL
        proxy_url = self.db.get_setting("snaptrade_proxy_url", "")
        
        if not proxy_url:
            self.execution_log.append(f"  • ❌ SnapTrade proxy URL not configured")
            return {"success": False, "error": "SnapTrade proxy URL not configured"}
        
        # Build payload for SELL order (not FOK, just GTC limit order)
        payload = {
            "ticker": ticker.upper(),
            "strike": strike_price,
            "exp": expiry_date,
            "optionType": option_type.upper(),
            "action": "SELL",  # SELL to close position
            "contracts": sell_quantity,
            "orderType": "Limit",
            "limitPrice": sell_price,
            "tif": "GTC",  # Good Til Cancelled - leave open until filled
            "account_id": ""  # Use --useLastAccount
        }
        
        self.execution_log.append(f"  • 📤 Placing SELL order: {ticker} {strike_price} {option_type}")
        self.execution_log.append(f"  • Action: SELL {sell_quantity} @ ${sell_price:.2f} (GTC)")
        
        try:
            response = requests.post(
                f"{proxy_url}/api/trade/option",
                json=payload,
                timeout=60
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("success"):
                order_id = result.get("order_id", "unknown")
                self.execution_log.append(f"  • ✅ Take-profit SELL order placed!")
                self.execution_log.append(f"  • Order ID: {order_id}")
                self.execution_log.append(f"✅ STEP 7 Complete: Sell order placed for {sell_quantity} contracts @ ${sell_price:.2f}")
                return {
                    "success": True,
                    "order_id": str(order_id),
                    "sell_quantity": sell_quantity,
                    "sell_price": sell_price
                }
            else:
                error_msg = result.get("error", "Unknown error")
                self.execution_log.append(f"  • ❌ Failed to place sell order: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "sell_quantity": sell_quantity,
                    "sell_price": sell_price
                }
                
        except requests.exceptions.Timeout:
            self.execution_log.append(f"  • ❌ Request timed out")
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.execution_log.append(f"  • ❌ Cannot connect to proxy")
            return {"success": False, "error": "Cannot connect to proxy server"}
        except Exception as e:
            self.execution_log.append(f"  • ❌ Exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _fail(self, error: str, step: int, execution_id: int = None) -> Dict:
        """Record failure and return result"""
        self.execution_log.append(f"\n❌ EXECUTION FAILED AT STEP {step}")
        self.execution_log.append(f"Error: {error}")
        
        if execution_id:
            self.db.update_execution_attempt(
                execution_id,
                status="failed",
                step_reached=step,
                error_message=error,
                log="\n".join(self.execution_log)
            )
        
        return {
            "success": False,
            "error": error,
            "step_failed": step,
            "log": self.execution_log
        }
    
    def _success(
        self,
        execution_id: int,
        order_id: str,
        filled_price: float,
        position_size: int,
        expiration_date: str,
        fill_attempts: int,
        sell_order_id: str = None,
        sell_quantity: int = None,
        sell_price: float = None
    ) -> Dict:
        """Record success and return result"""
        self.execution_log.append(f"  • BUY Order ID: {order_id}")
        self.execution_log.append(f"  • Filled Price: ${filled_price:.2f}")
        self.execution_log.append(f"  • Position Size: {position_size} contracts")
        self.execution_log.append(f"  • Expiration: {expiration_date}")
        self.execution_log.append(f"  • Fill Attempts: {fill_attempts}")
        
        if sell_order_id:
            self.execution_log.append(f"  • SELL Order ID: {sell_order_id}")
            self.execution_log.append(f"  • Sell Quantity: {sell_quantity} contracts")
            self.execution_log.append(f"  • Sell Price: ${sell_price:.2f}")
        
        if execution_id:
            self.db.update_execution_attempt(
                execution_id,
                status="success",
                step_reached=7,
                order_id=order_id,
                filled_price=filled_price,
                final_position_size=position_size,
                final_expiration_date=expiration_date,
                fill_attempts=fill_attempts,
                log="\n".join(self.execution_log)
            )
        
        result = {
            "success": True,
            "order_id": order_id,
            "filled_price": filled_price,
            "position_size": position_size,
            "expiration_date": expiration_date,
            "fill_attempts": fill_attempts,
            "log": self.execution_log
        }
        
        # Add sell order info if available
        if sell_order_id:
            result["sell_order_id"] = sell_order_id
            result["sell_quantity"] = sell_quantity
            result["sell_price"] = sell_price
        
        return result

