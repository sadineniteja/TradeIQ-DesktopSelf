"""
Standalone script to test E*TRADE options order preview.
Reads credentials from database and environment variables.
"""

import os
import re
import json
import sqlite3
from rauth import OAuth1Service

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# ============================================================================
# CONFIGURATION
# ============================================================================
DB_PATH = "tradeiq.db"
SANDBOX = False  # Set to False for production, True for sandbox
# IMPORTANT: Use the osiKey from the options chain response (format: SYMBOL--YYMMDD[C/P]STRIKE)
# Example: "AAPL--251212C00280000" (from OptionChainResponse -> OptionPair -> Call/Put -> osiKey)
OPTION_SYMBOL = "AAPL--251212C00280000"  # UPDATE THIS with osiKey from your options chain

# ============================================================================

def get_db_setting(db_path, setting_key, default=None):
    """Get a setting from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (setting_key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
    except Exception as e:
        print(f"Warning: Could not read setting {setting_key}: {e}")
        return default

def parse_osikey(osikey):
    """Parse osiKey format into components.
    
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

def extract_option_type(option_symbol):
    """Extract CALL or PUT from option symbol (legacy function, kept for compatibility)."""
    parsed = parse_osikey(option_symbol)
    return parsed["callPut"]

def build_option_order_xml(option_symbol, order_action="BUY_OPEN", quantity=1, 
                          price_type="MARKET", limit_price="", order_term="GOOD_FOR_DAY",
                          market_session="REGULAR", client_order_id=None):
    """Build XML for options order preview using callPut and separate fields."""
    # Parse osiKey to get components
    parsed = parse_osikey(option_symbol)
    
    if not parsed["symbol"] or parsed["strikePrice"] is None:
        raise ValueError(f"Could not parse option symbol: {option_symbol}")
    
    if client_order_id is None:
        import time
        client_order_id = str(int(time.time() * 1000))
    
    limit_price_tag = f"<limitPrice>{limit_price}</limitPrice>" if price_type != "MARKET" and limit_price else "<limitPrice></limitPrice>"
    
    # Structure using callPut and separate fields (based on official E*TRADE API docs)
    xml = f"""<PreviewOrderRequest>
    <orderType>OPTN</orderType>
    <clientOrderId>{client_order_id}</clientOrderId>
    <Order>
        <allOrNone>false</allOrNone>
        <priceType>{price_type}</priceType>
        <orderTerm>{order_term}</orderTerm>
        <marketSession>{market_session}</marketSession>
        <stopPrice></stopPrice>
        {limit_price_tag}
        <Instrument>
            <Product>
                <symbol>{parsed["symbol"]}</symbol>
                <securityType>OPTN</securityType>
                <callPut>{parsed["callPut"]}</callPut>
                <expiryYear>{parsed["expiryYear"]}</expiryYear>
                <expiryMonth>{parsed["expiryMonth"]}</expiryMonth>
                <expiryDay>{parsed["expiryDay"]}</expiryDay>
                <strikePrice>{parsed["strikePrice"]}</strikePrice>
            </Product>
            <orderAction>{order_action}</orderAction>
            <quantityType>QUANTITY</quantityType>
            <quantity>{quantity}</quantity>
        </Instrument>
    </Order>
</PreviewOrderRequest>"""
    
    return [
        ("Structure: callPut with separate fields (Official E*TRADE format)", xml)
    ]

def do_oauth_flow(base_url, consumer_key, consumer_secret):
    """Complete OAuth flow to get access tokens."""
    print("=" * 80)
    print("Starting OAuth Flow...")
    print("=" * 80)
    print()
    
    try:
        oauth_service = OAuth1Service(
            name="etrade",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            request_token_url=f"{base_url}/oauth/request_token",
            access_token_url=f"{base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=base_url,
        )
        
        # Step 1: Get request token
        print("Step 1: Requesting authorization token...")
        request_token, request_token_secret = oauth_service.get_request_token(
            params={"oauth_callback": "oob", "format": "json"}
        )
        print(f"✓ Request token received")
        print()
        
        # Step 2: Get authorization URL
        print("Step 2: Getting authorization URL...")
        auth_url = oauth_service.authorize_url.format(consumer_key, request_token)
        print()
        print("=" * 80)
        print("ACTION REQUIRED:")
        print("=" * 80)
        print(f"1. Open this URL in your browser:")
        print()
        print(f"   {auth_url}")
        print()
        print("2. Log in and authorize the application")
        print("3. Copy the verification code from the page")
        print()
        print("=" * 80)
        print()
        
        # Step 3: Get verifier from user
        verifier = input("Enter the verification code: ").strip()
        if not verifier:
            print("❌ ERROR: Verification code is required")
            return None, None
        
        print()
        print("Step 3: Exchanging for access token...")
        
        # Step 4: Get access token
        session = oauth_service.get_auth_session(
            request_token, request_token_secret, params={"oauth_verifier": verifier}
        )
        
        access_token = session.access_token
        access_token_secret = session.access_token_secret
        
        print(f"✓ Access token received")
        print(f"✓ Access token: {access_token[:20]}...")
        print()
        
        # Save to environment
        os.environ["ETRADE_ACCESS_TOKEN"] = access_token
        os.environ["ETRADE_ACCESS_TOKEN_SECRET"] = access_token_secret
        print("✓ Tokens saved to environment")
        print()
        
        return access_token, access_token_secret
        
    except Exception as e:
        print(f"❌ OAuth flow failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def get_account_id_key(base_url, consumer_key, consumer_secret, access_token, access_token_secret):
    """Get the first account ID key from the account list."""
    try:
        oauth_service = OAuth1Service(
            name="etrade",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            request_token_url=f"{base_url}/oauth/request_token",
            access_token_url=f"{base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=base_url,
        )
        session = oauth_service.get_session((access_token, access_token_secret))
        
        url = f"{base_url}/v1/accounts/list.json"
        response = session.get(url, header_auth=True)
        
        print(f"  Account list API status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response keys: {list(data.keys())}")
            if "AccountListResponse" in data and "Accounts" in data["AccountListResponse"]:
                accounts = data["AccountListResponse"]["Accounts"].get("Account", [])
                if isinstance(accounts, dict):
                    accounts = [accounts]
                if accounts:
                    account = accounts[0]
                    account_id = account.get("accountIdKey") or account.get("accountId")
                    print(f"  Found account ID: {account_id}")
                    return account_id
                else:
                    print("  No accounts found in response")
            else:
                print(f"  Unexpected response structure: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"  Error response: {response.text[:500]}")
    except Exception as e:
        print(f"  Exception fetching account ID: {e}")
        import traceback
        traceback.print_exc()
    return None

def test_options_preview():
    """Test options order preview with different XML structures."""
    
    print("=" * 80)
    print("E*TRADE Options Order Preview Test (Standalone)")
    print("=" * 80)
    print()
    
    # Read credentials from database
    print("Reading credentials from database...")
    # Force use of SANDBOX setting from config (overrides database setting)
    use_sandbox = SANDBOX
    
    print(f"⚠️  Using {'SANDBOX' if use_sandbox else 'PRODUCTION'} environment")
    if not use_sandbox:
        print("⚠️  WARNING: You are using PRODUCTION keys - real money will be involved!")
        print()
    
    if use_sandbox:
        consumer_key = get_db_setting(DB_PATH, "etrade_sandbox_key", "")
        consumer_secret = get_db_setting(DB_PATH, "etrade_sandbox_secret", "")
    else:
        consumer_key = get_db_setting(DB_PATH, "etrade_prod_key", "")
        consumer_secret = get_db_setting(DB_PATH, "etrade_prod_secret", "")
    
    # Fallback to environment variables
    if not consumer_key:
        consumer_key = os.getenv("ETRADE_CONSUMER_KEY", "")
    if not consumer_secret:
        consumer_secret = os.getenv("ETRADE_CONSUMER_SECRET", "")
    
    # Get access tokens from environment
    # Note: Access tokens are environment-specific (sandbox tokens don't work with production)
    access_token = os.getenv("ETRADE_ACCESS_TOKEN", "")
    access_token_secret = os.getenv("ETRADE_ACCESS_TOKEN_SECRET", "")
    
    base_url = "https://apisb.etrade.com" if use_sandbox else "https://api.etrade.com"
    
    # Validate credentials
    if not consumer_key:
        env_name = "sandbox" if use_sandbox else "production"
        print(f"❌ ERROR: {env_name.capitalize()} consumer key not found in database or environment")
        setting_name = "etrade_sandbox_key" if use_sandbox else "etrade_prod_key"
        print(f"   Please set {setting_name} in database, or ETRADE_CONSUMER_KEY in environment")
        return
    
    if not consumer_secret:
        env_name = "sandbox" if use_sandbox else "production"
        print(f"❌ ERROR: {env_name.capitalize()} consumer secret not found in database or environment")
        setting_name = "etrade_sandbox_secret" if use_sandbox else "etrade_prod_secret"
        print(f"   Please set {setting_name} in database, or ETRADE_CONSUMER_SECRET in environment")
        return
    
    # If no access tokens, run OAuth flow
    if not access_token or not access_token_secret:
        env_name = "sandbox" if use_sandbox else "production"
        print(f"⚠️  {env_name.capitalize()} access tokens not found in environment")
        print(f"   Starting OAuth flow for {env_name} environment...")
        print()
        
        access_token, access_token_secret = do_oauth_flow(base_url, consumer_key, consumer_secret)
        
        if not access_token or not access_token_secret:
            print("❌ ERROR: Failed to complete OAuth flow")
            return
    else:
        # Test if tokens are valid by trying to get account list
        print("Testing access tokens...")
        test_oauth = OAuth1Service(
            name="etrade",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            request_token_url=f"{base_url}/oauth/request_token",
            access_token_url=f"{base_url}/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url=base_url,
        )
        test_session = test_oauth.get_session((access_token, access_token_secret))
        test_url = f"{base_url}/v1/accounts/list.json"
        test_response = test_session.get(test_url, header_auth=True)
        
        if test_response.status_code == 401:
            env_name = "sandbox" if use_sandbox else "production"
            print(f"⚠️  Existing tokens are invalid or expired for {env_name} environment")
            print(f"   Starting OAuth flow to get new tokens...")
            print()
            
            access_token, access_token_secret = do_oauth_flow(base_url, consumer_key, consumer_secret)
            
            if not access_token or not access_token_secret:
                print("❌ ERROR: Failed to complete OAuth flow")
                return
        else:
            print("✓ Access tokens are valid")
            print()
    
    print(f"✓ Consumer Key: {consumer_key[:10]}...")
    print(f"✓ Consumer Secret: {'*' * 10}...")
    print(f"✓ Access Token: {access_token[:10] if access_token else 'NOT SET'}...")
    env_name = 'SANDBOX' if use_sandbox else 'PRODUCTION'
    print(f"✓ Environment: {env_name}")
    if not use_sandbox:
        print("⚠️  PRODUCTION MODE - Real trading environment!")
    print()
    
    # Get account ID
    print("Fetching account ID...")
    account_id_key = get_account_id_key(base_url, consumer_key, consumer_secret, access_token, access_token_secret)
    
    if not account_id_key:
        print()
        print("⚠️  Could not automatically fetch account ID")
        print("   Trying to read from environment variable...")
        account_id_key = os.getenv("ETRADE_ACCOUNT_ID_KEY", "")
        
        if not account_id_key:
            print("   Please enter your account ID key manually (or set ETRADE_ACCOUNT_ID_KEY env var)")
            print("   Example: rvsTzrZpNJ524B5rB8mVJw")
            account_id_key = input("   Account ID Key: ").strip()
            
            if not account_id_key:
                print("❌ ERROR: Account ID key is required")
                return
    
    print(f"✓ Account ID: {account_id_key}")
    print(f"✓ Option Symbol (osiKey): {OPTION_SYMBOL}")
    
    # Parse and display components
    parsed = parse_osikey(OPTION_SYMBOL)
    if parsed["symbol"]:
        print(f"✓ Parsed Components:")
        print(f"    Symbol: {parsed['symbol']}")
        print(f"    Expiry: {parsed['expiryYear']}-{parsed['expiryMonth']:02d}-{parsed['expiryDay']:02d}")
        print(f"    Type: {parsed['callPut']}")
        print(f"    Strike: {parsed['strikePrice']}")
    else:
        print(f"⚠️  Warning: Could not parse option symbol properly")
    print()
    print("ℹ️  NOTE: Using 'callPut' field with separate expiry/strike fields (Official E*TRADE format)")
    print()
    
    # Create OAuth service
    oauth_service = OAuth1Service(
        name="etrade",
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        request_token_url=f"{base_url}/oauth/request_token",
        access_token_url=f"{base_url}/oauth/access_token",
        authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
        base_url=base_url,
    )
    
    # Create authenticated session
    session = oauth_service.get_session((access_token, access_token_secret))
    
    print("✓ Authenticated session created")
    print()
    
    # Test different XML structures
    xml_structures = build_option_order_xml(
        option_symbol=OPTION_SYMBOL,
        order_action="BUY_OPEN",
        quantity=1,
        price_type="MARKET",
        order_term="GOOD_FOR_DAY"
    )
    
    url = f"{base_url}/v1/accounts/{account_id_key}/orders/preview.json"
    headers = {"Content-Type": "application/xml", "consumerKey": consumer_key}
    
    for structure_name, xml in xml_structures:
        print("=" * 80)
        print(f"Testing: {structure_name}")
        print("=" * 80)
        print()
        print("XML being sent:")
        print("-" * 80)
        print(xml)
        print("-" * 80)
        print()
        
        try:
            response = session.post(url, header_auth=True, headers=headers, data=xml)
            
            print(f"Response Status: {response.status_code}")
            print()
            
            if response.status_code == 200:
                print("✅ SUCCESS!")
                data = response.json()
                print("Response:")
                print(json.dumps(data, indent=2))
                print()
                print(f"✓ This XML structure works: {structure_name}")
                return  # Exit on first success
            else:
                print("❌ FAILED")
                print(f"Response Headers: {dict(response.headers)}")
                print()
                try:
                    error_data = response.json()
                    print("Error Response (JSON):")
                    print(json.dumps(error_data, indent=2))
                except:
                    print("Error Response (Text):")
                    print(response.text[:1000])
                print()
                
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            print()
    
    print("=" * 80)
    print("All XML structures failed. Check the error messages above.")
    print("=" * 80)

if __name__ == "__main__":
    test_options_preview()
