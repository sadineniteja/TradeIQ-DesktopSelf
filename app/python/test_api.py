"""
Quick test script to verify the API is working.
Run this after starting the application with: python app.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_health():
    """Test health endpoint."""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_create_channel():
    """Test creating a channel prompt."""
    print("🏗️  Testing channel prompt creation...")
    
    data = {
        "channel_name": "test_channel",
        "training_data": [
            {
                "signal": "BUY TSLA @ 250 SL 245 TP 260",
                "date": "2025-12-03"
            },
            {
                "signal": "SELL AAPL @ 180 Stop 185 Target 170",
                "date": "2025-12-02"
            },
            {
                "signal": "Long NVDA Entry: 500 | SL: 490 | TP: 520",
                "date": "2025-12-01"
            }
        ],
        "is_update": False
    }
    
    response = requests.post(
        f"{BASE_URL}/api/channel/prompt/build",
        json=data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Channel created: {result['channel_name']}")
        print(f"Prompt preview: {result['prompt'][:200]}...")
    else:
        print(f"❌ Error: {response.json()}")
    print()

def test_send_signal():
    """Test sending a trade signal."""
    print("📤 Testing signal reception...")
    
    data = {
        "title": "test_channel",
        "content": "BUY MSFT @ 380 SL 375 TP 395"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/signal",
        json=data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    if response.status_code == 200 and result.get('success'):
        print(f"✅ Signal processed successfully!")
        print(f"Order ID: {result.get('order_id')}")
        print(f"Parsed signal: {json.dumps(result.get('parsed_signal'), indent=2)}")
    else:
        print(f"❌ Error: {result.get('error')}")
        if result.get('details'):
            print(f"Details: {result['details']}")
    print()

def test_get_channels():
    """Test getting all channels."""
    print("📡 Testing get channels...")
    response = requests.get(f"{BASE_URL}/api/channels")
    print(f"Status: {response.status_code}")
    channels = response.json().get('channels', [])
    print(f"Found {len(channels)} channel(s)")
    for channel in channels:
        print(f"  - {channel['channel_name']}")
    print()

def test_get_recent_signals():
    """Test getting recent signals."""
    print("📊 Testing get recent signals...")
    response = requests.get(f"{BASE_URL}/api/signals/recent?limit=5")
    print(f"Status: {response.status_code}")
    signals = response.json().get('signals', [])
    print(f"Found {len(signals)} recent signal(s)")
    for signal in signals:
        print(f"  - {signal['channel_name']}: {signal['status']}")
    print()

if __name__ == "__main__":
    print("="*60)
    print("TradeIQ API Test Suite")
    print("="*60)
    print()
    
    try:
        # Test health
        test_health()
        
        # Test creating a channel
        test_create_channel()
        
        # Wait a moment for the prompt to be created
        time.sleep(2)
        
        # Test getting channels
        test_get_channels()
        
        # Test sending a signal
        test_send_signal()
        
        # Wait a moment for the signal to be processed
        time.sleep(2)
        
        # Test getting recent signals
        test_get_recent_signals()
        
        print("="*60)
        print("✅ All tests completed!")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the API.")
        print("Make sure the application is running with: python app.py")
    except Exception as e:
        print(f"❌ Error: {str(e)}")




