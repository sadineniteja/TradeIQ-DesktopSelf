"""
E*TRADE API integration module for TradeIQ.
Based on official E*TRADE Python client implementation using rauth.
"""

import os
import re
import logging
from typing import Dict, Optional
from rauth import OAuth1Service

# Configure logging
logger = logging.getLogger(__name__)


class EtradeAPI:
    def __init__(
        self,
        consumer_key: str = None,
        consumer_secret: str = None,
        sandbox: bool = True,
        db: Optional[object] = None,
    ):
        """
        Initialize E*TRADE API connection using rauth (official client approach).
        """
        # Load from database if available
        if db:
            use_sandbox = db.get_setting("etrade_use_sandbox", "true").lower() == "true"
            sandbox = use_sandbox
            
            if use_sandbox:
                saved_key = db.get_setting("etrade_sandbox_key", "")
                saved_secret = db.get_setting("etrade_sandbox_secret", "")
            else:
                saved_key = db.get_setting("etrade_prod_key", "")
                saved_secret = db.get_setting("etrade_prod_secret", "")
            
            if saved_key:
                consumer_key = consumer_key or saved_key
            if saved_secret:
                consumer_secret = consumer_secret or saved_secret
        
        self.consumer_key = consumer_key or os.getenv("ETRADE_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.getenv("ETRADE_CONSUMER_SECRET")
        self.sandbox = sandbox
        self.db = db

        # Base URL
        self.base_url = "https://apisb.etrade.com" if sandbox else "https://api.etrade.com"

        # OAuth service
        self.oauth_service = OAuth1Service(
            name="etrade",
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            request_token_url=f"{self.base_url}/oauth/request_token",
            access_token_url=f"{self.base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=self.base_url,
        )

        self.session = None
        self.is_authenticated = False
        self.accounts = []
        self.default_account_id = None
        
        self._load_tokens()
    
    def _load_tokens(self):
        access_token = os.getenv("ETRADE_ACCESS_TOKEN")
        access_token_secret = os.getenv("ETRADE_ACCESS_TOKEN_SECRET")
        if access_token and access_token_secret:
            self.session = self.oauth_service.get_session((access_token, access_token_secret))
            self.is_authenticated = True
            logger.info("Loaded existing E*TRADE tokens from environment")

    def _save_tokens(self, access_token: str, access_token_secret: str):
        os.environ["ETRADE_ACCESS_TOKEN"] = access_token
        os.environ["ETRADE_ACCESS_TOKEN_SECRET"] = access_token_secret

    # OAuth flow
    def get_request_token(self) -> Dict:
        try:
            request_token, request_token_secret = self.oauth_service.get_request_token(
                params={"oauth_callback": "oob", "format": "json"}
            )
            self.request_token = request_token
            self.request_token_secret = request_token_secret
            auth_url = self.oauth_service.authorize_url.format(self.consumer_key, request_token)
            return {"success": True, "request_token": request_token, "authorization_url": auth_url}
        except Exception as e:
            return {"success": False, "error": f"Failed to get request token: {str(e)}"}

    def get_access_token(self, verifier: str) -> Dict:
        try:
            if not hasattr(self, "request_token") or not hasattr(self, "request_token_secret"):
                return {"success": False, "error": "Request token missing. Call get_request_token first."}

            self.session = self.oauth_service.get_auth_session(
                self.request_token, self.request_token_secret, params={"oauth_verifier": verifier}
            )
            access_token = self.session.access_token
            access_token_secret = self.session.access_token_secret
            self._save_tokens(access_token, access_token_secret)
            self.is_authenticated = True
            return {"success": True, "access_token": access_token}
        except Exception as e:
            return {"success": False, "error": f"Failed to get access token: {str(e)}"}

    # Accounts
    def get_accounts_list(self) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "accounts": []}

            url = f"{self.base_url}/v1/accounts/list.json"
            response = self.session.get(url, header_auth=True)

            if response.status_code == 200:
                data = response.json()
                accounts = []
                if (
                    "AccountListResponse" in data
                    and "Accounts" in data["AccountListResponse"]
                    and "Account" in data["AccountListResponse"]["Accounts"]
                ):
                    accounts_data = data["AccountListResponse"]["Accounts"]["Account"]
                    if isinstance(accounts_data, dict):
                        accounts_data = [accounts_data]
                    for acct in accounts_data:
                        if acct.get("accountStatus") != "CLOSED":
                            accounts.append(acct)
                self.accounts = accounts
                if accounts:
                    first = accounts[0]
                    self.default_account_id = first.get("accountIdKey") or first.get("accountId")
                return {"success": True, "accounts": accounts, "default_account_id": self.default_account_id}
            else:
                err = "Failed to get accounts"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "accounts": [], "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "accounts": []}

    # Balance
    def get_account_balance(self, account_id_key: str, inst_type: str = "BROKERAGE") -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "balance": {}}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/balance.json"
            params = {"instType": inst_type, "realTimeNAV": "true"}
            headers = {"consumerkey": self.consumer_key}
            response = self.session.get(url, header_auth=True, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                balance = data.get("BalanceResponse", {})
                return {"success": True, "balance": balance}
            else:
                err = "Failed to get balance"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "balance": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "balance": {}}

    # Portfolio
    def get_account_portfolio(self, account_id_key: str) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "portfolio": {}}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/portfolio.json"
            response = self.session.get(url, header_auth=True)
            if response.status_code == 200:
                data = response.json()
                portfolio = data.get("PortfolioResponse", {})
                return {"success": True, "portfolio": portfolio}
            elif response.status_code == 204:
                return {"success": True, "portfolio": {"Position": []}, "message": "Portfolio is empty"}
            else:
                err = "Failed to get portfolio"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "portfolio": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "portfolio": {}}

    # Orders
    def get_orders(self, account_id_key: str, status: str = "OPEN") -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "orders": {}}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders.json"
            params = {"status": status}
            headers = {"consumerkey": self.consumer_key}
            response = self.session.get(url, header_auth=True, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                orders = data.get("OrdersResponse", {})
                return {"success": True, "orders": orders}
            elif response.status_code == 204:
                return {"success": True, "orders": {"Order": []}, "message": "No orders found"}
            else:
                err = "Failed to get orders"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "orders": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "orders": {}}

    def preview_order(self, account_id_key: str, order_xml: str) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "preview": {}}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/preview.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            response = self.session.post(url, header_auth=True, headers=headers, data=order_xml)
            if response.status_code == 200:
                data = response.json()
                preview = data.get("PreviewOrderResponse", {})
                return {"success": True, "preview": preview}
            else:
                err = "Failed to preview order"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "preview": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "preview": {}}

    def place_order(self, account_id_key: str, order_xml: str) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "order": {}}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            response = self.session.post(url, header_auth=True, headers=headers, data=order_xml)
            if response.status_code == 200:
                data = response.json()
                order_resp = data.get("PlaceOrderResponse", {})
                return {"success": True, "order": order_resp}
            else:
                err = "Failed to place order"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "order": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "order": {}}

    def cancel_order(self, account_id_key: str, order_id: str) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated"}

            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/cancel.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            payload = f"<CancelOrderRequest><orderId>{order_id}</orderId></CancelOrderRequest>"
            response = self.session.put(url, header_auth=True, headers=headers, data=payload)
            if response.status_code == 200:
                data = response.json()
                cancel_resp = data.get("CancelOrderResponse", {})
                return {"success": True, "cancel": cancel_resp}
            else:
                err = "Failed to cancel order"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}"}

    # Market data
    def get_quote(self, symbol: str) -> Dict:
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "quote": {}}

            url = f"{self.base_url}/v1/market/quote/{symbol}.json"
            response = self.session.get(url, header_auth=True)
            if response.status_code == 200:
                data = response.json()
                quote = data.get("QuoteResponse", {})
                return {"success": True, "quote": quote}
            else:
                err = "Failed to get quote"
                try:
                    err_json = response.json()
                    if "QuoteResponse" in err_json and "Messages" in err_json["QuoteResponse"]:
                        msgs = err_json["QuoteResponse"]["Messages"].get("Message")
                        if isinstance(msgs, list) and msgs:
                            err = msgs[0].get("description", err)
                except Exception:
                    pass
                return {"success": False, "error": err, "quote": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "quote": {}}

    def set_default_account(self, account_id_key: str):
        self.default_account_id = account_id_key

    def update_credentials(self, consumer_key: str, consumer_secret: str, sandbox: bool = True):
        """Update API credentials and environment."""
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.sandbox = sandbox
        self.base_url = "https://apisb.etrade.com" if sandbox else "https://api.etrade.com"
        self.oauth_service = OAuth1Service(
            name="etrade",
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            request_token_url=f"{self.base_url}/oauth/request_token",
            access_token_url=f"{self.base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=self.base_url,
        )
        self.session = None
        self.is_authenticated = False

    def test_credentials(self, consumer_key: str = "", consumer_secret: str = "", sandbox: bool = True) -> Dict:
        """
        Validate consumer key/secret by attempting a request token call.
        Does not persist tokens or mutate current session.
        """
        key = consumer_key
        secret = consumer_secret

        # fallback to stored settings if missing
        if self.db:
            if sandbox:
                key = key or self.db.get_setting("etrade_sandbox_key", "")
                secret = secret or self.db.get_setting("etrade_sandbox_secret", "")
            else:
                key = key or self.db.get_setting("etrade_prod_key", "")
                secret = secret or self.db.get_setting("etrade_prod_secret", "")

        key = key or self.consumer_key
        secret = secret or self.consumer_secret

        if not key or not secret:
            return {"success": False, "error": "Consumer key/secret required", "sandbox": sandbox}

        base_url = "https://apisb.etrade.com" if sandbox else "https://api.etrade.com"
        temp_service = OAuth1Service(
            name="etrade-test",
            consumer_key=key,
            consumer_secret=secret,
            request_token_url=f"{base_url}/oauth/request_token",
            access_token_url=f"{base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=base_url,
        )
        try:
            temp_service.get_request_token(params={"oauth_callback": "oob", "format": "json"})
            return {"success": True, "sandbox": sandbox}
        except Exception as e:
            return {"success": False, "error": f"Failed to get request token: {str(e)}", "sandbox": sandbox}

    # ==================== Options & Chains ====================
    
    def get_option_expiration_dates(self, symbol: str) -> Dict:
        """
        Get available option expiration dates for a symbol.
        This is useful for finding the nearest available expiration dates.
        
        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
            
        Returns:
            Dictionary with success status and list of expiration dates
            Format: {
                "success": bool,
                "expiration_dates": [
                    {
                        "year": int,
                        "month": int,
                        "day": int,
                        "date_string": "YYYY-MM-DD"
                    },
                    ...
                ],
                "error": str (if failed)
            }
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "expiration_dates": []}

            url = f"{self.base_url}/v1/market/optionexpiredate.json"
            params = {
                "symbol": symbol.upper()
            }

            headers = {"consumerkey": self.consumer_key}
            logger.info(f"========== OPTION EXPIRATION DATES REQUEST ==========")
            logger.info(f"URL: {url}")
            logger.info(f"Symbol: {symbol}")
            
            response = self.session.get(url, header_auth=True, params=params, headers=headers)
            logger.info(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Response keys: {list(data.keys())}")
                
                # Parse the response - E*TRADE API typically returns:
                # OptionExpireDateResponse -> ExpirationDate -> date (YYYYMMDD format)
                expiration_dates = []
                
                try:
                    expire_response = data.get("OptionExpireDateResponse", {})
                    dates = expire_response.get("ExpirationDate", [])
                    
                    # Handle both single date (dict) and multiple dates (list)
                    if isinstance(dates, dict):
                        dates = [dates]
                    
                    for date_item in dates:
                        if isinstance(date_item, dict):
                            # E*TRADE returns date as YYYYMMDD integer or string
                            date_value = date_item.get("date") or date_item.get("expirationDate")
                            
                            if date_value:
                                # Convert to string if it's an integer
                                date_str = str(date_value)
                                
                                # Parse YYYYMMDD format
                                if len(date_str) == 8:
                                    year = int(date_str[0:4])
                                    month = int(date_str[4:6])
                                    day = int(date_str[6:8])
                                    
                                    expiration_dates.append({
                                        "year": year,
                                        "month": month,
                                        "day": day,
                                        "date_string": f"{year}-{month:02d}-{day:02d}"
                                    })
                        elif isinstance(date_item, (int, str)):
                            # Direct date value (YYYYMMDD)
                            date_str = str(date_item)
                            if len(date_str) == 8:
                                year = int(date_str[0:4])
                                month = int(date_str[4:6])
                                day = int(date_str[6:8])
                                
                                expiration_dates.append({
                                    "year": year,
                                    "month": month,
                                    "day": day,
                                    "date_string": f"{year}-{month:02d}-{day:02d}"
                                })
                    
                    # Sort by date (nearest first)
                    expiration_dates.sort(key=lambda x: (x["year"], x["month"], x["day"]))
                    
                    logger.info(f"Found {len(expiration_dates)} expiration date(s)")
                    if expiration_dates:
                        logger.info(f"Nearest expiration: {expiration_dates[0]['date_string']}")
                        if len(expiration_dates) > 1:
                            logger.info(f"Farthest expiration: {expiration_dates[-1]['date_string']}")
                    logger.info(f"==========================================")
                    
                    return {
                        "success": True,
                        "expiration_dates": expiration_dates,
                        "nearest_date": expiration_dates[0]["date_string"] if expiration_dates else None
                    }
                except Exception as parse_error:
                    logger.error(f"Error parsing expiration dates response: {parse_error}")
                    logger.debug(f"Response data: {data}")
                    return {
                        "success": False,
                        "error": f"Failed to parse expiration dates: {str(parse_error)}",
                        "expiration_dates": [],
                        "raw_response": data
                    }
            else:
                err = "Failed to get option expiration dates"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                    elif "message" in err_json:
                        err = err_json["message"]
                except Exception:
                    pass
                logger.error(f"API Error: {err} (Status: {response.status_code})")
                return {
                    "success": False,
                    "error": err,
                    "status_code": response.status_code,
                    "expiration_dates": []
                }
        except Exception as e:
            logger.error(f"Exception getting option expiration dates: {str(e)}")
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "expiration_dates": []
            }
    def parse_osikey(self, osikey: str) -> Dict:
        """
        Parse osiKey format into components.
        
        Format: SYMBOL--YYMMDD[C/P]STRIKE
        Example: "AAPL--251212C00280000" -> symbol="AAPL", year=2025, month=12, day=12, callPut="CALL", strike=280.0
        """
        result = {
            "symbol": "",
            "expiryYear": None,
            "expiryMonth": None,
            "expiryDay": None,
            "callPut": "CALL",
            "strikePrice": None
        }
        
        if not osikey:
            return result
        
        # Handle osiKey format: SYMBOL--YYMMDD[C/P]STRIKE
        # Example: "AAPL--251212C00280000"
        match = re.match(r'^([A-Z]+)--(\d{6})([CPcp])(\d{8})$', osikey)
        if match:
            symbol = match.group(1)
            date_str = match.group(2)  # YYMMDD
            option_type = match.group(3).upper()
            strike_str = match.group(4)  # 8 digits
            
            # Parse date: YYMMDD
            year_2digit = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            
            # Convert 2-digit year to 4-digit (assuming 20xx for years 00-99)
            year = 2000 + year_2digit if year_2digit < 100 else year_2digit
            
            # Parse strike: 8 digits, last 3 are decimals
            # Example: 00280000 = 280.000
            strike_int = int(strike_str)
            strike = strike_int / 1000.0
            
            result["symbol"] = symbol
            result["expiryYear"] = year
            result["expiryMonth"] = month
            result["expiryDay"] = day
            result["callPut"] = "CALL" if option_type == "C" else "PUT"
            result["strikePrice"] = strike
        
        return result
    
    def get_option_chain(
        self,
        symbol: str,
        expiry_year: int,
        expiry_month: int,
        expiry_day: int,
        strike_price_near: float = None,
        no_of_strikes: int = None,
        include_weekly: bool = True,
    ) -> Dict:
        """
        Fetch option chains for a symbol.
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "chain": {}}

            url = f"{self.base_url}/v1/market/optionchains.json"
            params = {
                "symbol": symbol,
                "expiryYear": expiry_year,
                "expiryMonth": expiry_month,
                "expiryDay": expiry_day,
                "includeWeekly": "true" if include_weekly else "false",
            }
            if strike_price_near is not None:
                params["strikePriceNear"] = strike_price_near
            if no_of_strikes is not None:
                params["noOfStrikes"] = no_of_strikes

            headers = {"consumerkey": self.consumer_key}
            logger.info(f"========== OPTIONS CHAIN REQUEST ==========")
            logger.info(f"URL: {url}")
            logger.info(f"Params: {params}")
            logger.info(f"Strike Price Near: {strike_price_near}")
            logger.info(f"No of Strikes: {no_of_strikes}")
            
            response = self.session.get(url, header_auth=True, params=params, headers=headers)
            logger.info(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # Log how many strikes were returned
                option_pairs = data.get("OptionChainResponse", {}).get("OptionPair", [])
                strikes_count = len(option_pairs) if isinstance(option_pairs, list) else 1
                logger.info(f"Options chain returned {strikes_count} strike(s)")
                logger.info(f"Response keys: {list(data.keys())}")
                if isinstance(option_pairs, list) and len(option_pairs) > 0:
                    logger.info(f"First strike: {option_pairs[0].get('Call', {}).get('strikePrice', 'N/A')}")
                    if len(option_pairs) > 1:
                        logger.info(f"Last strike: {option_pairs[-1].get('Call', {}).get('strikePrice', 'N/A')}")
                logger.info(f"==========================================")
                return {"success": True, "chain": data}
            else:
                err = "Failed to get option chain"
                try:
                    err_json = response.json()
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                except Exception:
                    pass
                return {"success": False, "error": err, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "chain": {}}

    def _build_option_order_xml(self, payload: Dict, order_type: str = "OPTN", request_type: str = "Preview") -> str:
        """
        Build an XML payload for a single-leg options order.
        Required keys: option_symbol (osiKey format), order_action, quantity, price_type
        Optional: limit_price, order_term, market_session, all_or_none, PreviewId (for Place requests)
        
        Args:
            request_type: "Preview" for preview orders, "Place" for placing orders
        
        Uses the same approach as the standalone script: parses osiKey and uses <callPut> with separate fields.
        """
        option_symbol_osikey = payload.get("option_symbol")
        parsed_osikey = self.parse_osikey(option_symbol_osikey)
        
        symbol = parsed_osikey["symbol"]
        expiry_year = parsed_osikey["expiryYear"]
        expiry_month = parsed_osikey["expiryMonth"]
        expiry_day = parsed_osikey["expiryDay"]
        call_put = parsed_osikey["callPut"]
        strike_price = parsed_osikey["strikePrice"]

        order_action = payload.get("order_action", "BUY_OPEN")
        quantity = payload.get("quantity", 1)
        price_type = payload.get("price_type", "MARKET")
        limit_price = payload.get("limit_price", "")
        order_term = payload.get("order_term", "GOOD_FOR_DAY")
        market_session = payload.get("market_session", "REGULAR")
        all_or_none = payload.get("all_or_none", False)  # FILL_OR_KILL flag

        # Convert quantity to int if it's a string
        if isinstance(quantity, str):
            try:
                quantity = int(quantity)
            except ValueError:
                raise ValueError(f"Invalid quantity: {quantity}")

        # Validate parsed components
        if not symbol or strike_price is None:
            raise ValueError(f"Could not parse option symbol (osiKey): {option_symbol_osikey}. Expected format: SYMBOL--YYMMDD[C/P]STRIKE (e.g., 'AAPL--251212C00280000')")

        limit_price_tag = f"<limitPrice>{limit_price}</limitPrice>" if price_type != "MARKET" and limit_price else "<limitPrice></limitPrice>"

        # Use PlaceOrderRequest for placing, PreviewOrderRequest for preview
        root_tag = "PlaceOrderRequest" if request_type == "Place" else "PreviewOrderRequest"
        
        # Add PreviewIds container if it's a Place request and PreviewId is provided
        # Note: E*TRADE API requires PreviewIds (plural) container with previewId (singular, lowercase p) inside
        # Format: <PreviewIds><previewId>12345678</previewId></PreviewIds>
        preview_ids_tag = ""
        preview_id_value = payload.get("PreviewId") or payload.get("previewId") or payload.get("preview_id")  # Support multiple formats for backward compatibility
        if request_type == "Place" and preview_id_value:
            preview_ids_tag = f"    <PreviewIds>\n        <previewId>{preview_id_value}</previewId>\n    </PreviewIds>\n    "

        xml = f"""
<{root_tag}>
{preview_ids_tag}<orderType>{order_type}</orderType>
    <clientOrderId>{payload.get('client_order_id', '')}</clientOrderId>
    <Order>
        <allOrNone>{str(all_or_none).lower()}</allOrNone>
        <priceType>{price_type}</priceType>
        <orderTerm>{order_term}</orderTerm>
        <marketSession>{market_session}</marketSession>
        <stopPrice></stopPrice>
        {limit_price_tag}
        <Instrument>
            <Product>
                <symbol>{symbol}</symbol>
                <securityType>OPTN</securityType>
                <callPut>{call_put}</callPut>
                <expiryYear>{expiry_year}</expiryYear>
                <expiryMonth>{expiry_month}</expiryMonth>
                <expiryDay>{expiry_day}</expiryDay>
                <strikePrice>{strike_price}</strikePrice>
            </Product>
            <orderAction>{order_action}</orderAction>
            <quantityType>QUANTITY</quantityType>
            <quantity>{quantity}</quantity>
        </Instrument>
    </Order>
</{root_tag}>
""".strip()
        logger.debug(f"Generated Options XML ({request_type}): {xml}")
        return xml

    def _build_equity_order_xml(self, payload: Dict, order_type: str = "EQ", request_type: str = "Preview") -> str:
        """
        Build an XML payload for an equity (stock) order.
        Required keys: symbol, order_action, quantity, price_type
        Optional: limit_price, order_term, market_session, stop_price
        
        Args:
            request_type: "Preview" for preview orders, "Place" for placing orders
        """
        symbol = payload.get("symbol", "").strip().upper()
        order_action = payload.get("order_action", "BUY")
        quantity = payload.get("quantity", 1)
        price_type = payload.get("price_type", "MARKET")
        limit_price = payload.get("limit_price", "")
        stop_price = payload.get("stop_price", "")
        order_term = payload.get("order_term", "GOOD_FOR_DAY")
        market_session = payload.get("market_session", "REGULAR")
        all_or_none = payload.get("all_or_none", False)

        if not symbol:
            raise ValueError("Symbol is required for equity orders")

        # Convert quantity to int if it's a string
        if isinstance(quantity, str):
            try:
                quantity = int(quantity)
            except ValueError:
                raise ValueError(f"Invalid quantity: {quantity}")

        # Build limit price tag
        limit_price_tag = ""
        if price_type in ["LIMIT", "STOP_LIMIT"]:
            if limit_price:
                # Ensure limit_price is properly formatted
                try:
                    float(limit_price)  # Validate it's a number
                    limit_price_tag = f"<limitPrice>{limit_price}</limitPrice>"
                except ValueError:
                    limit_price_tag = "<limitPrice></limitPrice>"
            else:
                limit_price_tag = "<limitPrice></limitPrice>"
        else:
            limit_price_tag = "<limitPrice></limitPrice>"

        # Build stop price tag
        stop_price_tag = ""
        if price_type in ["STOP", "STOP_LIMIT"]:
            if stop_price:
                try:
                    float(stop_price)  # Validate it's a number
                    stop_price_tag = f"<stopPrice>{stop_price}</stopPrice>"
                except ValueError:
                    stop_price_tag = "<stopPrice></stopPrice>"
            else:
                stop_price_tag = "<stopPrice></stopPrice>"
        else:
            stop_price_tag = "<stopPrice></stopPrice>"

        # Use PlaceOrderRequest for placing, PreviewOrderRequest for preview
        root_tag = "PlaceOrderRequest" if request_type == "Place" else "PreviewOrderRequest"

        # Add PreviewIds container if it's a Place request and PreviewId is provided
        # Note: E*TRADE API requires PreviewIds (plural) container with previewId (singular, lowercase p) inside
        # Format: <PreviewIds><previewId>12345678</previewId></PreviewIds>
        preview_ids_tag = ""
        preview_id_value = payload.get("PreviewId") or payload.get("previewId") or payload.get("preview_id")  # Support multiple formats for backward compatibility
        if request_type == "Place" and preview_id_value:
            preview_ids_tag = f"    <PreviewIds>\n        <previewId>{preview_id_value}</previewId>\n    </PreviewIds>\n    "

        xml = f"""
<{root_tag}>
{preview_ids_tag}<orderType>{order_type}</orderType>
    <clientOrderId>{payload.get('client_order_id', '')}</clientOrderId>
    <Order>
        <allOrNone>{str(all_or_none).lower()}</allOrNone>
        <priceType>{price_type}</priceType>
        <orderTerm>{order_term}</orderTerm>
        <marketSession>{market_session}</marketSession>
        {stop_price_tag}
        {limit_price_tag}
        <Instrument>
            <Product>
                <symbol>{symbol}</symbol>
                <securityType>EQ</securityType>
            </Product>
            <orderAction>{order_action}</orderAction>
            <quantityType>QUANTITY</quantityType>
            <quantity>{quantity}</quantity>
        </Instrument>
    </Order>
</{root_tag}>
""".strip()
        logger.debug(f"Generated Equity XML ({request_type}): {xml}")
        return xml

    def preview_equity_order(self, account_id_key: str, payload: Dict) -> Dict:
        """
        Preview an equity (stock) order using generated XML.
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "preview": {}}

            xml = self._build_equity_order_xml(payload)
            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/preview.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            
            logger.info("=" * 80)
            logger.info("PREVIEWING EQUITY ORDER")
            logger.info("=" * 80)
            logger.info(f"URL: {url}")
            logger.info(f"Payload received: {payload}")
            logger.info(f"Generated XML:\n{xml}")
            logger.info("-" * 80)
            
            response = self.session.post(url, header_auth=True, headers=headers, data=xml)
            
            logger.info(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                preview = data.get("PreviewOrderResponse", {})
                
                # Log PreviewId for debugging
                preview_ids = preview.get("PreviewIds", [])
                if preview_ids and len(preview_ids) > 0:
                    # E*TRADE API uses "PreviewId" (capital P) inside PreviewIds array
                    preview_id = preview_ids[0].get("PreviewId") or preview_ids[0].get("previewId")  # Support both formats
                    logger.info(f"✅ Preview successful - PreviewId: {preview_id}")
                else:
                    logger.warning("⚠️ No PreviewIds found in preview response!")
                    logger.debug(f"Preview response structure: {preview}")
                
                logger.info("=" * 80)
                return {"success": True, "preview": preview}
            else:
                err = "Failed to preview equity order"
                raw_response = response.text
                logger.error("=" * 80)
                logger.error("❌ E*TRADE PREVIEW ERROR")
                logger.error("=" * 80)
                logger.error(f"Status Code: {response.status_code}")
                logger.error(f"Raw Response (first 1000 chars):\n{raw_response[:1000]}")
                
                try:
                    err_json = response.json()
                    logger.error(f"Parsed JSON Response:\n{err_json}")
                    
                    if "Error" in err_json:
                        if "message" in err_json["Error"]:
                            err = err_json["Error"]["message"]
                            logger.error(f"Error Message: {err}")
                        if "code" in err_json["Error"]:
                            logger.error(f"Error Code: {err_json['Error']['code']}")
                    elif "PreviewOrderResponse" in err_json and "Messages" in err_json["PreviewOrderResponse"]:
                        messages = err_json["PreviewOrderResponse"]["Messages"]
                        if "Message" in messages:
                            msg_list = messages["Message"] if isinstance(messages["Message"], list) else [messages["Message"]]
                            err = "; ".join([m.get("description", str(m)) for m in msg_list if m])
                            logger.error(f"Preview Messages: {msg_list}")
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response text: {raw_response[:500]}")
                    err = f"Failed to preview equity order: {raw_response[:200]}"
                
                logger.error("=" * 80)
                return {"success": False, "error": err, "preview": {}, "status_code": response.status_code, "debug_info": {"raw_response": raw_response[:500]}}
        except Exception as e:
            logger.error(f"Exception in preview_equity_order: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Exception: {str(e)}", "preview": {}}

    def place_equity_order(self, account_id_key: str, payload: Dict) -> Dict:
        """
        Place an equity (stock) order using generated XML.
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "order": {}}

            # Check if PreviewId is provided
            # Note: E*TRADE API is case-sensitive, must use "PreviewId" (capital P)
            preview_id = payload.get("PreviewId") or payload.get("previewId") or payload.get("preview_id")  # Support multiple formats for backward compatibility
            if preview_id:
                logger.info(f"✅ PreviewId provided: {preview_id}")
            else:
                logger.warning("⚠️ No PreviewId provided! E*TRADE may reject this order.")
            
            xml = self._build_equity_order_xml(payload, order_type="EQ", request_type="Place")
            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/place.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            
            logger.info("=" * 80)
            logger.info("PLACING EQUITY ORDER")
            logger.info("=" * 80)
            logger.info(f"Endpoint: /orders/place.json")
            logger.info(f"HTTP Method: POST")
            logger.info(f"PreviewId: {preview_id or 'NOT PROVIDED'}")
            logger.info(f"URL: {url}")
            logger.info(f"Payload received: {payload}")
            logger.info(f"Generated XML:\n{xml}")
            logger.info("=" * 80)
            
            response = self.session.post(url, header_auth=True, headers=headers, data=xml)
            
            logger.info(f"Response Status: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                order_resp = data.get("PlaceOrderResponse", {})
                logger.info(f"✅ Order placed successfully: {order_resp}")
                logger.info("=" * 80)
                return {"success": True, "order": order_resp}
            else:
                err = "Failed to place equity order"
                raw_response = response.text
                logger.error("=" * 80)
                logger.error("❌ E*TRADE ERROR RESPONSE")
                logger.error("=" * 80)
                logger.error(f"Status Code: {response.status_code}")
                logger.error(f"Raw Response (first 1000 chars):\n{raw_response[:1000]}")
                
                try:
                    err_json = response.json()
                    logger.error(f"Parsed JSON Response:\n{err_json}")
                    
                    if "Error" in err_json:
                        if "message" in err_json["Error"]:
                            err = err_json["Error"]["message"]
                            logger.error(f"Error Message: {err}")
                        if "code" in err_json["Error"]:
                            logger.error(f"Error Code: {err_json['Error']['code']}")
                    elif "PlaceOrderResponse" in err_json:
                        if "Messages" in err_json["PlaceOrderResponse"]:
                            messages = err_json["PlaceOrderResponse"]["Messages"]
                            if "Message" in messages:
                                msg_list = messages["Message"] if isinstance(messages["Message"], list) else [messages["Message"]]
                                err = "; ".join([m.get("description", str(m)) for m in msg_list if m])
                                logger.error(f"Order Messages: {msg_list}")
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response text: {raw_response[:500]}")
                    err = f"Failed to place equity order: {raw_response[:200]}"
                
                logger.error("=" * 80)
                return {"success": False, "error": err, "order": {}, "status_code": response.status_code, "debug_info": {"raw_response": raw_response[:500]}}
        except Exception as e:
            logger.error(f"Exception in place_equity_order: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Exception: {str(e)}", "order": {}}

    def preview_options_order(self, account_id_key: str, payload: Dict) -> Dict:
        """
        Preview a single-leg options order using generated XML.
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "preview": {}}

            xml = self._build_option_order_xml(payload)
            logger.debug(f"Options Order XML: {xml}")
            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/preview.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            response = self.session.post(url, header_auth=True, headers=headers, data=xml)
            if response.status_code == 200:
                data = response.json()
                preview = data.get("PreviewOrderResponse", {})
                return {"success": True, "preview": preview}
            else:
                err = "Failed to preview options order"
                try:
                    err_json = response.json()
                    logger.debug(f"E*TRADE Error Response: {err_json}")
                    if "Error" in err_json and "message" in err_json["Error"]:
                        err = err_json["Error"]["message"]
                    elif "PreviewOrderResponse" in err_json and "Messages" in err_json["PreviewOrderResponse"]:
                        messages = err_json["PreviewOrderResponse"]["Messages"]
                        if "Message" in messages:
                            msg_list = messages["Message"] if isinstance(messages["Message"], list) else [messages["Message"]]
                            err = "; ".join([m.get("description", str(m)) for m in msg_list if m])
                except Exception as e:
                    logger.debug(f"Error parsing response: {e}, Raw: {response.text[:500]}")
                    err = f"Failed to preview options order: {response.text[:200]}"
                return {"success": False, "error": err, "preview": {}, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "preview": {}}

    def place_options_order(self, account_id_key: str, payload: Dict) -> Dict:
        """
        Place a single-leg options order using generated XML.
        """
        try:
            if not self.is_authenticated or not self.session:
                return {"success": False, "error": "Not authenticated", "order": {}}

            # Check if PreviewId is provided
            # Note: E*TRADE API is case-sensitive, must use "PreviewId" (capital P)
            preview_id = payload.get("PreviewId") or payload.get("previewId") or payload.get("preview_id")  # Support multiple formats for backward compatibility
            if preview_id:
                logger.info(f"✅ PreviewId provided for options order: {preview_id}")
            else:
                logger.warning("⚠️ No PreviewId provided for options order! E*TRADE may reject this order.")

            xml = self._build_option_order_xml(payload, order_type="OPTN", request_type="Place")
            url = f"{self.base_url}/v1/accounts/{account_id_key}/orders/place.json"
            headers = {"Content-Type": "application/xml", "consumerKey": self.consumer_key}
            
            logger.info("=" * 80)
            logger.info("PLACING OPTIONS ORDER")
            logger.info("=" * 80)
            logger.info(f"Endpoint: /orders/place.json")
            logger.info(f"HTTP Method: POST")
            logger.info(f"PreviewId: {preview_id or 'NOT PROVIDED'}")
            logger.info(f"URL: {url}")
            logger.info(f"Payload received: {payload}")
            logger.info(f"Generated XML:\n{xml}")
            logger.info("=" * 80)
            
            response = self.session.post(url, header_auth=True, headers=headers, data=xml)
            
            logger.info(f"Response Status: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            if response.status_code == 200:
                data = response.json()
                order_resp = data.get("PlaceOrderResponse", {})
                logger.info(f"✅ Options order placed successfully: {order_resp}")
                logger.info("=" * 80)
                return {"success": True, "order": order_resp}
            else:
                err = "Failed to place options order"
                raw_response = response.text
                logger.error("=" * 80)
                logger.error("❌ E*TRADE ERROR RESPONSE (OPTIONS)")
                logger.error("=" * 80)
                logger.error(f"Status Code: {response.status_code}")
                logger.error(f"Raw Response (first 1000 chars):\n{raw_response[:1000]}")
                
                try:
                    err_json = response.json()
                    logger.error(f"Parsed JSON Response:\n{err_json}")
                    
                    if "Error" in err_json:
                        if "message" in err_json["Error"]:
                            err = err_json["Error"]["message"]
                            logger.error(f"Error Message: {err}")
                        if "code" in err_json["Error"]:
                            logger.error(f"Error Code: {err_json['Error']['code']}")
                    elif "PlaceOrderResponse" in err_json:
                        if "Messages" in err_json["PlaceOrderResponse"]:
                            messages = err_json["PlaceOrderResponse"]["Messages"]
                            if "Message" in messages:
                                msg_list = messages["Message"] if isinstance(messages["Message"], list) else [messages["Message"]]
                                err = "; ".join([m.get("description", str(m)) for m in msg_list if m])
                                logger.error(f"Order Messages: {msg_list}")
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response text: {raw_response[:500]}")
                    err = f"Failed to place options order: {raw_response[:200]}"
                
                logger.error("=" * 80)
                return {"success": False, "error": err, "order": {}, "status_code": response.status_code, "debug_info": {"raw_response": raw_response[:500]}}
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}", "order": {}}

