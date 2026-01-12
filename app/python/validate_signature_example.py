"""
Validation script to verify signature generation matches the official Webull API documentation example.
Reference: https://developer.webull.com/apis/docs/authentication/signature

This script uses the EXACT example from the documentation to verify our implementation.
"""

import hashlib
import hmac
import base64
import urllib.parse

# Example values from Webull API documentation
EXAMPLE_URI = "/trade/place_order"
EXAMPLE_QUERY_PARAMS = {
    "a1": "webull",
    "a2": "123",
    "a3": "xxx",
    "q1": "yyy"
}
EXAMPLE_HEADERS_DICT = {
    "x-app-key": "776da210ab4a452795d74e726ebd74b6",
    "x-timestamp": "2022-01-04T03:55:31Z",
    "x-signature-version": "1.0",
    "x-signature-algorithm": "HMAC-SHA1",
    "x-signature-nonce": "48ef5afed43d4d91ae514aaeafbc29ba",
    "host": "api.webull.com"
}
EXAMPLE_BODY = '{"k1":123,"k2":"this is the api request body","k3":true,"k4":{"foo":[1,2]}}'
EXAMPLE_APP_SECRET = "0f50a2e853334a9aae1a783bee120c1f"
EXPECTED_SIGNATURE = "kvlS6opdZDhEBo5jq40nHYXaLvM="


def generate_signature_validation():
    """Generate signature using the exact example from documentation."""
    print("="*80)
    print("🔍 Validating Signature Generation Against Official Documentation")
    print("="*80)
    
    # Step 1: Combine query params and headers into a map
    params_map = {}
    
    # Add query params
    for k, v in EXAMPLE_QUERY_PARAMS.items():
        params_map[k] = str(v)
    
    # Add signature headers
    for header in ['x-app-key', 'x-signature-algorithm', 'x-signature-version', 
                  'x-signature-nonce', 'x-timestamp', 'host']:
        if header in EXAMPLE_HEADERS_DICT:
            params_map[header] = str(EXAMPLE_HEADERS_DICT[header])
    
    # Step 2: Sort by key and construct str1
    sorted_items = sorted(params_map.items())
    str1 = '&'.join([f"{k}={v}" for k, v in sorted_items])
    
    print(f"\n📋 Step 1-2: Sorted parameters and constructed str1")
    print(f"   Expected order: a1, a2, a3, host, q1, x-app-key, x-signature-algorithm, x-signature-nonce, x-signature-version, x-timestamp")
    print(f"   str1: {str1}")
    
    # Verify expected str1 from documentation
    expected_str1 = "a1=webull&a2=123&a3=xxx&host=api.webull.com&q1=yyy&x-app-key=776da210ab4a452795d74e726ebd74b6&x-signature-algorithm=HMAC-SHA1&x-signature-nonce=48ef5afed43d4d91ae514aaeafbc29ba&x-signature-version=1.0&x-timestamp=2022-01-04T03:55:31Z"
    
    if str1 == expected_str1:
        print(f"   ✅ str1 matches documentation!")
    else:
        print(f"   ❌ str1 mismatch!")
        print(f"   Expected: {expected_str1}")
        print(f"   Got:      {str1}")
        return False
    
    # Step 3: Calculate body MD5 and convert to uppercase
    body_md5 = hashlib.md5(EXAMPLE_BODY.encode('utf-8')).hexdigest().upper()
    str2 = body_md5
    
    print(f"\n📋 Step 3: Calculate body MD5 (str2)")
    print(f"   Body: {EXAMPLE_BODY}")
    print(f"   str2 (MD5 uppercase): {str2}")
    
    expected_str2 = "E296C96787E1A309691CEF3692F5EEDD"
    if str2 == expected_str2:
        print(f"   ✅ str2 matches documentation!")
    else:
        print(f"   ❌ str2 mismatch!")
        print(f"   Expected: {expected_str2}")
        print(f"   Got:      {str2}")
        return False
    
    # Step 4: Join path&str1&str2 to create str3
    str3 = f"{EXAMPLE_URI}&{str1}&{str2}"
    
    print(f"\n📋 Step 4: Construct str3")
    print(f"   str3: {str3}")
    
    expected_str3 = "/trade/place_order&a1=webull&a2=123&a3=xxx&host=api.webull.com&q1=yyy&x-app-key=776da210ab4a452795d74e726ebd74b6&x-signature-algorithm=HMAC-SHA1&x-signature-nonce=48ef5afed43d4d91ae514aaeafbc29ba&x-signature-version=1.0&x-timestamp=2022-01-04T03:55:31Z&E296C96787E1A309691CEF3692F5EEDD"
    
    if str3 == expected_str3:
        print(f"   ✅ str3 matches documentation!")
    else:
        print(f"   ❌ str3 mismatch!")
        print(f"   Expected: {expected_str3}")
        print(f"   Got:      {str3}")
        return False
    
    # Step 5: URL encode str3
    encoded_string = urllib.parse.quote(str3, safe='')
    
    print(f"\n📋 Step 5: URL encode str3")
    print(f"   encoded_string: {encoded_string[:100]}... (truncated)")
    
    expected_encoded = "%2Ftrade%2Fplace_order%26a1%3Dwebull%26a2%3D123%26a3%3Dxxx%26host%3Dapi.webull.com%26q1%3Dyyy%26x-app-key%3D776da210ab4a452795d74e726ebd74b6%26x-signature-algorithm%3DHMAC-SHA1%26x-signature-nonce%3D48ef5afed43d4d91ae514aaeafbc29ba%26x-signature-version%3D1.0%26x-timestamp%3D2022-01-04T03%3A55%3A31Z%26E296C96787E1A309691CEF3692F5EEDD"
    
    if encoded_string == expected_encoded:
        print(f"   ✅ encoded_string matches documentation!")
    else:
        print(f"   ❌ encoded_string mismatch!")
        print(f"   Expected: {expected_encoded}")
        print(f"   Got:      {encoded_string}")
        return False
    
    # Step 6: Append "&" to App Secret
    app_secret_key = EXAMPLE_APP_SECRET + "&"
    
    print(f"\n📋 Step 6: Construct app_secret")
    print(f"   app_secret: {app_secret_key}")
    
    expected_app_secret = "0f50a2e853334a9aae1a783bee120c1f&"
    if app_secret_key == expected_app_secret:
        print(f"   ✅ app_secret matches documentation!")
    else:
        print(f"   ❌ app_secret mismatch!")
        return False
    
    # Step 7: Generate signature
    signature_bytes = hmac.new(
        app_secret_key.encode('utf-8'),
        encoded_string.encode('utf-8'),
        hashlib.sha1
    ).digest()
    
    signature = base64.b64encode(signature_bytes).decode('utf-8')
    
    print(f"\n📋 Step 7: Generate signature")
    print(f"   signature: {signature}")
    print(f"   Expected:  {EXPECTED_SIGNATURE}")
    
    if signature == EXPECTED_SIGNATURE:
        print(f"\n✅✅✅ SIGNATURE MATCHES DOCUMENTATION EXACTLY! ✅✅✅")
        return True
    else:
        print(f"\n❌ Signature mismatch!")
        print(f"   Expected: {EXPECTED_SIGNATURE}")
        print(f"   Got:      {signature}")
        return False


if __name__ == "__main__":
    success = generate_signature_validation()
    
    print("\n" + "="*80)
    if success:
        print("✅ VALIDATION PASSED: Implementation matches official documentation!")
    else:
        print("❌ VALIDATION FAILED: Implementation does not match documentation!")
    print("="*80)

