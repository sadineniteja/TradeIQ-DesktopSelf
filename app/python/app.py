"""
Main Flask application for TradeIQ.
This application receives trade signals, processes them using AI,
and executes trades via Webull API.
"""

import os
import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import json
import re
import base64
import time
import requests
from datetime import datetime
from typing import Dict, List
from openai import OpenAI

# Try to import cryptography
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    print("⚠ Cryptography not available - VAPID key validation will be disabled")
    CRYPTOGRAPHY_AVAILABLE = False
    serialization = None
    ec = None
    default_backend = None

from database import Database
from prompt_builder import PromptBuilder
from signal_processor import SignalProcessor
from etrade_api import EtradeAPI
from discord_api import DiscordAPI
from x_api import XAPI
from x_signal_processor import XSignalProcessor
from grok_api import GrokAPI
from alphavantage_api import AlphaVantageAPI
from signals import Signals
from trade_executor import TradeExecutor
from tradingview_executor import TradingViewExecutor
from push_notifications import PushNotificationManager

# Determine base directory and paths for Android vs desktop BEFORE loading .env
# Debug logging disabled to reduce logcat noise
DEBUG_LOGGING = False  # Set to True to enable verbose debug output

if DEBUG_LOGGING:
    print(f"DEBUG: ANDROID_ASSETS = {os.environ.get('ANDROID_ASSETS')}")
    print(f"DEBUG: ANDROID_APP_FILES_DIR = {os.environ.get('ANDROID_APP_FILES_DIR')}")

# Check if running on Android by looking for Chaquopy or Android-specific paths
is_android = False
try:
    # Try to detect Android by checking for Chaquopy
    import java
    is_android = True
    if DEBUG_LOGGING:
        print("DEBUG: Detected Android via Chaquopy")
except ImportError:
    # Check for Android-specific environment or paths
    if os.path.exists('/data/data') or os.environ.get('ANDROID_DATA'):
        is_android = True
        if DEBUG_LOGGING:
            print("DEBUG: Detected Android via filesystem check")
    else:
        if DEBUG_LOGGING:
            print("DEBUG: Running on desktop")

if is_android:
    # Running on Android - use app's internal storage paths
    # Chaquopy typically runs from the app's files directory
    app_files_dir = '/data/user/0/com.tradeiq.app/files'
    assets_dir = os.path.join(app_files_dir, 'assets')

    BASE_DIR = assets_dir
    TEMPLATE_FOLDER = os.path.join(assets_dir, 'templates')
    STATIC_FOLDER = os.path.join(assets_dir, 'static')
    # Database path in Android app's internal storage
    db_path = os.path.join(app_files_dir, 'tradeiq.db')
    # .env file path in Android app's internal storage (writable location)
    env_file_path = os.path.join(app_files_dir, '.env')
    if DEBUG_LOGGING:
        print(f"DEBUG: Android mode - db_path = {db_path}")
        print(f"DEBUG: TEMPLATE_FOLDER = {TEMPLATE_FOLDER}")
        print(f"DEBUG: Template exists: {os.path.exists(os.path.join(TEMPLATE_FOLDER, 'index.html'))}")
        if os.path.exists(TEMPLATE_FOLDER):
            print(f"DEBUG: Template dir contents: {os.listdir(TEMPLATE_FOLDER)}")
        else:
            print(f"DEBUG: Template directory does not exist: {TEMPLATE_FOLDER}")
else:
    # Running on desktop
    # Get the app directory (parent of python directory)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    APP_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
    TEMPLATE_FOLDER = os.path.join(APP_ROOT, 'templates')
    STATIC_FOLDER = os.path.join(APP_ROOT, 'static')
    # Database in app root directory
    db_path = os.path.join(APP_ROOT, 'tradeiq.db')
    # .env file path in desktop mode (app root directory)
    env_file_path = os.path.join(APP_ROOT, '.env')
    if DEBUG_LOGGING:
        print(f"DEBUG: Desktop mode - db_path = {db_path}")
        print(f"DEBUG: TEMPLATE_FOLDER = {TEMPLATE_FOLDER}")
        print(f"DEBUG: Template exists: {os.path.exists(os.path.join(TEMPLATE_FOLDER, 'index.html'))}")
        if os.path.exists(TEMPLATE_FOLDER):
            print(f"DEBUG: Template dir contents: {os.listdir(TEMPLATE_FOLDER)}")
        else:
            print(f"DEBUG: Template directory does not exist: {TEMPLATE_FOLDER}")

# Load environment variables from the correct location
if DEBUG_LOGGING:
    print(f"DEBUG: Loading .env from: {env_file_path}")
load_dotenv(dotenv_path=env_file_path)
if DEBUG_LOGGING:
    if os.path.exists(env_file_path):
        print(f"DEBUG: .env file size: {os.path.getsize(env_file_path)} bytes")

# Initialize Flask app with Android-compatible paths
# Ensure template folder is absolute
TEMPLATE_FOLDER_ABS = os.path.abspath(TEMPLATE_FOLDER) if TEMPLATE_FOLDER else None
STATIC_FOLDER_ABS = os.path.abspath(STATIC_FOLDER) if STATIC_FOLDER else None

app = Flask(__name__, template_folder=TEMPLATE_FOLDER_ABS, static_folder=STATIC_FOLDER_ABS)
CORS(app)

# Force Flask to use absolute paths by updating template_folder and Jinja2 loader
if TEMPLATE_FOLDER_ABS:
    app.template_folder = TEMPLATE_FOLDER_ABS
    # Set the FileSystemLoader directly on jinja_env.loader to bypass DispatchingJinjaLoader
    from jinja2 import FileSystemLoader
    app.jinja_loader = FileSystemLoader(TEMPLATE_FOLDER_ABS)
    app.jinja_env.loader = app.jinja_loader  # Direct assignment, bypass DispatchingJinjaLoader
    
    # Debug: Verify loader searchpath (only if DEBUG_LOGGING enabled)
    if DEBUG_LOGGING:
        if hasattr(app.jinja_loader, 'searchpath'):
            print(f"DEBUG: Jinja2 loader searchpath = {app.jinja_loader.searchpath}")
        print(f"DEBUG: Jinja2 env loader type = {type(app.jinja_env.loader)}")
        
        # Debug: Test if FileSystemLoader can actually read the file
        template_path = os.path.join(TEMPLATE_FOLDER_ABS, 'index.html')
        print(f"DEBUG: Testing file read: {template_path}")
        print(f"DEBUG: os.path.isfile: {os.path.isfile(template_path)}")
        print(f"DEBUG: os.access(read): {os.access(template_path, os.R_OK)}")
        try:
            with open(template_path, 'r') as f:
                content = f.read()
                print(f"DEBUG: File readable, length: {len(content)} bytes")
        except Exception as e:
            print(f"DEBUG: File read error: {e}")
        
        # Debug: Test FileSystemLoader.get_source directly
        try:
            source, filename, uptodate = app.jinja_loader.get_source(app.jinja_env, 'index.html')
            print(f"DEBUG: FileSystemLoader.get_source SUCCESS: {filename}")
            print(f"DEBUG: Source length: {len(source)} bytes")
        except Exception as e:
            print(f"DEBUG: FileSystemLoader.get_source FAILED: {e}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")

# Debug: Verify Flask's template folder (only if DEBUG_LOGGING enabled)
if DEBUG_LOGGING:
    print(f"DEBUG: Flask template_folder = {app.template_folder}")
    print(f"DEBUG: Flask template_folder absolute = {os.path.abspath(app.template_folder) if app.template_folder else 'None'}")
    if app.template_folder:
        template_path = os.path.join(app.template_folder, 'index.html')
        print(f"DEBUG: Flask can see template: {os.path.exists(template_path)}")
        print(f"DEBUG: Flask template path checked: {template_path}")
        if os.path.exists(app.template_folder):
            print(f"DEBUG: Flask template dir contents: {os.listdir(app.template_folder)}")
        else:
            print(f"DEBUG: Flask template directory does not exist: {app.template_folder}")

# Initialize components
# Ensure database directory exists
db_dir = os.path.dirname(db_path)
if DEBUG_LOGGING:
    print(f"DEBUG: Creating database directory: {db_dir}")
    print(f"DEBUG: Database path: {db_path}")
try:
    os.makedirs(db_dir, exist_ok=True)
    if DEBUG_LOGGING:
        print(f"DEBUG: Directory created successfully: {os.path.exists(db_dir)}")
        print(f"DEBUG: Directory contents: {os.listdir(db_dir) if os.path.exists(db_dir) else 'N/A'}")
except Exception as e:
    if DEBUG_LOGGING:
        print(f"DEBUG: Directory creation failed: {e}")

db = Database(db_path=db_path)
signals = Signals(db=db)

# Get API keys and model configurations from environment
openai_api_key = os.getenv('OPENAI_API_KEY')
execution_model = os.getenv('EXECUTION_MODEL', 'gpt-4-turbo-preview')
builder_model = os.getenv('BUILDER_MODEL', 'gpt-4-turbo-preview')

# Initialize AI components
if openai_api_key:
    prompt_builder = PromptBuilder(api_key=openai_api_key, model=builder_model)
    signal_processor = SignalProcessor(api_key=openai_api_key, model=execution_model)
else:
    prompt_builder = None
    signal_processor = None
    print("⚠ OpenAI API key not found. AI features will be disabled.")

# SnapTrade API - uses proxy endpoints, no direct API instance needed
# When SnapTrade is selected in executor, it will use the proxy endpoints
snaptrade_api = None

# Initialize E*TRADE API (will load credentials from database if available)
etrade_api = EtradeAPI(db=db)

# Initialize Trade Executor
trade_executor = TradeExecutor(snaptrade_api=snaptrade_api, etrade_api=etrade_api, db=db)

# Initialize TradingView Executor
tradingview_executor = TradingViewExecutor(snaptrade_api=snaptrade_api, etrade_api=etrade_api, db=db)

# Initialize Discord API
discord_api = DiscordAPI(db=db)

# Initialize X (Twitter) API
x_api = XAPI(db=db)

# Initialize Alpha Vantage API (for stock prices)
alphavantage_api = AlphaVantageAPI(db=db)
# Set API key if not already configured
if not alphavantage_api.is_enabled():
    alphavantage_api.save_config("ODPB7JT0ZHFU12MS")

# Initialize Grok API (with Alpha Vantage for stock prices)
grok_api = GrokAPI(db=db, alphavantage_api=alphavantage_api)

# Initialize X Signal Processor (with Grok API for context-aware generation)
x_signal_processor = XSignalProcessor(db=db, grok_api=grok_api)

# Initialize Push Notification Manager
push_manager = PushNotificationManager(db=db)

# Helper function to check if a channel is in channel management
def is_channel_management_channel(channel_name: str) -> bool:
    """
    Check if a channel is part of channel management.
    Channel Management includes all channels except special channels like 'x', 'TradingView', 'UNMATCHED'.
    This includes "Master Channel", "remz 100k", "remz alerts", and any other channels.
    
    Args:
        channel_name: Name of the channel to check
        
    Returns:
        True if channel is in channel management, False otherwise
    """
    if not channel_name or not channel_name.strip():
        return False
    
    channel_name = channel_name.strip()
    
    # Exclude special channels
    excluded_channels = {'x', 'TradingView', 'UNMATCHED'}
    if channel_name in excluded_channels:
        return False
    
    # All other channels are considered channel management channels
    # This includes "Master Channel", "remz 100k", "remz alerts", and any other channels
    return True

# Helper function to get all channel management channel names
def get_channel_management_channels() -> List[str]:
    """
    Get all channel names that have signals (from trade_signals table).
    Excludes special channels like 'x', 'TradingView', 'UNMATCHED'.
    This includes "Master Channel", "remz 100k", "remz alerts", and any other channels that have signals.
    
    Returns:
        List of channel names
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get all unique channel names from trade_signals table
        cursor.execute("""
            SELECT DISTINCT channel_name 
            FROM trade_signals 
            WHERE channel_name IS NOT NULL 
            AND channel_name != ''
            AND channel_name NOT IN ('x', 'TradingView', 'UNMATCHED')
            ORDER BY channel_name
        """)
        
        channels = [row[0] for row in cursor.fetchall()]
        conn.close()
        return channels
    except Exception as e:
        print(f"Error getting channel management channels: {e}")
        return []


def estimate_tokens(text):
    """
    Estimate token count for a text string.
    Uses a simple approximation: ~4 characters per token for English text.
    For more accurate counts, tiktoken could be used, but this is a good approximation.
    """
    if not text:
        return 0
    # Rough approximation: 1 token ≈ 4 characters for English text
    # This is a conservative estimate (actual is usually 3-4 chars per token)
    return len(text) // 4


def parse_tradingview_signal(message: str) -> Dict:
    """
    Parse TradingView signal format manually (no AI).
    Format: "EMA Buy Signal for SPY at price: 678.99"
    or: "EMA Sell Signal for AAPL at price: 150.50"
    
    Extracts:
    - ticker/symbol (e.g., SPY, AAPL)
    - action (Buy or Sell)
    - price (e.g., 678.99)
    
    Args:
        message: The signal message from TradingView
        
    Returns:
        Dict with success status and parsed data or error
    """
    import re
    
    if not message:
        return {"success": False, "error": "Empty message", "data": {}}
    
    try:
        # Pattern to match: "EMA Buy Signal for SPY at price: 678.99"
        # or variations like "Buy Signal for SPY at price: 678.99"
        # or "Sell Signal for AAPL at price: 150.50"
        
        # Extract action (Buy or Sell) - case insensitive
        action_match = re.search(r'\b(Buy|Sell)\b', message, re.IGNORECASE)
        action = action_match.group(1).upper() if action_match else None
        
        # Extract ticker - look for "for TICKER" pattern
        # Ticker can be 1-5 uppercase letters (e.g., SPY, AAPL, TSLA)
        ticker_match = re.search(r'\bfor\s+([A-Z]{1,5})\b', message, re.IGNORECASE)
        if not ticker_match:
            # Try alternative: ticker might be before "at price"
            ticker_match = re.search(r'\b([A-Z]{1,5})\s+at\s+price', message, re.IGNORECASE)
        if not ticker_match:
            # Try: find uppercase word before "at price" or after "for"
            ticker_match = re.search(r'(?:for\s+|^)([A-Z]{1,5})(?:\s+at\s+price|\s+at\s+|$)', message, re.IGNORECASE)
        if not ticker_match:
            # Last resort: find any 1-5 letter uppercase word in the message
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', message)
        ticker = ticker_match.group(1).upper() if ticker_match else None
        
        # Extract price - look for "price: 678.99" or "price 678.99"
        price_match = re.search(r'price[:\s]+([\d]+\.?\d*)', message, re.IGNORECASE)
        if not price_match:
            # Try to find any decimal number at the end
            price_match = re.search(r'([\d]+\.?\d*)\s*$', message)
        price = float(price_match.group(1)) if price_match else None
        
        # Validate extracted data
        if not action:
            return {"success": False, "error": "Could not extract action (Buy/Sell)", "data": {}}
        if not ticker:
            return {"success": False, "error": "Could not extract ticker/symbol", "data": {}}
        if price is None:
            return {"success": False, "error": "Could not extract price", "data": {}}
        
        parsed_data = {
            "symbol": ticker,
            "action": action,
            "price": price,  # Keep for backward compatibility
            "purchase_price": price,  # Standard field name for frontend display
            "entry_price": price,  # Alternative field name
            "source": "tradingview",
            "parsed_at": datetime.now().isoformat()
        }
        
        return {"success": True, "data": parsed_data}
        
    except Exception as e:
        return {"success": False, "error": f"Error parsing TradingView signal: {str(e)}", "data": {}}


@app.route('/')
def index():
    """Serve the main UI."""
    return render_template('index.html')

@app.route('/test_api_direct.html')
def test_api_direct():
    """Serve test page for debugging X module"""
    from flask import send_from_directory
    return send_from_directory('.', 'test_api_direct.html')

@app.route('/react')
def react_index():
    """Serve the React-based UI."""
    return render_template('react_index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "openai_configured": openai_api_key is not None,
        "webull_authenticated": False,  # Webull removed - use SnapTrade via proxy
        "execution_model": execution_model,
        "builder_model": builder_model
    })


@app.route('/api/signal', methods=['POST'])
def receive_signal():
    """
    Receive a trade signal notification.
    
    Expected JSON format:
    {
        "title": "channel_name",
        "content": "trade signal content"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Extract title (channel) and content
        channel_name = data.get('title', '').strip()
        signal_content = data.get('content', '').strip()
        
        if not channel_name:
            return jsonify({"error": "Title (channel name) is required"}), 400
        
        if not signal_content:
            return jsonify({"error": "Content (signal) is required"}), 400
        
        # Log the received signal
        signal_id = db.log_received_signal(channel_name, signal_content)
        
        # Get channel-specific prompt
        channel_prompt = db.get_channel_prompt(channel_name)
        
        if not channel_prompt:
            db.update_signal_status(signal_id, "failed")
            return jsonify({
                "error": f"No prompt found for channel: {channel_name}",
                "message": "Please create a channel prompt first using the Prompt Builder",
                "signal_id": signal_id
            }), 404
        
        # Check if AI components are available
        if not signal_processor:
            db.update_signal_status(signal_id, "failed")
            return jsonify({
                "error": "OpenAI API not configured",
                "signal_id": signal_id
            }), 503
        
        # Parse the signal using AI
        parse_result = signal_processor.parse_signal(signal_content, channel_prompt)
        
        if not parse_result["success"]:
            db.update_signal_status(signal_id, "parse_failed")
            return jsonify({
                "error": "Failed to parse signal",
                "details": parse_result["error"],
                "signal_id": signal_id
            }), 400
        
        parsed_data = parse_result["data"]
        db.update_signal_status(signal_id, "parsed", json.dumps(parsed_data))
        
        # Validate the parsed signal (general validation)
        validation = signal_processor.validate_signal(parsed_data)
        
        if not validation["valid"]:
            db.update_signal_status(signal_id, "validation_failed")
            return jsonify({
                "error": "Signal validation failed",
                "validation_errors": validation["errors"],
                "signal_id": signal_id
            }), 400
        
        # Validate required options fields before execution
        options_validation = signal_processor.validate_options_signal(parsed_data)
        
        if not options_validation["valid"]:
            db.update_signal_status(signal_id, "validation_failed")
            # Build detailed error message
            error_details = []
            for error in options_validation["errors"]:
                error_details.append(error)
            
            return jsonify({
                "error": "Missing required fields for options trade execution",
                "validation_errors": error_details,
                "missing_fields": options_validation.get("missing_fields", []),
                "signal_id": signal_id,
                "parsed_signal": parsed_data
            }), 400
        
        # ==================== SMART EXECUTOR HANDOFF ====================
        # Build executor-friendly payload
        # Get signal title from database if available
        signal_title = ""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM trade_signals WHERE id = ?", (signal_id,))
            result = cursor.fetchone()
            if result and result[0]:
                signal_title = result[0]
            conn.close()
        except:
            pass
        
        executor_payload = {
            "signal_id": signal_id,
            "ticker": parsed_data.get("symbol"),
            "direction": parsed_data.get("action"),
            "option_type": parsed_data.get("option_type"),
            "strike_price": parsed_data.get("strike"),
            "signal_title": signal_title if signal_title else channel_name,  # Use signal title or channel name as fallback
            "purchase_price": parsed_data.get("purchase_price") or parsed_data.get("entry_price"),
            "input_position_size": parsed_data.get("position_size") or parsed_data.get("quantity"),
            "expiration_date": parsed_data.get("expiration_date"),
        }
        
        # Log the payload for debugging
        print("\n" + "="*80)
        print("🤖 SMART EXECUTOR HANDOFF")
        print("="*80)
        print(f"Signal ID: {signal_id}")
        print(f"Parsed Data: {json.dumps(parsed_data, indent=2)}")
        print(f"Executor Payload: {json.dumps(executor_payload, indent=2, default=str)}")
        print("="*80 + "\n")
        
        # Determine platform (default to etrade if not provided)
        platform = data.get("platform", "etrade").lower()
        print(f"Platform: {platform}")
        
        # Execute via Smart Trade Executor (with full step-by-step logging)
        execution_result = trade_executor.execute_trade(executor_payload, platform)
        
        print("\n" + "="*80)
        print("🤖 SMART EXECUTOR RESULT")
        print("="*80)
        print(f"Success: {execution_result.get('success')}")
        if execution_result.get('success'):
            print(f"Order ID: {execution_result.get('order_id')}")
            print(f"Filled Price: ${execution_result.get('filled_price')}")
            print(f"Position Size: {execution_result.get('position_size')}")
        else:
            print(f"Failed at Step: {execution_result.get('step_failed')}")
            print(f"Error: {execution_result.get('error')}")
        print("="*80 + "\n")
        
        if execution_result["success"]:
            db.update_signal_status(signal_id, "executed")
            
            return jsonify({
                "success": True,
                "message": "Trade signal processed and executed",
                "signal_id": signal_id,
                "parsed_signal": parsed_data,
                "order_id": execution_result.get("order_id"),
                "executor_result": execution_result,
                "warnings": validation.get("warnings", [])
            }), 200
        else:
            db.update_signal_status(signal_id, "execution_failed")
            
            return jsonify({
                "success": False,
                "error": "Trade execution failed",
                "details": execution_result.get("error"),
                "signal_id": signal_id,
                "parsed_signal": parsed_data,
                "executor_result": execution_result
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/channels', methods=['GET'])
def get_channels():
    """Get all channels with token counts."""
    try:
        channels = db.get_all_channels()
        
        # Add token count for each channel
        for channel in channels:
            channel_name = channel.get("channel_name")
            if channel_name:
                prompt = db.get_channel_prompt(channel_name)
                channel["token_count"] = estimate_tokens(prompt) if prompt else 0
        
        return jsonify({"channels": channels}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/channels/management', methods=['GET'])
def get_channel_management_channels():
    """Get all channel management channel names (excludes special channels like x, TradingView)."""
    try:
        channels = get_channel_management_channels()
        return jsonify({"channels": channels}), 200
    except Exception as e:
        return jsonify({"channels": [], "error": str(e)}), 500


@app.route('/api/channel/<channel_name>', methods=['GET'])
def get_channel(channel_name):
    """Get a specific channel with its prompt and title_filter."""
    try:
        channel_info = db.get_channel_info(channel_name)
        
        if not channel_info:
            return jsonify({"error": "Channel not found"}), 404
        
        prompt = channel_info.get("channel_prompt")
        title_filter = channel_info.get("title_filter")
        model_provider = channel_info.get("model_provider", "openai")
        
        # Calculate token count for the prompt
        token_count = estimate_tokens(prompt) if prompt else 0
        
        # Get current model names from settings for display
        grok_model = grok_api.model if grok_api else "grok-2-1212"
        
        # Try to extract builder prompt from training data if available
        training_data = db.get_training_data(channel_name)
        builder_prompt_hint = None
        
        if training_data:
            # Check if we have the full signals dump stored
            for item in training_data:
                if len(item['signal_text']) > 500:  # Likely the full dump
                    builder_prompt_hint = "Builder prompt was generated from conversational analysis. Original signals analyzed are stored in training data."
                    break
        
        return jsonify({
            "channel_name": channel_name,
            "prompt": prompt,
            "title_filter": title_filter,
            "model_provider": model_provider,
            "token_count": token_count,
            "execution_model": execution_model,  # OpenAI model from settings
            "grok_model": grok_model,  # Grok model from settings
            "builder_prompt_hint": builder_prompt_hint
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/channel/<channel_name>/duplicate', methods=['POST'])
def duplicate_channel(channel_name):
    """
    Duplicate a channel with all its settings.
    
    Expected JSON format:
    {
        "new_channel_name": "new_channel_name"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        new_channel_name = data.get('new_channel_name', '').strip()
        
        if not new_channel_name:
            return jsonify({"error": "New channel name is required"}), 400
        
        # Check if source channel exists
        channel_info = db.get_channel_info(channel_name)
        if not channel_info:
            return jsonify({"error": f"Source channel '{channel_name}' not found"}), 404
        
        # Check if new channel name already exists
        existing = db.get_channel_info(new_channel_name)
        if existing:
            return jsonify({"error": f"Channel '{new_channel_name}' already exists"}), 400
        
        # Duplicate the channel
        success = db.duplicate_channel(channel_name, new_channel_name)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Channel '{channel_name}' duplicated to '{new_channel_name}'",
                "new_channel_name": new_channel_name
            }), 200
        else:
            import traceback
            print(f"Failed to duplicate channel '{channel_name}' to '{new_channel_name}'")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": f"Failed to duplicate channel. Check server logs for details."
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Exception in duplicate_channel: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error duplicating channel: {str(e)}"}), 500


@app.route('/api/channel/<channel_name>/rename', methods=['PUT'])
def rename_channel(channel_name):
    """
    Rename a channel.
    
    Expected JSON format:
    {
        "new_channel_name": "new_channel_name"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        new_channel_name = data.get('new_channel_name', '').strip()
        
        if not new_channel_name:
            return jsonify({"error": "New channel name is required"}), 400
        
        if new_channel_name == channel_name:
            return jsonify({"error": "New channel name must be different from current name"}), 400
        
        # Check if source channel exists
        channel_info = db.get_channel_info(channel_name)
        if not channel_info:
            return jsonify({"error": f"Channel '{channel_name}' not found"}), 404
        
        # Check if new channel name already exists
        existing = db.get_channel_info(new_channel_name)
        if existing:
            return jsonify({"error": f"Channel '{new_channel_name}' already exists"}), 400
        
        # Rename the channel
        success = db.rename_channel(channel_name, new_channel_name)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Channel '{channel_name}' renamed to '{new_channel_name}'",
                "new_channel_name": new_channel_name
            }), 200
        else:
            import traceback
            print(f"Failed to rename channel '{channel_name}' to '{new_channel_name}'")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": f"Failed to rename channel. Check server logs for details."
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Exception in rename_channel: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error renaming channel: {str(e)}"}), 500


@app.route('/api/channel/<channel_name>/title-filter', methods=['PUT'])
def update_channel_title_filter(channel_name):
    """
    Update the title filter for an existing channel.
    
    Expected JSON format:
    {
        "title_filter": "filter text" or null/empty to remove
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        title_filter = data.get('title_filter', '').strip() or None
        
        # Check if channel exists
        channel_info = db.get_channel_info(channel_name)
        if not channel_info:
            return jsonify({"error": f"Channel '{channel_name}' not found"}), 404
        
        # Update the title filter
        success = db.update_channel_title_filter(channel_name, title_filter)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Channel '{channel_name}' title filter updated",
                "title_filter": title_filter
            }), 200
        else:
            # Log the error for debugging
            import traceback
            print(f"Failed to update title filter for channel '{channel_name}'")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": f"Failed to update title filter for channel '{channel_name}'. Check server logs for details."
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Exception in update_channel_title_filter: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error updating title filter: {str(e)}"}), 500


@app.route('/api/channel/<channel_name>/model-provider', methods=['PUT'])
def update_channel_model_provider(channel_name):
    """
    Update the model provider for an existing channel.
    
    Expected JSON format:
    {
        "model_provider": "openai" or "grok"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        model_provider = data.get('model_provider', '').strip().lower()
        
        if model_provider not in ['openai', 'grok']:
            return jsonify({"error": "Invalid model provider. Must be 'openai' or 'grok'"}), 400
        
        # Check if channel exists
        channel_info = db.get_channel_info(channel_name)
        if not channel_info:
            return jsonify({"error": f"Channel '{channel_name}' not found"}), 404
        
        # Update the model provider
        success = db.update_channel_model_provider(channel_name, model_provider)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Channel '{channel_name}' model provider updated to {model_provider.upper()}",
                "model_provider": model_provider
            }), 200
        else:
            # Log the error for debugging
            import traceback
            print(f"Failed to update model provider for channel '{channel_name}'")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": f"Failed to update model provider for channel '{channel_name}'. Check server logs for details."
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Exception in update_channel_model_provider: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error updating model provider: {str(e)}"}), 500


@app.route('/api/channel/<channel_name>', methods=['DELETE'])
def delete_channel(channel_name):
    """
    Delete a channel and optionally all related data.
    
    Optional query parameter:
    - delete_related_data: true/false (default: true) - whether to delete training data, signals, and executions
    """
    try:
        delete_related = request.args.get('delete_related_data', 'true').lower() == 'true'
        
        result = db.delete_channel(channel_name, delete_related_data=delete_related)
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"Channel '{channel_name}' deleted successfully",
                "channel_deleted": result["channel_deleted"],
                "training_data_deleted": result["training_data_deleted"],
                "signals_deleted": result["signals_deleted"],
                "executions_deleted": result["executions_deleted"],
                "total_deleted": result["total_deleted"]
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to delete channel")
            }), 404 if "not found" in result.get("error", "").lower() else 500
            
    except Exception as e:
        return jsonify({"error": f"Error deleting channel: {str(e)}"}), 500


@app.route('/api/prompt-builder/start', methods=['POST'])
def start_prompt_building():
    """
    Start a conversational prompt building session.
    
    Expected JSON format:
    {
        "channel_name": "my_channel",
        "signals_dump": "paste all your signals here...",
        "title_filter": "XYZ-Trade-alerts" (optional),
        "is_update": false
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        channel_name = data.get('channel_name', '').strip()
        signals_dump = data.get('signals_dump', '').strip()
        title_filter = data.get('title_filter', '').strip() or None
        model_provider = data.get('model_provider', 'openai').strip().lower()  # 'openai' or 'grok'
        is_update = data.get('is_update', False)
        
        if not channel_name:
            return jsonify({"error": "Channel name is required"}), 400
        
        if not signals_dump:
            return jsonify({"error": "Signals dump is required"}), 400
        
        # Check if the selected model provider is configured
        if model_provider == 'grok':
            if not grok_api or not grok_api.is_enabled():
                return jsonify({"error": "Grok API not configured. Please configure Grok in Settings first."}), 503
        else:  # openai
            if not prompt_builder:
                return jsonify({"error": "OpenAI API not configured"}), 503
        
        # Get existing prompt if updating
        existing_prompt = None
        if is_update:
            existing_prompt = db.get_channel_prompt(channel_name)
            if not existing_prompt:
                return jsonify({
                    "error": f"Channel '{channel_name}' not found. Cannot update non-existent channel."
                }), 404
        
        # Start conversational analysis
        result = prompt_builder.start_conversation(
            channel_name=channel_name,
            signals_dump=signals_dump,
            existing_prompt=existing_prompt,
            is_update=is_update
        )
        
        # Add title_filter and model_provider to context if provided
        if title_filter:
            result["context"]["title_filter"] = title_filter
        result["context"]["model_provider"] = model_provider
        
        # Store conversation context in session (for now, return it to client)
        return jsonify({
            "success": True,
            "message": "Analysis started",
            "response": result["response"],
            "has_questions": result["has_questions"],
            "ready_to_build": result["ready_to_build"],
            "conversation_id": result["conversation_id"],
            "context": result["context"]
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error starting prompt builder: {str(e)}"}), 500


@app.route('/api/prompt-builder/continue', methods=['POST'])
def continue_prompt_building():
    """
    Continue the conversational prompt building session.
    
    Expected JSON format:
    {
        "conversation_id": "...",
        "user_response": "user's answer to questions",
        "context": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        conversation_id = data.get('conversation_id')
        user_response = data.get('user_response', '').strip()
        context = data.get('context', {})
        
        if not conversation_id:
            return jsonify({"error": "Conversation ID is required"}), 400
        
        if not user_response:
            return jsonify({"error": "User response is required"}), 400
        
        if not prompt_builder:
            return jsonify({"error": "OpenAI API not configured"}), 503
        
        # Continue conversation
        result = prompt_builder.continue_conversation(
            conversation_id=conversation_id,
            user_response=user_response,
            context=context
        )
        
        return jsonify({
            "success": True,
            "response": result["response"],
            "has_questions": result["has_questions"],
            "ready_to_build": result["ready_to_build"],
            "context": result["context"]
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error continuing conversation: {str(e)}"}), 500


@app.route('/api/prompt-builder/finalize', methods=['POST'])
def finalize_prompt_building():
    """
    Finalize and generate the channel prompt.
    
    Expected JSON format:
    {
        "conversation_id": "...",
        "context": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        conversation_id = data.get('conversation_id')
        context = data.get('context', {})
        
        if not conversation_id:
            return jsonify({"error": "Conversation ID is required"}), 400
        
        if not prompt_builder:
            return jsonify({"error": "OpenAI API not configured"}), 503
        
        # Generate final prompt
        result = prompt_builder.finalize_prompt(
            conversation_id=conversation_id,
            context=context
        )
        
        if result["success"]:
            # Save the prompt to database
            channel_name = context.get("channel_name")
            generated_prompt = result["prompt"]
            title_filter = context.get("title_filter")  # Get title_filter from context
            model_provider = context.get("model_provider", "openai")  # Get model_provider from context
            
            success = db.save_channel_prompt(channel_name, generated_prompt, title_filter=title_filter, model_provider=model_provider)
            
            if success:
                # Also save the signals as training data
                signals_dump = context.get("signals_dump", "")
                if signals_dump:
                    # Store as a single training record for reference
                    db.save_training_data(
                        channel_name=channel_name,
                        signal_text=signals_dump,
                        signal_date=None,
                        weight=1.0
                    )
                
                return jsonify({
                    "success": True,
                    "message": f"Channel prompt {'updated' if context.get('is_update') else 'created'} successfully",
                    "channel_name": channel_name,
                    "prompt": generated_prompt,
                    "builder_prompt_used": result.get("builder_prompt_used"),
                    "context": result.get("context", context)  # Return updated context with finalize prompts
                }), 200
            else:
                return jsonify({
                    "error": "Failed to save channel prompt"
                }), 500
        else:
            return jsonify({
                "error": result.get("error", "Failed to generate prompt")
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error finalizing prompt: {str(e)}"}), 500


@app.route('/api/channel/prompt/build', methods=['POST'])
def build_channel_prompt():
    """
    Build or update a channel prompt using AI.
    
    Expected JSON format:
    {
        "channel_name": "my_channel",
        "training_data": [
            {"signal": "BUY TSLA @ 250 SL 245 TP 260", "date": "2025-12-01"},
            {"signal": "SELL AAPL @ 180", "date": "2025-11-25"}
        ],
        "title_filter": "XYZ-Trade-alerts" (optional),
        "is_update": false
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        channel_name = data.get('channel_name', '').strip()
        training_data = data.get('training_data', [])
        title_filter = data.get('title_filter', '').strip() or None
        is_update = data.get('is_update', False)
        
        if not channel_name:
            return jsonify({"error": "Channel name is required"}), 400
        
        if not training_data:
            return jsonify({"error": "Training data is required"}), 400
        
        if not prompt_builder:
            return jsonify({"error": "OpenAI API not configured"}), 503
        
        # Save training data to database
        for item in training_data:
            db.save_training_data(
                channel_name=channel_name,
                signal_text=item.get('signal', ''),
                signal_date=item.get('date')
            )
        
        # Build or update the prompt
        if is_update:
            existing_prompt = db.get_channel_prompt(channel_name)
            
            if not existing_prompt:
                return jsonify({
                    "error": f"Channel '{channel_name}' not found. Cannot update non-existent channel."
                }), 404
            
            # Update the prompt
            new_prompt = prompt_builder.update_prompt(
                channel_name=channel_name,
                existing_prompt=existing_prompt,
                new_training_data=training_data
            )
        else:
            # Create new prompt
            new_prompt = prompt_builder.build_prompt(
                channel_name=channel_name,
                training_data=training_data
            )
        
        # Save the prompt
        success = db.save_channel_prompt(channel_name, new_prompt)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Channel prompt {'updated' if is_update else 'created'} successfully",
                "channel_name": channel_name,
                "prompt": new_prompt
            }), 200
        else:
            return jsonify({
                "error": "Failed to save channel prompt"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error building prompt: {str(e)}"}), 500


@app.route('/api/signals/receive', methods=['POST'])
def receive_external_signal():
    """
    Receive signals from external sources (e.g., Chrome extension).
    Attempts to match signal title to a channel using title_filter.
    If matched, processes the signal with the channel's prompt.
    If unmatched, stores as raw signal with status "unmatched".
    
    Expected JSON format:
    {
        "title": "Notification title",
        "message": "Notification message",
        "source": "chrome_extension" (optional, defaults to "external")
    }
    """
    try:
        # Log incoming request for debugging
        print(f"\n{'='*80}")
        print("📥 INCOMING WEBHOOK REQUEST")
        print(f"{'='*80}")
        print(f"Content-Type: {request.content_type}")
        print(f"Method: {request.method}")
        print(f"Raw Data: {request.get_data(as_text=True)[:500]}")
        print(f"{'='*80}\n")
        
        # Try to get data - handle JSON, form data, and plain text (TradingView sends plain text)
        data = None
        raw_data = request.get_data(as_text=True)
        
        print(f"📋 Raw Request Data: '{raw_data}'")
        print(f"📋 Content-Type: {request.content_type}")
        
        if request.is_json:
            # Standard JSON request
            data = request.get_json()
            print(f"📋 Parsed as JSON")
        elif request.content_type and 'application/json' in request.content_type:
            # JSON content type but not detected as JSON
            try:
                data = json.loads(raw_data) if raw_data else {}
                print(f"📋 Parsed as JSON from raw data")
            except:
                pass
        elif request.content_type and 'text/plain' in request.content_type:
            # TradingView sends plain text - convert to our format
            print(f"📋 Detected plain text (TradingView format)")
            if raw_data:
                # Use the plain text as the message
                data = {
                    "title": "TradingView Alert",
                    "message": raw_data,
                    "source": "tradingview"
                }
                print(f"📋 Converted plain text to message: '{raw_data[:100]}...'")
        else:
            # Try to parse as JSON from raw data
            try:
                if raw_data:
                    data = json.loads(raw_data)
                    print(f"📋 Parsed as JSON from raw data (fallback)")
            except:
                # If not JSON, try form data
                data = request.form.to_dict()
                if data:
                    print(f"📋 Parsed as form data")
                else:
                    # Also check if data is in request.args
                    data = request.args.to_dict()
                    if data:
                        print(f"📋 Parsed as query parameters")
        
        # Final fallback: if we have raw_data but no parsed data, treat it as plain text
        if not data and raw_data:
            print(f"📋 Fallback: Treating raw data as plain text message")
            data = {
                "title": "TradingView Alert",
                "message": raw_data,
                "source": "tradingview"
            }
            print(f"📋 Converted plain text to message: '{raw_data[:100]}...'")
        
        if not data:
            print("⚠️ No data found in request")
            return jsonify({"error": "No data provided"}), 400
        
        print(f"📋 Final Parsed Data: {json.dumps(data, indent=2)}")
        
        # Handle TradingView webhook format - they might send data differently
        # TradingView might send the entire payload as a string in 'message' field
        if isinstance(data, dict) and 'message' in data and isinstance(data['message'], str):
            # Check if message contains JSON
            try:
                message_json = json.loads(data['message'])
                # If it's valid JSON, merge it with the main data
                if isinstance(message_json, dict):
                    data = {**data, **message_json}
                    print(f"📋 Merged TradingView JSON from message field")
            except:
                pass
        
        title = data.get('title', '').strip() if isinstance(data.get('title'), str) else str(data.get('title', '')).strip()
        message = data.get('message', '').strip() if isinstance(data.get('message'), str) else str(data.get('message', '')).strip()
        source = data.get('source', 'external').strip() if isinstance(data.get('source'), str) else 'external'
        
        # If no title/message, try alternative field names (TradingView might use different names)
        if not title and not message:
            # Try common TradingView field names
            title = data.get('ticker', data.get('symbol', data.get('text', ''))).strip() if isinstance(data.get('ticker', data.get('symbol', data.get('text', ''))), str) else ''
            message = data.get('alert', data.get('content', data.get('body', ''))).strip() if isinstance(data.get('alert', data.get('content', data.get('body', ''))), str) else ''
        
        print(f"📝 Extracted - Title: '{title}', Message: '{message[:100]}...', Source: '{source}'")
        
        # Validate that we have at least title or message
        if not title and not message:
            return jsonify({"error": "At least 'title' or 'message' is required"}), 400
        
        # Check if this is an X-related bot signal using configured keywords
        # These should be assigned to "x" channel automatically
        is_x_bot_signal = False
        # Get configured X bot keywords from database (default to original values)
        x_bot_keywords_str = db.get_setting("x_bot_keywords", '"flow-bot" OR "uwhale-news-bot" OR "x-news-bot"')
        # Parse the keywords string (format: "keyword1" OR "keyword2" OR "keyword3")
        # Extract keywords from quoted strings
        x_bot_keywords = re.findall(r'"([^"]+)"', x_bot_keywords_str)
        if not x_bot_keywords:
            # Fallback to default if parsing fails
            x_bot_keywords = ["flow-bot", "uwhale-news-bot", "x-news-bot"]
        
        if title:
            title_lower = title.strip().lower()
            for keyword in x_bot_keywords:
                if keyword.lower() in title_lower:
                    is_x_bot_signal = True
                    print(f"\n{'='*80}")
                    print("🐦 X BOT SIGNAL DETECTED")
                    print(f"{'='*80}")
                    print(f"Title: {title}")
                    print(f"Matched Keyword: {keyword}")
                    print(f"Message: {message[:200]}...")
                    print(f"{'='*80}\n")
                    break
        
        # Check if this is a TradingView Alert (special handling - no AI processing)
        is_tradingview_alert = (title and title.strip().lower() == "tradingview alert")
        
        if is_x_bot_signal:
            # Record the signal with "x" channel
            signal_id = signals.record_signal(
                source=source,
                title=title,
                message=message,
                metadata=None
            )
            
            # Update channel_name to "x"
            conn = db.get_connection()
            cursor = conn.cursor()
            received_at = None
            try:
                cursor.execute("""
                    UPDATE trade_signals 
                    SET channel_name = ?, status = ?
                    WHERE id = ?
                """, ("x", "matched", signal_id))
                
                # Get the received_at timestamp for analysis
                cursor.execute("""
                    SELECT received_at 
                    FROM trade_signals 
                    WHERE id = ?
                """, (signal_id,))
                result = cursor.fetchone()
                if result:
                    received_at = result[0]
                
                conn.commit()
                print(f"✅ X bot signal assigned to 'x' channel. Signal ID: {signal_id}")
            except Exception as e:
                print(f"Error updating channel_name: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # Automatically analyze the signal
            if received_at:
                try:
                    print(f"🧠 Auto-analyzing X signal {signal_id}...")
                    analysis = x_signal_processor.analyze_signal(
                        signal_id=signal_id,
                        title=title,
                        message=message,
                        received_at=received_at
                    )
                    
                    if 'error' not in analysis:
                        # Store analysis in database
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        try:
                            # Insert analysis
                            cursor.execute("""
                                INSERT OR REPLACE INTO x_signal_analysis 
                                (signal_id, signal_type, engagement_score, score_breakdown, 
                                 recommendation, star_rating, entities, analyzed_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                signal_id,
                                analysis['signal_type'],
                                analysis['score'],
                                json.dumps(analysis['score_breakdown']),
                                analysis['recommendation'],
                                analysis['star_rating'],
                                json.dumps(analysis['entities']),
                                datetime.now().isoformat()
                            ))
                            
                            analysis_id = cursor.lastrowid
                            
                            # Insert variants
                            for variant in analysis['variants']:
                                cursor.execute("""
                                    INSERT INTO x_tweet_variants 
                                    (signal_id, analysis_id, variant_type, tweet_text, 
                                     predicted_engagement, style_description, is_recommended, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    signal_id,
                                    analysis_id,
                                    variant['type'],
                                    variant['text'],
                                    variant['predicted_engagement'],
                                    variant['style'],
                                    variant['recommended'],
                                    datetime.now().isoformat()
                                ))
                            
                            conn.commit()
                            print(f"✅ Signal {signal_id} automatically analyzed. Score: {analysis['score']:.2f}, Recommendation: {analysis['recommendation']}")
                            
                            # Send push notification if engagement score >= 0.5 and tweet variant exists
                            if analysis.get('score', 0) >= 0.5 and analysis.get('variants') and len(analysis['variants']) > 0:
                                try:
                                    tweet_text = analysis['variants'][0].get('text', '')
                                    if tweet_text:
                                        # Truncate tweet for notification body (max 100 chars)
                                        notification_body = tweet_text[:100] + ('...' if len(tweet_text) > 100 else '')
                                        
                                        push_manager.send_notification_to_all(
                                            title="News",
                                            body=notification_body,
                                            data={
                                                "url": "/",
                                                "signal_id": signal_id,
                                                "action": "view_signal",
                                                "tab": "x"
                                            },
                                            tag=f"signal-{signal_id}",  # Tag to replace previous notifications for same signal
                                            requireInteraction=False
                                        )
                                        print(f"✅ Push notification sent for signal {signal_id} (score: {analysis['score']:.2f})")
                                        
                                        # Also send Android native notification
                                        send_android_notification("X Signal", notification_body)
                                except Exception as e:
                                    print(f"⚠️ Error sending push notification for signal {signal_id}: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    # Don't fail the analysis if notification fails
                        except Exception as e:
                            print(f"⚠️ Error saving analysis to database: {e}")
                            conn.rollback()
                        finally:
                            conn.close()
                    else:
                        print(f"⚠️ Error analyzing signal {signal_id}: {analysis.get('error')}")
                except Exception as e:
                    print(f"⚠️ Error during auto-analysis: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Send Discord notification if Discord is enabled and configured
            if discord_api.is_enabled() and discord_api.is_configured:
                try:
                    # Format message with title and signal content
                    discord_title = title if title else "X Bot Signal"
                    discord_body = message if message else title
                    
                    # Format Discord message
                    discord_message = f"**{discord_title}**\n\n{discord_body}"
                    
                    discord_result = discord_api.send_message(discord_message)
                    if discord_result.get("success"):
                        print(f"✅ Discord notification sent for X bot signal")
                        print(f"   Title: {discord_title}")
                        print(f"   Message: {discord_body[:100]}...")
                    else:
                        print(f"⚠️ Failed to send Discord notification: {discord_result.get('error')}")
                except Exception as e:
                    print(f"⚠️ Error sending Discord notification: {e}")
                    import traceback
                    traceback.print_exc()
            
            return jsonify({
                "success": True,
                "signal_id": signal_id,
                "matched_channel": "x",
                "status": "matched",
                "message": "X bot signal received, assigned to 'x' channel, and automatically analyzed"
            }), 200
        
        if is_tradingview_alert:
            print(f"\n{'='*80}")
            print("📊 TRADINGVIEW ALERT DETECTED")
            print(f"{'='*80}")
            print(f"Title: {title}")
            print(f"Message: {message}")
            print(f"{'='*80}\n")
            
            # Check for duplicate signals BEFORE processing
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(trade_signals)")
                columns = [col[1] for col in cursor.fetchall()]
                has_message = 'message' in columns
                
                if has_message:
                    cursor.execute("""
                        SELECT id, received_at 
                        FROM trade_signals 
                        WHERE channel_name = 'TradingView' 
                        AND message = ? 
                        AND datetime(received_at) > datetime('now', '-3 seconds')
                        ORDER BY received_at DESC
                        LIMIT 1
                    """, (message,))
                else:
                    cursor.execute("""
                        SELECT id, received_at 
                        FROM trade_signals 
                        WHERE channel_name = 'TradingView' 
                        AND raw_content LIKE ? 
                        AND datetime(received_at) > datetime('now', '-3 seconds')
                        ORDER BY received_at DESC
                        LIMIT 1
                    """, (f'%{message}%',))
                
                duplicate = cursor.fetchone()
                conn.close()
                
                if duplicate:
                    print(f"⚠️ DUPLICATE REJECTED - Signal ID: {duplicate[0]}")
                    return jsonify({
                        "success": True,
                        "signal_id": duplicate[0],
                        "status": "duplicate",
                        "message": "Duplicate rejected",
                        "duplicate_of": duplicate[0]
                    }), 200
            except Exception as e:
                print(f"⚠️ Error checking duplicates: {e}")
                if conn:
                    conn.close()
            
            # Parse signal
            parsed_tradingview = parse_tradingview_signal(message)
            
            if not parsed_tradingview["success"]:
                signal_id = signals.record_signal(source=source, title=title, message=message, metadata=None)
                conn = db.get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE trade_signals SET channel_name = ?, status = ? WHERE id = ?", 
                                 ("TradingView", "parse_failed", signal_id))
                    conn.commit()
                finally:
                    conn.close()
                
                return jsonify({
                    "success": True,
                    "signal_id": signal_id,
                    "status": "parse_failed",
                    "error": parsed_tradingview.get("error")
                }), 200
            
            # Record the signal with TradingView channel
            signal_id = signals.record_signal(
                source=source,
                title=title,
                message=message,
                metadata=None
            )
            
            # Update channel_name to TradingView
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE trade_signals 
                    SET channel_name = ?, status = ?
                    WHERE id = ?
                """, ("TradingView", "processed", signal_id))
                conn.commit()
            except Exception as e:
                print(f"Error updating channel_name: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # Store parsed data
            parsed_json = json.dumps(parsed_tradingview["data"])
            db.update_signal_status(signal_id, "processed", parsed_json)
            
            print(f"✅ TradingView signal parsed successfully:")
            print(f"   Ticker: {parsed_tradingview['data'].get('symbol')}")
            print(f"   Action: {parsed_tradingview['data'].get('action')}")
            print(f"   Price: {parsed_tradingview['data'].get('price')}")
            print(f"   Purchase Price: {parsed_tradingview['data'].get('purchase_price')}")
            
            # Execute the signal automatically using TradingView Executor
            execution_result = None
            try:
                print(f"\n🤖 Executing TradingView signal via TradingView Executor...")
                execution_result = tradingview_executor.execute_signal(
                    parsed_tradingview["data"], 
                    account_id=None,
                    signal_id=signal_id
                )
                
                if execution_result.get("success"):
                    print(f"✅ Execution successful!")
                    print(f"   Order ID: {execution_result.get('order_id')}")
                    print(f"   Filled Price: ${execution_result.get('filled_price')}")
                    print(f"   Attempts: {execution_result.get('attempts')}")
                else:
                    print(f"⚠️  Execution failed: {execution_result.get('error')}")
                    print(f"   Attempts: {execution_result.get('attempts', 0)}")
            except Exception as e:
                print(f"❌ Error executing signal: {e}")
                import traceback
                traceback.print_exc()
            
            return jsonify({
                "success": True,
                "signal_id": signal_id,
                "matched_channel": "TradingView",
                "status": "processed",
                "message": "TradingView signal received, parsed, and executed",
                "parsed_signal": parsed_tradingview["data"],
                "execution_result": execution_result
            }), 200
        
        # Check for Commentary channel first (if title contains "commentary")
        matched_channel = None
        if title and "commentary" in title.lower():
            # Check if Commentary channel exists, if not create it
            commentary_channel_info = db.get_channel_info("Commentary")
            if not commentary_channel_info:
                # Create Commentary channel with default settings
                print("📝 Creating Commentary channel (not found in database)")
                db.save_channel_prompt(
                    channel_name="Commentary",
                    prompt="Parse this commentary signal and extract any relevant trading information.",
                    title_filter="commentary",
                    model_provider="openai"
                )
            matched_channel = "Commentary"
            print(f"✅ Signal matched to Commentary channel (title contains 'commentary')")
        
        # If not Commentary, try to find matching channel by title filter
        if not matched_channel and title:
            matched_channel = db.find_channel_by_title_filter(title)
        
        # Determine channel name and initial status
        if matched_channel:
            channel_name = matched_channel
            initial_status = "matched"
        else:
            channel_name = "UNMATCHED"
            initial_status = "unmatched"
        
        # Record the signal (will use external_source initially, we'll update channel_name)
        signal_id = signals.record_signal(
            source=source,
            title=title,
            message=message,
            metadata=None
        )
        
        # Update channel_name in database if matched
        if matched_channel:
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE trade_signals 
                    SET channel_name = ?, status = ?
                    WHERE id = ?
                """, (channel_name, initial_status, signal_id))
                conn.commit()
            except Exception as e:
                print(f"Error updating channel_name: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # Send Discord notification for Commentary channel immediately when matched
            if matched_channel == "Commentary":
                if discord_api.is_enabled() and discord_api.is_configured:
                    try:
                        # Format message with title and signal content
                        discord_title = title if title else "Commentary Signal"
                        discord_body = message if message else title
                        if not discord_body:
                            discord_body = "New commentary signal received"
                        
                        # Format Discord message with title and body
                        discord_message = f"**{discord_title}**\n\n{discord_body}"
                        
                        # Use commentary channel ID if configured, otherwise use default channel
                        commentary_channel_id = None
                        if discord_api.db:
                            commentary_channel_id = discord_api.db.get_setting("discord_commentary_channel_id", "").strip() or None
                        
                        # Send to commentary channel if configured, otherwise to default channel
                        target_channel_id = commentary_channel_id if commentary_channel_id else None
                        discord_result = discord_api.send_message(discord_message, channel_id=target_channel_id)
                        
                        if discord_result.get("success"):
                            channel_used = target_channel_id or discord_api.channel_id
                            print(f"✅ Discord notification sent for Commentary signal (immediate)")
                            print(f"   Signal ID: {signal_id}")
                            print(f"   Discord Channel ID: {channel_used}")
                            print(f"   Title: {discord_title}")
                            print(f"   Message: {discord_body[:100]}...")
                        else:
                            print(f"⚠️ Failed to send Discord notification for Commentary signal: {discord_result.get('error')}")
                    except Exception as e:
                        print(f"⚠️ Error sending Discord notification for Commentary signal: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't fail the signal processing if notification fails
                elif not discord_api.is_enabled():
                    print(f"ℹ️ Discord notifications disabled (module is disabled)")
                elif not discord_api.is_configured:
                    print(f"ℹ️ Discord not configured (missing bot token or channel ID)")
            
            # Send push notification if matched to any channel management channel (regardless of processing status)
            if matched_channel and is_channel_management_channel(matched_channel):
                try:
                    # Use signal title as notification title
                    notification_title = title if title else f"{matched_channel} Signal"
                    # Use actual signal content (message) as notification body
                    notification_body = message if message else title
                    if not notification_body:
                        notification_body = "New signal received"
                    
                    # Truncate body if too long (max 200 chars for notification body)
                    if len(notification_body) > 200:
                        notification_body = notification_body[:200] + '...'
                    
                    push_manager.send_notification_to_all(
                        title=notification_title,  # Signal title as notification title
                        body=notification_body,    # Actual signal content as body
                        data={
                            "url": "/",
                            "signal_id": signal_id,
                            "action": "view_signal",
                            "tab": "dashboard"
                        },
                        tag=f"master-signal-{signal_id}",  # Tag to replace previous notifications for same signal
                        requireInteraction=False
                    )
                    print(f"✅ Push notification sent for channel management signal {signal_id} (channel: {matched_channel})")
                    print(f"   Title: {notification_title}")
                    print(f"   Body: {notification_body[:100]}...")
                    
                    # Also send Android native notification
                    send_android_notification(notification_title, notification_body)
                except Exception as e:
                    print(f"⚠️ Error sending push notification for channel management signal {signal_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the signal processing if notification fails
            
            # If matched, try to process the signal with the channel's prompt
            try:
                # Check if signal_processor is available
                if not signal_processor:
                    print("⚠️ signal_processor not available (OpenAI not configured)")
                    db.update_signal_status(signal_id, "no_processor", None)
                    return jsonify({
                        "success": True,
                        "signal_id": signal_id,
                        "matched_channel": matched_channel,
                        "status": "no_processor",
                        "message": "Signal matched but OpenAI API not configured"
                    }), 200
                
                # Get channel info to determine model provider
                channel_info = db.get_channel_info(matched_channel)
                channel_prompt = db.get_channel_prompt(matched_channel)
                
                if channel_prompt and channel_info:
                    # Process the signal using the channel's prompt
                    # Use message as the signal content
                    signal_content = message if message else title
                    
                    if not signal_content:
                        db.update_signal_status(signal_id, "empty_content", None)
                        return jsonify({
                            "success": True,
                            "signal_id": signal_id,
                            "matched_channel": matched_channel,
                            "status": "empty_content",
                            "message": "Signal matched but content is empty"
                        }), 200
                    
                    # Determine which model provider to use
                    model_provider = channel_info.get("model_provider", "openai")
                    
                    # Parse the signal using the appropriate model provider
                    if model_provider == "grok":
                        if not grok_api or not grok_api.is_enabled():
                            print(f"⚠️ Grok API not configured for channel {matched_channel}, falling back to OpenAI")
                            parsed_result = signal_processor.parse_signal(signal_content, channel_prompt) if signal_processor else None
                        else:
                            print(f"🤖 Using Grok model for channel: {matched_channel}")
                            parsed_result = grok_api.parse_signal(signal_content, channel_prompt)
                    else:  # openai (default)
                        print(f"🤖 Using OpenAI model for channel: {matched_channel}")
                        parsed_result = signal_processor.parse_signal(signal_content, channel_prompt) if signal_processor else None
                    
                    if not parsed_result:
                        db.update_signal_status(signal_id, "no_processor", None)
                        return jsonify({
                            "success": True,
                            "signal_id": signal_id,
                            "matched_channel": matched_channel,
                            "status": "no_processor",
                            "message": f"Signal matched but {model_provider.upper()} API not configured"
                        }), 200
                    
                    if parsed_result["success"]:
                        parsed_data = parsed_result["data"]
                        parsed_json = json.dumps(parsed_data)
                        
                        print("\n" + "="*80)
                        print("📥 SIGNAL RECEIVED AND PARSED (/api/signals/receive)")
                        print("="*80)
                        print(f"Signal ID: {signal_id}")
                        print(f"Matched Channel: {matched_channel}")
                        print(f"Signal Content: {signal_content[:100]}...")
                        print(f"Parsed Data: {json.dumps(parsed_data, indent=2, default=str)}")
                        print("="*80 + "\n")
                        
                        # Update signal with parsed data
                        db.update_signal_status(signal_id, "processed", parsed_json)
                        
                        # Send Android native notification for channel management signals
                        if matched_channel and is_channel_management_channel(matched_channel):
                            try:
                                notification_title = title if title else f"{matched_channel} Signal"
                                # Use parsed signal summary if available, otherwise use signal content
                                if parsed_data and parsed_data.get('symbol'):
                                    symbol = parsed_data.get('symbol', '')
                                    action = parsed_data.get('action', '')
                                    notification_body = f"{action} {symbol}"
                                    if parsed_data.get('option_type'):
                                        notification_body += f" {parsed_data.get('option_type')}"
                                    if parsed_data.get('strike'):
                                        notification_body += f" @ ${parsed_data.get('strike')}"
                                else:
                                    notification_body = signal_content[:100] if signal_content else message[:100] if message else "New signal received"
                                    if len(notification_body) > 100:
                                        notification_body = notification_body[:100] + '...'
                                
                                send_android_notification(notification_title, notification_body)
                            except Exception as e:
                                print(f"⚠️ Error sending Android notification for channel management signal: {e}")
                                # Don't fail the signal processing if notification fails
                        
                        # Note: Commentary channel Discord forwarding happens immediately when matched (before processing)
                        # This ensures commentary signals are always forwarded to Discord, even if parsing fails
                        
                        # Send Discord notification if channel is in channel management and Discord is enabled
                        # This includes Commentary channel (Commentary is a channel management channel)
                        if matched_channel and is_channel_management_channel(matched_channel):
                            if discord_api.is_enabled() and discord_api.is_configured:
                                try:
                                    # Format message with title and signal content
                                    # Use title if available, otherwise use signal_content
                                    discord_title = title if title else "Signal Notification"
                                    discord_body = signal_content if signal_content else message
                                    
                                    # Format Discord message with title and body
                                    discord_message = f"**{discord_title}**\n\n{discord_body}"
                                    
                                    # Use channel management channel ID if configured, otherwise use default channel
                                    channel_management_channel_id = None
                                    if discord_api.db:
                                        channel_management_channel_id = discord_api.db.get_setting("discord_channel_management_channel_id", "").strip() or None
                                    
                                    # Send to channel management channel if configured, otherwise to default channel
                                    target_channel_id = channel_management_channel_id if channel_management_channel_id else None
                                    discord_result = discord_api.send_message(discord_message, channel_id=target_channel_id)
                                    
                                    if discord_result.get("success"):
                                        channel_used = target_channel_id or discord_api.channel_id
                                        print(f"✅ Discord notification sent for channel management signal (channel: {matched_channel})")
                                        print(f"   Discord Channel ID: {channel_used}")
                                        print(f"   Title: {discord_title}")
                                        print(f"   Message: {discord_body[:100]}...")
                                    else:
                                        print(f"⚠️ Failed to send Discord notification: {discord_result.get('error')}")
                                except Exception as e:
                                    print(f"⚠️ Error sending Discord notification: {e}")
                                    import traceback
                                    traceback.print_exc()
                            elif not discord_api.is_enabled():
                                print(f"ℹ️ Discord notifications disabled (module is disabled)")
                            elif not discord_api.is_configured:
                                print(f"ℹ️ Discord not configured (missing bot token or channel ID)")
                        
                        # Validate the parsed signal (general validation)
                        validation = signal_processor.validate_signal(parsed_data)
                        
                        print(f"✅ General Validation: {'PASSED' if validation['valid'] else 'FAILED'}")
                        if not validation["valid"]:
                            print(f"   Errors: {validation.get('errors', [])}")
                        
                        if not validation["valid"]:
                            db.update_signal_status(signal_id, "validation_failed")
                            return jsonify({
                                "success": True,
                                "signal_id": signal_id,
                                "matched_channel": matched_channel,
                                "status": "validation_failed",
                                "message": "Signal matched and parsed but validation failed",
                                "validation_errors": validation["errors"],
                                "parsed_signal": parsed_data
                            }), 200
                        
                        # Validate required options fields before execution
                        options_validation = signal_processor.validate_options_signal(parsed_data)
                        
                        print(f"✅ Options Validation: {'PASSED' if options_validation['valid'] else 'FAILED'}")
                        if not options_validation["valid"]:
                            print(f"   Errors: {options_validation.get('errors', [])}")
                            print(f"   Missing Fields: {options_validation.get('missing_fields', [])}")
                            db.update_signal_status(signal_id, "validation_failed")
                            return jsonify({
                                "success": True,
                                "signal_id": signal_id,
                                "matched_channel": matched_channel,
                                "status": "validation_failed",
                                "message": "Signal matched and parsed but options validation failed",
                                "validation_errors": options_validation["errors"],
                                "parsed_signal": parsed_data
                            }), 200
                        
                        # Check if it's a BUY order (Smart Executor only processes BUY)
                        # Note: parsed_data uses "action" not "direction"
                        action = parsed_data.get("action", "").upper()
                        print(f"🔍 Checking action: {action} (from parsed_data)")
                        if action != "BUY":
                            return jsonify({
                                "success": True,
                                "signal_id": signal_id,
                                "matched_channel": matched_channel,
                                "status": "skipped",
                                "message": "Signal processed but skipped Smart Executor (only BUY orders are processed)",
                                "parsed_signal": parsed_data
                            }), 200
                        
                        # Prepare data for Smart Trade Executor
                        # Determine platform (default to snaptrade)
                        platform = "snaptrade"  # Default platform
                        
                        # Build executor payload from parsed data
                        executor_payload = {
                            "ticker": parsed_data.get("symbol"),
                            "direction": parsed_data.get("action", "BUY"),
                            "option_type": parsed_data.get("option_type"),
                            "strike_price": parsed_data.get("strike"),
                            "purchase_price": parsed_data.get("purchase_price"),
                            "input_position_size": parsed_data.get("position_size") or parsed_data.get("quantity") or 2,
                            "signal_id": signal_id,
                            "signal_title": title if title else ""  # Pass signal title for budget/selling filter matching
                        }
                        
                        # Add expiration date if present
                        exp_date = parsed_data.get("expiration_date")
                        if exp_date:
                            if isinstance(exp_date, dict):
                                executor_payload["expiration_date"] = exp_date
                            elif isinstance(exp_date, str):
                                # Try to parse YYYY-MM-DD format
                                try:
                                    parts = exp_date.split("-")
                                    if len(parts) == 3:
                                        executor_payload["expiration_date"] = {
                                            "year": parts[0],
                                            "month": parts[1],
                                            "day": parts[2]
                                        }
                                    else:
                                        executor_payload["expiration_date"] = exp_date
                                except:
                                    executor_payload["expiration_date"] = exp_date
                        
                        # Log the payload for debugging
                        print("\n" + "="*80)
                        print("🤖 SMART EXECUTOR HANDOFF (from /api/signals/receive)")
                        print("="*80)
                        print(f"Signal ID: {signal_id}")
                        print(f"Matched Channel: {matched_channel}")
                        print(f"Parsed Data: {json.dumps(parsed_data, indent=2, default=str)}")
                        print(f"Executor Payload: {json.dumps(executor_payload, indent=2, default=str)}")
                        print(f"Platform: {platform}")
                        print("="*80 + "\n")
                        
                        # Execute via Smart Trade Executor
                        try:
                            execution_result = trade_executor.execute_trade(executor_payload, platform)
                            
                            print("\n" + "="*80)
                            print("🤖 SMART EXECUTOR RESULT (from /api/signals/receive)")
                            print("="*80)
                            print(f"Success: {execution_result.get('success')}")
                            if execution_result.get('success'):
                                print(f"Order ID: {execution_result.get('order_id')}")
                                print(f"Filled Price: ${execution_result.get('filled_price')}")
                                print(f"Position Size: {execution_result.get('position_size')}")
                            else:
                                print(f"Failed at Step: {execution_result.get('step_failed')}")
                                print(f"Error: {execution_result.get('error')}")
                                if execution_result.get('log'):
                                    print(f"Execution Log (last 5 lines):")
                                    log_lines = execution_result.get('log', [])
                                    for line in log_lines[-5:]:
                                        print(f"  {line}")
                            print("="*80 + "\n")
                            
                            if execution_result["success"]:
                                db.update_signal_status(signal_id, "executed")
                                return jsonify({
                                    "success": True,
                                    "signal_id": signal_id,
                                    "matched_channel": matched_channel,
                                    "status": "executed",
                                    "message": "Signal matched, processed, and executed via Smart Executor",
                                    "parsed_signal": parsed_data,
                                    "executor_result": {
                                        "order_id": execution_result.get("order_id"),
                                        "filled_price": execution_result.get("filled_price"),
                                        "position_size": execution_result.get("position_size"),
                                        "expiration_date": execution_result.get("expiration_date"),
                                        "fill_attempts": execution_result.get("fill_attempts")
                                    }
                                }), 200
                            else:
                                db.update_signal_status(signal_id, "execution_failed")
                                return jsonify({
                                    "success": True,
                                    "signal_id": signal_id,
                                    "matched_channel": matched_channel,
                                    "status": "execution_failed",
                                    "message": f"Signal processed but Smart Executor failed at step {execution_result.get('step_failed', 'unknown')}",
                                    "parsed_signal": parsed_data,
                                    "executor_error": execution_result.get("error"),
                                    "executor_log": execution_result.get("log", [])
                                }), 200
                        except Exception as executor_error:
                            print(f"Error executing trade via Smart Executor: {executor_error}")
                            db.update_signal_status(signal_id, "execution_error")
                            return jsonify({
                                "success": True,
                                "signal_id": signal_id,
                                "matched_channel": matched_channel,
                                "status": "execution_error",
                                "message": "Signal processed but Smart Executor encountered an error",
                                "parsed_signal": parsed_data,
                                "error": str(executor_error)
                            }), 200
                    else:
                        # Parsing failed, but signal was matched
                        print("\n" + "="*80)
                        print("❌ SIGNAL PARSING FAILED (/api/signals/receive)")
                        print("="*80)
                        print(f"Signal ID: {signal_id}")
                        print(f"Matched Channel: {matched_channel}")
                        print(f"Signal Content: {signal_content[:200]}...")
                        print(f"Error: {parsed_result.get('error')}")
                        raw_response = parsed_result.get("raw_response")
                        if raw_response:
                            print(f"\n--- RAW OPENAI RESPONSE (for debugging) ---")
                            print(raw_response)
                            print(f"--- END RAW RESPONSE (length: {len(raw_response)} chars) ---")
                        else:
                            print("\n⚠️ No raw_response available in error result")
                        print("="*80 + "\n")
                        
                        db.update_signal_status(signal_id, "parse_failed", None)
                        return jsonify({
                            "success": True,
                            "signal_id": signal_id,
                            "matched_channel": matched_channel,
                            "status": "parse_failed",
                            "message": "Signal matched but parsing failed",
                            "error": parsed_result.get("error")
                        }), 200
                else:
                    # Channel exists but no prompt
                    db.update_signal_status(signal_id, "no_prompt", None)
                    return jsonify({
                        "success": True,
                        "signal_id": signal_id,
                        "matched_channel": matched_channel,
                        "status": "no_prompt",
                        "message": "Signal matched but channel has no prompt"
                    }), 200
            except Exception as e:
                print(f"Error processing matched signal: {e}")
                return jsonify({
                    "success": True,
                    "signal_id": signal_id,
                    "matched_channel": matched_channel,
                    "status": "error",
                    "message": "Signal matched but processing failed",
                    "error": str(e)
                }), 200
        else:
            # No match found - update channel_name to UNMATCHED
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE trade_signals 
                    SET channel_name = ?, status = ?
                    WHERE id = ?
                """, (channel_name, initial_status, signal_id))
                conn.commit()
            except Exception as e:
                print(f"Error updating channel_name: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            return jsonify({
                "success": True,
                "signal_id": signal_id,
                "matched_channel": None,
                "status": "unmatched",
                "message": "Signal recorded but no matching channel found"
            }), 200
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"\n{'='*80}")
        print("❌ ERROR in /api/signals/receive")
        print(f"{'='*80}")
        print(f"Error: {str(e)}")
        print(f"Traceback:\n{error_traceback}")
        print(f"{'='*80}\n")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "details": error_traceback if app.debug else "Check server logs for details"
        }), 500


@app.route('/api/signals/recent', methods=['GET'])
def get_recent_signals():
    """Get recent trade signals with their status."""
    try:
        limit = request.args.get('limit', 50, type=int)
        signals_list = db.get_recent_signals(limit)
        return jsonify({"signals": signals_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/signals/all', methods=['GET'])
def get_all_signals():
    """Get all signals including external sources."""
    try:
        limit = request.args.get('limit', 100, type=int)
        source = request.args.get('source', None)  # Optional filter
        
        if source:
            # Get signals from specific source
            signals_list = signals.get_signals(limit=limit, source=source)
        else:
            # Get all signals (mix of all sources)
            signals_list = signals.get_signals(limit=limit, source=None)
        
        # Add dashboard_read and x_read status to each signal
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            for signal in signals_list:
                signal_id = signal.get('id')
                if signal_id:
                    cursor.execute("""
                        SELECT dashboard_read, x_read 
                        FROM trade_signals 
                        WHERE id = ?
                    """, (signal_id,))
                    row = cursor.fetchone()
                    if row:
                        signal['dashboard_read'] = bool(row[0]) if row[0] is not None else False
                        signal['x_read'] = bool(row[1]) if row[1] is not None else False
                    else:
                        signal['dashboard_read'] = False
                        signal['x_read'] = False
                else:
                    signal['dashboard_read'] = False
                    signal['x_read'] = False
        finally:
            conn.close()
        
        return jsonify({"signals": signals_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/signals/x-channel', methods=['GET'])
def get_x_channel_signals():
    """Get signals from 'x' channel (for real-time display in Discord module)."""
    try:
        limit = request.args.get('limit', 50, type=int)
        since_id = request.args.get('since_id', None, type=int)  # Optional: get signals after this ID
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if 'message' column exists
            cursor.execute("PRAGMA table_info(trade_signals)")
            columns = [col[1] for col in cursor.fetchall()]
            has_message = 'message' in columns
            
            if since_id:
                # Get signals after the specified ID
                if has_message:
                    cursor.execute("""
                        SELECT id, source, title, message, channel_name, status, received_at, raw_content
                        FROM trade_signals 
                        WHERE channel_name = 'x' AND id > ?
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (since_id, limit))
                else:
                    cursor.execute("""
                        SELECT id, source, title, raw_content as message, channel_name, status, received_at, raw_content
                        FROM trade_signals 
                        WHERE channel_name = 'x' AND id > ?
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (since_id, limit))
            else:
                # Get latest signals
                if has_message:
                    cursor.execute("""
                        SELECT id, source, title, message, channel_name, status, received_at, raw_content
                        FROM trade_signals 
                        WHERE channel_name = 'x'
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor.execute("""
                        SELECT id, source, title, raw_content as message, channel_name, status, received_at, raw_content
                        FROM trade_signals 
                        WHERE channel_name = 'x'
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
            
            rows = cursor.fetchall()
            signals_list = []
            
            # Get read status for all signals
            signal_ids = [row[0] for row in rows]
            read_status_map = {}
            if signal_ids:
                placeholders = ','.join(['?'] * len(signal_ids))
                cursor.execute(f"""
                    SELECT id, dashboard_read, x_read 
                    FROM trade_signals 
                    WHERE id IN ({placeholders})
                """, signal_ids)
                for read_row in cursor.fetchall():
                    read_status_map[read_row[0]] = {
                        'dashboard_read': bool(read_row[1]) if read_row[1] is not None else False,
                        'x_read': bool(read_row[2]) if read_row[2] is not None else False
                    }
            
            for row in rows:
                signal_id = row[0]
                read_status = read_status_map.get(signal_id, {'dashboard_read': False, 'x_read': False})
                signal = {
                    "id": signal_id,
                    "source": row[1] or "external",
                    "title": row[2] or "",
                    "message": row[3] or "",
                    "channel_name": row[4] or "x",
                    "status": row[5] or "matched",
                    "received_at": row[6],
                    "raw_content": row[7] or "",
                    "dashboard_read": read_status['dashboard_read'],
                    "x_read": read_status['x_read']
                }
                signals_list.append(signal)
            
            return jsonify({
                "success": True,
                "signals": signals_list,
                "count": len(signals_list)
            }), 200
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/signals/<int:signal_id>', methods=['DELETE'])
def delete_signal(signal_id):
    """Delete a single signal by ID."""
    try:
        result = db.delete_signal(signal_id)
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": "Signal deleted successfully",
                "signal_deleted": result["signal_deleted"],
                "executions_deleted": result["executions_deleted"],
                "total_deleted": result["total_deleted"]
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Signal not found")
            }), 404
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/signals/clear-by-source', methods=['POST'])
def clear_signals_by_source():
    """
    Clear all signals from a specific source.
    
    Expected JSON format:
    {
        "source": "chrome_extension" (optional, if not provided or empty string clears all)
    }
    """
    try:
        data = request.get_json() or {}
        source = data.get('source', '').strip() if data.get('source') else ''
        
        if source:
            # Clear signals from specific source
            result = db.clear_signals_by_source(source)
        else:
            # Clear all signals if no source specified
            result = db.clear_all_signals()
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"Cleared {result['total_deleted']} record(s) ({result['signals_deleted']} signals, {result['executions_deleted']} executions)",
                "signals_deleted": result["signals_deleted"],
                "executions_deleted": result["executions_deleted"],
                "total_deleted": result["total_deleted"]
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to clear signals")
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error clearing signals: {str(e)}"}), 500


@app.route('/api/signals/clear', methods=['POST'])
def clear_signals():
    """
    Clear all trade signals and executions.
    
    Optional JSON body:
    {
        "channel_name": "optional_channel_name"  // If provided, only clear signals for this channel
    }
    """
    try:
        data = request.get_json() or {}
        channel_name = data.get('channel_name', '').strip()
        
        if channel_name:
            # Clear signals for specific channel
            result = db.clear_signals_by_channel(channel_name)
        else:
            # Clear all signals
            result = db.clear_all_signals()
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"Cleared {result['total_deleted']} record(s) ({result['signals_deleted']} signals, {result['executions_deleted']} executions)",
                "signals_deleted": result["signals_deleted"],
                "executions_deleted": result["executions_deleted"],
                "total_deleted": result["total_deleted"]
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to clear signals")
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error clearing signals: {str(e)}"}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    return jsonify({
        "execution_model": execution_model,
        "builder_model": builder_model,
        "grok_model": grok_api.model if grok_api else "grok-2-1212",
        "openai_api_key": openai_api_key[:20] + "..." if openai_api_key else None,
        "openai_configured": openai_api_key is not None,
        "webull_authenticated": False,  # Webull removed - use SnapTrade via proxy
        "paper_trading": False  # Webull removed - use SnapTrade via proxy
    }), 200


@app.route('/api/config/update', methods=['POST'])
def update_config():
    """Update configuration (models and API keys) and save to .env file."""
    global openai_api_key, execution_model, builder_model, prompt_builder, signal_processor
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        config_updated = False
        
        # Update OpenAI API key if provided
        if 'openai_api_key' in data and data['openai_api_key']:
            new_key = data['openai_api_key'].strip()
            if new_key and new_key != openai_api_key:
                openai_api_key = new_key
                config_updated = True
                # Reinitialize AI components with new key (lazy initialization - no client created yet)
                prompt_builder = PromptBuilder(api_key=openai_api_key, model=builder_model)
                signal_processor = SignalProcessor(api_key=openai_api_key, model=execution_model)
        
        # Update models if provided
        if 'execution_model' in data and data['execution_model']:
            new_model = data['execution_model'].strip()
            if new_model and new_model != execution_model:
                execution_model = new_model
                config_updated = True
                if openai_api_key:
                    # Reinitialize with new model (lazy initialization - no client created yet)
                    signal_processor = SignalProcessor(api_key=openai_api_key, model=execution_model)
        
        if 'builder_model' in data and data['builder_model']:
            new_model = data['builder_model'].strip()
            if new_model and new_model != builder_model:
                builder_model = new_model
                config_updated = True
                if openai_api_key:
                    # Reinitialize with new model (lazy initialization - no client created yet)
                    prompt_builder = PromptBuilder(api_key=openai_api_key, model=builder_model)
        
        # Save configuration to .env file
        if config_updated:
            try:
                # Use the same env_file_path that was used for loading at startup
                env_path = env_file_path
                print(f"DEBUG: Saving config to: {env_path}")
                
                # Ensure directory exists (important for first-time Android setup)
                env_dir = os.path.dirname(env_path)
                if env_dir:
                    os.makedirs(env_dir, exist_ok=True)
                    print(f"DEBUG: Directory exists: {os.path.exists(env_dir)}")
                
                # Read existing .env file if it exists
                env_lines = []
                if os.path.exists(env_path):
                    with open(env_path, 'r', encoding='utf-8') as f:
                        env_lines = f.readlines()
                
                # Update or add configuration values
                updated_lines = []
                keys_to_update = {
                    'OPENAI_API_KEY': openai_api_key or '',
                    'EXECUTION_MODEL': execution_model,
                    'BUILDER_MODEL': builder_model
                }
                
                keys_found = set()
                
                # Process existing lines
                for line in env_lines:
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith('#'):
                        updated_lines.append(line)
                        continue
                    
                    # Check if this line contains a key we want to update
                    updated = False
                    for key, value in keys_to_update.items():
                        if line_stripped.startswith(f'{key}='):
                            # Update the value
                            updated_lines.append(f'{key}={value}\n')
                            keys_found.add(key)
                            updated = True
                            break
                    
                    if not updated:
                        updated_lines.append(line)
                
                # Add any keys that weren't found
                for key, value in keys_to_update.items():
                    if key not in keys_found:
                        # Find the right place to insert based on key type
                        insert_index = len(updated_lines)
                        
                        if key == 'OPENAI_API_KEY':
                            # Insert after OpenAI API Keys comment
                            for i, line in enumerate(updated_lines):
                                if '# OpenAI API Keys' in line:
                                    insert_index = i + 1
                                    break
                        elif key in ['EXECUTION_MODEL', 'BUILDER_MODEL']:
                            # Insert after Model Configuration comment
                            for i, line in enumerate(updated_lines):
                                if '# Model Configuration' in line:
                                    # Find the next non-comment, non-empty line
                                    for j in range(i + 1, len(updated_lines)):
                                        if updated_lines[j].strip() and not updated_lines[j].strip().startswith('#'):
                                            insert_index = j
                                            break
                                    if insert_index == len(updated_lines):
                                        insert_index = i + 1
                                    break
                        
                        updated_lines.insert(insert_index, f'{key}={value}\n')
                
                # Write back to .env file
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                
                print(f"DEBUG: Config saved successfully to {env_path}")
                print(f"DEBUG: File size after save: {os.path.getsize(env_path)} bytes")
                
                # Reload .env file to ensure latest values are in memory
                load_dotenv(dotenv_path=env_path, override=True)
                # Update module-level variables (global already declared at function start)
                openai_api_key = os.getenv('OPENAI_API_KEY')
                execution_model = os.getenv('EXECUTION_MODEL', 'gpt-4-turbo-preview')
                builder_model = os.getenv('BUILDER_MODEL', 'gpt-4-turbo-preview')
                
                # Reinitialize AI components if API key is available
                if openai_api_key:
                    prompt_builder = PromptBuilder(api_key=openai_api_key, model=builder_model)
                    signal_processor = SignalProcessor(api_key=openai_api_key, model=execution_model)
                
                print(f"DEBUG: Config reloaded - execution_model={execution_model}, builder_model={builder_model}")
                
            except Exception as save_error:
                # Log error but don't fail the request
                print(f"Warning: Failed to save configuration to .env file: {str(save_error)}")
                import traceback
                print(f"DEBUG: Traceback: {traceback.format_exc()}")
        
        return jsonify({
            "success": True,
            "message": "Configuration updated successfully",
            "config": {
                "execution_model": execution_model,
                "builder_model": builder_model,
                "openai_configured": openai_api_key is not None
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to update config: {str(e)}"}), 500


@app.route('/api/config/paper-trading', methods=['POST'])
def set_paper_trading():
    """Enable or disable paper trading mode."""
    try:
        data = request.get_json()
        paper_mode = data.get('paper_trading', True)
        
        # Webull removed - paper trading setting handled by executor directly
        
        return jsonify({
            "success": True,
            "paper_trading": paper_mode
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/config/test-model', methods=['POST'])
def test_model():
    """Test an AI model with a simple request."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        api_key = data.get('api_key', openai_api_key)
        model_name = data.get('model_name', '').strip()
        
        if not api_key:
            return jsonify({
                "success": False,
                "error": "No API key provided"
            }), 400
        
        if not model_name:
            return jsonify({
                "success": False,
                "error": "No model name provided"
            }), 400
        
        # Test the model with a simple request
        try:
            # Create a test client with the provided API key
            # httpx==0.25.2 is pinned in build.gradle for compatibility
            test_client = OpenAI(api_key=api_key)
            
            # For openai==1.3.0, only max_tokens is supported
            # max_completion_tokens was added in later versions
            # Always use max_tokens for compatibility
            use_max_completion_tokens = False  # Disabled for openai 1.3.0
            model_lower = model_name.lower()
            
            start_time = datetime.now()
            
            # Check if model requires default temperature
            # Models like o1, o3 series only support temperature=1 (default)
            model_lower = model_name.lower()
            requires_default_temp = (
                'o1' in model_lower or 
                'o3' in model_lower or
                model_lower.startswith('o1-') or
                model_lower.startswith('o3-') or
                'gpt-o1' in model_lower or
                'gpt-o3' in model_lower
            )
            
            # Build request parameters
            request_params = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Test successful!' if you can read this."}
                ]
            }
            
            # Use temperature 1.0 (default) for all models for consistency
            request_params["temperature"] = 1.0
            
            # Try the appropriate parameter, with fallback if needed
            try:
                if use_max_completion_tokens:
                    request_params["max_completion_tokens"] = 50
                else:
                    request_params["max_tokens"] = 50
                
                response = test_client.chat.completions.create(**request_params)
            except Exception as api_error:
                # Handle various API errors with fallbacks
                # Get error message from multiple sources
                error_str = str(api_error).lower()
                error_repr = repr(api_error).lower()
                
                # Try to get error details from OpenAI error object if available
                error_message = error_str
                error_code = None
                error_param = None
                
                # Check for OpenAI API error structure
                if hasattr(api_error, 'response'):
                    try:
                        if hasattr(api_error.response, 'json'):
                            error_data = api_error.response.json()
                            if 'error' in error_data:
                                if 'message' in error_data['error']:
                                    error_message = str(error_data['error']['message']).lower()
                                if 'code' in error_data['error']:
                                    error_code = str(error_data['error']['code']).lower()
                                if 'param' in error_data['error']:
                                    error_param = str(error_data['error']['param']).lower()
                    except:
                        pass
                
                # Also check error body if available
                if hasattr(api_error, 'body'):
                    try:
                        import json
                        if isinstance(api_error.body, dict):
                            if 'error' in api_error.body:
                                if 'message' in api_error.body['error']:
                                    error_message = str(api_error.body['error']['message']).lower()
                                if 'code' in api_error.body['error']:
                                    error_code = str(api_error.body['error']['code']).lower()
                                if 'param' in api_error.body['error']:
                                    error_param = str(api_error.body['error']['param']).lower()
                    except:
                        pass
                
                # Combine all error message sources
                all_error_text = f"{error_str} {error_repr} {error_message}".lower()
                
                # Check for temperature errors - check param, code, and message
                # Be very aggressive - if temperature is mentioned with any unsupported/error, retry
                is_temp_error = (
                    error_param == 'temperature' or
                    (error_param == 'temperature' and error_code == 'unsupported_value') or
                    ('temperature' in all_error_text and 'unsupported' in all_error_text) or
                    ('temperature' in all_error_text and 'does not support' in all_error_text) or
                    ('temperature' in all_error_text and 'only the default' in all_error_text) or
                    ('temperature' in all_error_text and 'default (1)' in all_error_text) or
                    ('temperature' in all_error_text and 'not support' in all_error_text)
                )
                
                if is_temp_error:
                    # Remove temperature and retry (will use default)
                    request_params.pop("temperature", None)
                    # Also remove max tokens params to start fresh
                    request_params.pop("max_tokens", None)
                    request_params.pop("max_completion_tokens", None)
                    # Re-add the appropriate token param
                    if use_max_completion_tokens:
                        request_params["max_completion_tokens"] = 50
                    else:
                        request_params["max_tokens"] = 50
                    try:
                        response = test_client.chat.completions.create(**request_params)
                    except Exception as retry_error:
                        # If still fails, re-raise original error
                        raise api_error
                elif 'max_tokens' in all_error_text and 'not supported' in all_error_text:
                    # For openai 1.3.0, max_completion_tokens is not supported
                    # Just remove the parameter and retry
                    request_params.pop("max_tokens", None)
                    response = test_client.chat.completions.create(**request_params)
                elif 'max_completion_tokens' in all_error_text and 'not supported' in all_error_text:
                    # For openai 1.3.0, always use max_tokens
                    request_params.pop("max_completion_tokens", None)
                    request_params["max_tokens"] = 50
                    response = test_client.chat.completions.create(**request_params)
                elif 'temperature' in request_params and not is_temp_error:
                    # Last resort: if temperature is set and we got an error (but didn't detect it as temp error),
                    # try without it. This catches edge cases where error detection might have missed something.
                    request_params.pop("temperature", None)
                    try:
                        response = test_client.chat.completions.create(**request_params)
                    except:
                        # If still fails, re-raise original error
                        raise api_error
                else:
                    # Re-raise if it's a different error
                    raise
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            response_text = response.choices[0].message.content
            
            return jsonify({
                "success": True,
                "model": model_name,
                "response": response_text,
                "response_time": f"{response_time:.2f}s",
                "tokens_used": response.usage.total_tokens if response.usage else "N/A"
            }), 200
            
        except Exception as e:
            error_message = str(e)
            print(f"DEBUG: test_model inner exception: {error_message}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            
            # Provide helpful error messages
            if "model_not_found" in error_message or "does not exist" in error_message:
                return jsonify({
                    "success": False,
                    "error": f"Model '{model_name}' not found",
                    "suggestion": "Check the model name. Available: gpt-4, gpt-4-turbo-preview, gpt-3.5-turbo, gpt-4o, gpt-4o-mini"
                }), 400
            elif "invalid_api_key" in error_message or "Incorrect API key" in error_message:
                return jsonify({
                    "success": False,
                    "error": "Invalid API key",
                    "suggestion": "Check your OpenAI API key"
                }), 401
            elif "quota" in error_message.lower():
                return jsonify({
                    "success": False,
                    "error": "API quota exceeded",
                    "suggestion": "Check your OpenAI account billing and usage limits"
                }), 429
            else:
                return jsonify({
                    "success": False,
                    "error": f"Model test failed: {error_message}"
                }), 400
                
    except Exception as e:
        print(f"DEBUG: test_model outer exception: {str(e)}")
        print(f"DEBUG: Exception type: {type(e).__name__}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Test error: {str(e)}"
        }), 500


@app.route('/api/etrade/status', methods=['GET'])
def etrade_status():
    return jsonify({
        "authenticated": etrade_api.is_authenticated,
        "sandbox": etrade_api.sandbox,
        "has_credentials": bool(etrade_api.consumer_key and etrade_api.consumer_secret),
        "has_sandbox_keys": bool(db.get_setting("etrade_sandbox_key", "")),
        "has_prod_keys": bool(db.get_setting("etrade_prod_key", ""))
    }), 200


@app.route('/api/etrade/config', methods=['GET'])
def etrade_get_config():
    sandbox_flag = db.get_setting("etrade_use_sandbox", "true").lower() == "true"
    return jsonify({
        "success": True,
        "sandbox": sandbox_flag,
        "has_sandbox_keys": bool(db.get_setting("etrade_sandbox_key", "")),
        "has_prod_keys": bool(db.get_setting("etrade_prod_key", "")),
        "sandbox_consumer_key": db.get_setting("etrade_sandbox_key", ""),
        "sandbox_consumer_secret": db.get_setting("etrade_sandbox_secret", ""),
        "prod_consumer_key": db.get_setting("etrade_prod_key", ""),
        "prod_consumer_secret": db.get_setting("etrade_prod_secret", ""),
    }), 200


@app.route('/api/etrade/config', methods=['POST'])
def etrade_save_config():
    data = request.get_json() or {}
    sandbox_key = data.get("sandbox_consumer_key", "").strip()
    sandbox_secret = data.get("sandbox_consumer_secret", "").strip()
    prod_key = data.get("prod_consumer_key", "").strip()
    prod_secret = data.get("prod_consumer_secret", "").strip()
    sandbox = data.get("sandbox", True)

    # Persist sandbox creds
    if sandbox_key:
        db.save_setting("etrade_sandbox_key", sandbox_key)
    if sandbox_secret:
        db.save_setting("etrade_sandbox_secret", sandbox_secret)

    # Persist prod creds
    if prod_key:
        db.save_setting("etrade_prod_key", prod_key)
    if prod_secret:
        db.save_setting("etrade_prod_secret", prod_secret)

    db.save_setting("etrade_use_sandbox", "true" if sandbox else "false")

    # Determine active credentials (fall back to stored)
    active_key = sandbox_key if sandbox else prod_key
    active_secret = sandbox_secret if sandbox else prod_secret
    if sandbox and not active_key:
        active_key = db.get_setting("etrade_sandbox_key", "")
    if sandbox and not active_secret:
        active_secret = db.get_setting("etrade_sandbox_secret", "")
    if (not sandbox) and not active_key:
        active_key = db.get_setting("etrade_prod_key", "")
    if (not sandbox) and not active_secret:
        active_secret = db.get_setting("etrade_prod_secret", "")

    # Update live instance
    etrade_api.update_credentials(active_key, active_secret, sandbox)

    return jsonify({
        "success": True,
        "sandbox": sandbox,
        "has_sandbox_keys": bool(db.get_setting("etrade_sandbox_key", "")),
        "has_prod_keys": bool(db.get_setting("etrade_prod_key", "")),
    }), 200


@app.route('/api/etrade/test-keys', methods=['POST'])
def etrade_test_keys():
    data = request.get_json() or {}
    consumer_key = data.get("consumer_key", "").strip()
    consumer_secret = data.get("consumer_secret", "").strip()
    sandbox = data.get("sandbox", True)

    result = etrade_api.test_credentials(consumer_key, consumer_secret, sandbox)
    if result.get("success"):
        return jsonify({"success": True, "sandbox": sandbox}), 200
    return jsonify({"success": False, "error": result.get("error", "Test failed"), "sandbox": sandbox}), 400


@app.route('/api/etrade/oauth/request-token', methods=['GET'])
def etrade_get_request_token():
    result = etrade_api.get_request_token()
    if result.get("success"):
        return jsonify({
            "success": True,
            "authorization_url": result.get("authorization_url"),
            "request_token": result.get("request_token")
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get request token")}), 400


@app.route('/api/etrade/oauth/access-token', methods=['POST'])
def etrade_get_access_token():
    data = request.get_json() or {}
    verifier = data.get('verifier')
    if not verifier:
        return jsonify({"success": False, "error": "Verifier code required"}), 400
    result = etrade_api.get_access_token(verifier)
    if result.get("success"):
        accounts_result = etrade_api.get_accounts_list()
        default_account_id = None
        if accounts_result.get("success") and accounts_result.get("accounts"):
            default_account_id = accounts_result.get("default_account_id")
        return jsonify({
            "success": True,
            "message": "Authentication successful",
            "default_account_id": default_account_id
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get access token")}), 400


@app.route('/api/etrade/accounts', methods=['GET'])
def etrade_get_accounts():
    if not etrade_api.is_authenticated:
        return jsonify({"success": False, "error": "Not authenticated", "accounts": []}), 401
    result = etrade_api.get_accounts_list()
    if result.get("success"):
        return jsonify({
            "success": True,
            "accounts": result.get("accounts", []),
            "default_account_id": result.get("default_account_id")
        }), 200
    return jsonify({
        "success": False,
        "error": result.get("error", "Failed to get accounts"),
        "status_code": result.get("status_code")
    }), 400


@app.route('/api/etrade/accounts/<account_id>/balance', methods=['GET'])
def etrade_get_balance(account_id):
    inst_type = request.args.get('instType', 'BROKERAGE')
    result = etrade_api.get_account_balance(account_id, inst_type)
    if result.get("success"):
        return jsonify({"success": True, "balance": result.get("balance", {})}), 200
    return jsonify({
        "success": False,
        "error": result.get("error", "Failed to get balance"),
        "status_code": result.get("status_code")
    }), 400


@app.route('/api/etrade/accounts/<account_id>/portfolio', methods=['GET'])
def etrade_get_portfolio(account_id):
    result = etrade_api.get_account_portfolio(account_id)
    if result.get("success"):
        return jsonify({"success": True, "portfolio": result.get("portfolio", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get portfolio")}), 400


@app.route('/api/etrade/accounts/<account_id>/orders', methods=['GET'])
def etrade_get_orders(account_id):
    status = request.args.get('status', 'OPEN')
    result = etrade_api.get_orders(account_id, status)
    if result.get("success"):
        return jsonify({"success": True, "orders": result.get("orders", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get orders")}), 400


@app.route('/api/etrade/accounts/<account_id>/orders/<order_id>', methods=['GET'])
def etrade_get_order_by_id(account_id, order_id):
    """Lookup a specific order by ID across all statuses including EXPIRED"""
    try:
        # Search through different order statuses (including EXPIRED for historical orders)
        statuses = ["OPEN", "EXECUTED", "CANCELLED", "REJECTED", "EXPIRED"]
        
        for status in statuses:
            result = etrade_api.get_orders(account_id, status)
            if result.get("success"):
                orders = result.get("orders", {})
                order_list = orders.get("Order", [])
                
                # Handle both single order and list of orders
                if not isinstance(order_list, list):
                    order_list = [order_list] if order_list else []
                
                # Search for matching order ID
                for order in order_list:
                    if str(order.get("orderId")) == str(order_id):
                        return jsonify({
                            "success": True,
                            "order": order,
                            "status": status
                        }), 200
        
        # Order not found in any status
        return jsonify({
            "success": False,
            "error": f"Order ID {order_id} not found in any status (OPEN, EXECUTED, CANCELLED, REJECTED, EXPIRED)"
        }), 404
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/etrade/accounts/<account_id>/preview-order', methods=['POST'])
def etrade_preview_order(account_id):
    order_xml = request.get_data(as_text=True)
    if not order_xml:
        return jsonify({"success": False, "error": "Order XML required"}), 400
    result = etrade_api.preview_order(account_id, order_xml)
    if result.get("success"):
        return jsonify({"success": True, "preview": result.get("preview", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to preview order")}), 400


@app.route('/api/etrade/accounts/<account_id>/place-order', methods=['POST'])
def etrade_place_order(account_id):
    order_xml = request.get_data(as_text=True)
    if not order_xml:
        return jsonify({"success": False, "error": "Order XML required"}), 400
    result = etrade_api.place_order(account_id, order_xml)
    if result.get("success"):
        return jsonify({"success": True, "order": result.get("order", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to place order")}), 400


@app.route('/api/etrade/accounts/<account_id>/cancel-order', methods=['POST'])
def etrade_cancel_order(account_id):
    data = request.get_json() or {}
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"success": False, "error": "Order ID required"}), 400
    result = etrade_api.cancel_order(account_id, order_id)
    return jsonify(result), 200 if result.get("success") else 400


@app.route('/api/etrade/quote/<symbol>', methods=['GET'])
def etrade_get_quote(symbol):
    result = etrade_api.get_quote(symbol)
    if result.get("success"):
        return jsonify({"success": True, "quote": result.get("quote", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get quote")}), 400


@app.route('/api/etrade/options/expiration-dates', methods=['GET'])
def etrade_get_option_expiration_dates():
    """Get available option expiration dates for a symbol."""
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({"success": False, "error": "symbol parameter is required"}), 400
    
    result = etrade_api.get_option_expiration_dates(symbol)
    if result.get("success"):
        return jsonify({
            "success": True,
            "expiration_dates": result.get("expiration_dates", []),
            "nearest_date": result.get("nearest_date")
        }), 200
    return jsonify({
        "success": False,
        "error": result.get("error", "Failed to get option expiration dates"),
        "status_code": result.get("status_code")
    }), 400


@app.route('/api/etrade/options/chain', methods=['GET'])
def etrade_get_option_chain():
    symbol = request.args.get('symbol')
    expiry_year = request.args.get('expiryYear') or request.args.get('expiry_year')
    expiry_month = request.args.get('expiryMonth') or request.args.get('expiry_month')
    expiry_day = request.args.get('expiryDay') or request.args.get('expiry_day')
    strike_price_near = request.args.get('strikePriceNear') or request.args.get('strike_price_near')
    no_of_strikes = request.args.get('noOfStrikes') or request.args.get('no_of_strikes')
    include_weekly = request.args.get('includeWeekly', 'true').lower() != 'false'

    if not symbol or not expiry_year or not expiry_month or not expiry_day:
        return jsonify({"success": False, "error": "symbol, expiryYear, expiryMonth, expiryDay are required"}), 400

    try:
        expiry_year = int(expiry_year)
        expiry_month = int(expiry_month)
        expiry_day = int(expiry_day)
        strike_price_near_val = float(strike_price_near) if strike_price_near else None
        no_of_strikes_val = int(no_of_strikes) if no_of_strikes else None
    except ValueError:
        return jsonify({"success": False, "error": "Invalid numeric value in parameters"}), 400

    result = etrade_api.get_option_chain(
        symbol,
        expiry_year,
        expiry_month,
        expiry_day,
        strike_price_near=strike_price_near_val,
        no_of_strikes=no_of_strikes_val,
        include_weekly=include_weekly,
    )
    if result.get("success"):
        return jsonify({"success": True, "chain": result.get("chain", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get option chain")}), 400


@app.route('/api/etrade/accounts/<account_id>/preview-options-order', methods=['POST'])
def etrade_preview_options_order(account_id):
    payload = request.get_json() or {}
    if not payload.get("option_symbol"):
        return jsonify({"success": False, "error": "option_symbol is required"}), 400
    result = etrade_api.preview_options_order(account_id, payload)
    if result.get("success"):
        return jsonify({"success": True, "preview": result.get("preview", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to preview options order")}), 400


@app.route('/api/etrade/accounts/<account_id>/place-options-order', methods=['POST'])
def etrade_place_options_order(account_id):
    payload = request.get_json() or {}
    if not payload.get("option_symbol"):
        return jsonify({"success": False, "error": "option_symbol is required"}), 400
    result = etrade_api.place_options_order(account_id, payload)
    if result.get("success"):
        return jsonify({"success": True, "order": result.get("order", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to place options order")}), 400


@app.route('/api/etrade/accounts/<account_id>/preview-equity-order', methods=['POST'])
def etrade_preview_equity_order(account_id):
    payload = request.get_json() or {}
    print(f"\n{'='*80}")
    print(f"👁️  PREVIEW EQUITY ORDER REQUEST")
    print(f"{'='*80}")
    print(f"Account ID: {account_id}")
    print(f"Payload received: {payload}")
    print(f"Payload types: {[(k, type(v).__name__) for k, v in payload.items()]}")
    print(f"{'='*80}\n")
    
    if not payload.get("symbol"):
        return jsonify({"success": False, "error": "symbol is required"}), 400
    result = etrade_api.preview_equity_order(account_id, payload)
    if result.get("success"):
        return jsonify({"success": True, "preview": result.get("preview", {})}), 200
    
    error_response = {
        "success": False,
        "error": result.get("error", "Failed to preview equity order"),
        "status_code": result.get("status_code"),
        "debug_info": result.get("debug_info", {})
    }
    print(f"\n{'='*80}")
    print(f"❌ PREVIEW EQUITY ORDER FAILED")
    print(f"{'='*80}")
    print(f"Error: {error_response['error']}")
    print(f"Status Code: {error_response.get('status_code')}")
    if error_response.get("debug_info"):
        print(f"Debug Info: {error_response['debug_info']}")
    print(f"{'='*80}\n")
    
    return jsonify(error_response), 400


@app.route('/api/etrade/accounts/<account_id>/place-equity-order', methods=['POST'])
def etrade_place_equity_order(account_id):
    payload = request.get_json() or {}
    print(f"\n{'='*80}")
    print(f"📥 PLACE EQUITY ORDER REQUEST")
    print(f"{'='*80}")
    print(f"Account ID: {account_id}")
    print(f"Payload received: {payload}")
    print(f"Payload types: {[(k, type(v).__name__) for k, v in payload.items()]}")
    print(f"{'='*80}\n")
    
    if not payload.get("symbol"):
        return jsonify({"success": False, "error": "symbol is required"}), 400
    
    # Note: E*TRADE API is case-sensitive, must use "PreviewId" (capital P)
    preview_id = payload.get("PreviewId") or payload.get("previewId") or payload.get("preview_id")  # Support multiple formats for backward compatibility
    client_order_id = payload.get("client_order_id")
    if preview_id:
        print(f"✅ PreviewId provided: {preview_id}")
        print(f"✅ Client Order ID: {client_order_id}")
        print("   (This should match the client_order_id from the preview request)")
    else:
        print("⚠️ WARNING: No previewId provided! E*TRADE may reject this order.")
        print("   User should preview the order first to get a previewId.")
    
    print("🔧 Using POST method with PlaceOrderRequest XML (same as options orders)")
    result = etrade_api.place_equity_order(account_id, payload)
    if result.get("success"):
        return jsonify({"success": True, "order": result.get("order", {})}), 200
    
    error_response = {
        "success": False,
        "error": result.get("error", "Failed to place equity order"),
        "status_code": result.get("status_code"),
        "debug_info": result.get("debug_info", {})
    }
    print(f"\n{'='*80}")
    print(f"❌ PLACE EQUITY ORDER FAILED")
    print(f"{'='*80}")
    print(f"Error: {error_response['error']}")
    print(f"Status Code: {error_response.get('status_code')}")
    if error_response.get("debug_info"):
        print(f"Debug Info: {error_response['debug_info']}")
    print(f"{'='*80}\n")
    
    return jsonify(error_response), 400


# ==================== Webull API Endpoints - REMOVED ====================
# All Webull routes removed

# ==================== SnapTrade Proxy Endpoints ====================

@app.route('/api/snaptrade/proxy-url', methods=['GET', 'POST'])
def snaptrade_proxy_url():
    """Get or set the SnapTrade proxy URL (ngrok URL)"""
    if request.method == 'POST':
        data = request.get_json() or {}
        proxy_url = data.get('proxy_url', '').strip().rstrip('/')
        if proxy_url:
            db.save_setting("snaptrade_proxy_url", proxy_url)
            return jsonify({"success": True, "proxy_url": proxy_url}), 200
        return jsonify({"success": False, "error": "proxy_url is required"}), 400
    else:
        proxy_url = db.get_setting("snaptrade_proxy_url", "")
        return jsonify({"success": True, "proxy_url": proxy_url}), 200

@app.route('/api/snaptrade/status', methods=['GET'])
def snaptrade_get_status():
    """Get SnapTrade status via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    
    try:
        response = requests.get(f"{proxy_url}/api/status", timeout=10)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": f"Proxy returned {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/accounts', methods=['GET'])
def snaptrade_get_accounts():
    """Get accounts via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    
    try:
        response = requests.get(f"{proxy_url}/api/accounts", timeout=10)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": f"Proxy returned {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/positions', methods=['GET'])
def snaptrade_get_positions():
    """Get positions via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    account_id = request.args.get('account_id')
    
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    if not account_id:
        return jsonify({"success": False, "error": "account_id is required"}), 400
    
    try:
        response = requests.get(f"{proxy_url}/api/positions", params={"account_id": account_id}, timeout=10)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": f"Proxy returned {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/orders', methods=['GET'])
def snaptrade_get_orders():
    """Get orders via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    account_id = request.args.get('account_id')
    
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    
    try:
        params = {}
        if account_id:
            params['account_id'] = account_id
        response = requests.get(f"{proxy_url}/api/orders", params=params, timeout=10)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": f"Proxy returned {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/options-chain', methods=['GET'])
def snaptrade_get_options_chain():
    """Get options chain via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    symbol = request.args.get('symbol')
    account_id = request.args.get('account_id')
    
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    if not symbol:
        return jsonify({"success": False, "error": "symbol parameter is required"}), 400
    
    try:
        params = {'symbol': symbol}
        if account_id:
            params['account_id'] = account_id
        response = requests.get(f"{proxy_url}/api/options-chain", params=params, timeout=30)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": response.json().get("error", f"Proxy returned {response.status_code}")}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/trade/option', methods=['POST'])
def snaptrade_place_option_trade():
    """Place options trade via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    
    data = request.get_json() or {}
    try:
        response = requests.post(f"{proxy_url}/api/trade/option", json=data, timeout=60)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": response.json().get("error", f"Proxy returned {response.status_code}")}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/snaptrade/trade/equity', methods=['POST'])
def snaptrade_place_equity_trade():
    """Place equity trade via proxy"""
    proxy_url = db.get_setting("snaptrade_proxy_url", "")
    if not proxy_url:
        return jsonify({"success": False, "error": "Proxy URL not configured"}), 400
    
    data = request.get_json() or {}
    try:
        response = requests.post(f"{proxy_url}/api/trade/equity", json=data, timeout=60)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"success": False, "error": response.json().get("error", f"Proxy returned {response.status_code}")}), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== Smart Trade Executor Endpoints ====================

@app.route('/api/smart-executor/enabled', methods=['GET'])
def smart_executor_get_enabled():
    """Get Smart Executor enabled state."""
    try:
        enabled = db.get_setting("smart_executor_enabled", "true").lower() == "true"
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== TradingView Executor API Endpoints (placeholder) ====================
# Webull and duplicate SnapTrade routes removed

@app.route('/placeholder_for_removal', methods=['GET'])
def placeholder_for_removal():
    data = request.get_json() or {}
    app_key = data.get("app_key", "").strip()
    app_secret = data.get("app_secret", "").strip()
    region_id = data.get("region_id", "us").strip()

    result = webull_api.test_credentials(
        app_key=app_key,
        app_secret=app_secret,
        region_id=region_id,
    )
    if result.get("success"):
        return jsonify({
            "success": True,
            "region_id": result.get("region_id", region_id),
            "message": result.get("message", "Credentials valid"),
            "account_ids": result.get("account_ids", []),
        }), 200
    return jsonify({
        "success": False,
        "error": result.get("error", "Test failed"),
        "region_id": result.get("region_id", region_id),
        "account_ids": [],
    }), 400


@app.route('/api/webull/token/create', methods=['POST'])
def webull_create_token():
    """Create a 2FA token. User must verify in Webull App."""
    result = webull_api.create_token()
    if result.get("success"):
        return jsonify({
            "success": True,
            "token": result.get("token"),
            "status": result.get("status"),
            "message": result.get("message", "Token created. Please verify in Webull App.")
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to create token")}), 400


@app.route('/api/webull/token/check', methods=['GET'])
def webull_check_token():
    """Check the status of the current 2FA token."""
    result = webull_api.check_token_status()
    if result.get("success"):
        return jsonify({
            "success": True,
            "token": result.get("token"),
            "status": result.get("status"),
            "message": result.get("message")
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to check token")}), 400


@app.route('/api/webull/accounts', methods=['GET'])
def webull_get_accounts():
    if not webull_api.is_authenticated:
        return jsonify({"success": False, "error": "Not authenticated", "accounts": []}), 401
    result = webull_api.get_accounts_list()
    if result.get("success"):
        return jsonify({
            "success": True,
            "accounts": result.get("accounts", []),
            "default_account_id": result.get("default_account_id")
        }), 200
    return jsonify({
        "success": False,
        "error": result.get("error", "Failed to get accounts"),
    }), 400


@app.route('/api/webull/accounts/<account_id>/set-default', methods=['POST'])
def webull_set_default_account(account_id):
    """Set the default account for Webull operations."""
    try:
        webull_api.set_default_account(account_id)
        # Also save to database if available
        if webull_api.db:
            webull_api.db.save_setting("webull_default_account_id", account_id)
        return jsonify({
            "success": True,
            "message": f"Default account set to {account_id}",
            "default_account_id": account_id
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to set default account: {str(e)}"
        }), 400


@app.route('/api/webull/accounts/<account_id>/balance', methods=['GET'])
def webull_get_balance(account_id):
    # Balance functionality is disabled as requested
    result = webull_api.get_account_balance(account_id)
    return jsonify({
        "success": False,
        "error": result.get("error", "Account balance functionality is disabled. Use portfolio endpoint instead."),
    }), 400


@app.route('/api/webull/accounts/<account_id>/portfolio', methods=['GET'])
def webull_get_portfolio(account_id):
    # Log the account_id received from URL
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🟢 PORTFOLIO ENDPOINT: account_id from URL: '{account_id}'")
    
    # Ensure account_id is not empty
    if not account_id or account_id.strip() == "":
        return jsonify({
            "success": False, 
            "error": f"No account ID provided in URL. Received: '{account_id}'"
        }), 400
    
    # ALWAYS use the account_id from URL, never fall back to default
    result = webull_api.get_account_portfolio(account_id.strip())
    
    # Log the full result for debugging
    logger.info(f"🟢 PORTFOLIO RESULT: success={result.get('success')}, has_portfolio={bool(result.get('portfolio'))}")
    if result.get('portfolio'):
        portfolio = result.get('portfolio', {})
        positions = portfolio.get('Position', [])
        logger.info(f"🟢 POSITIONS COUNT: {len(positions)}")
        if positions:
            logger.info(f"🟢 FIRST POSITION: {positions[0]}")
    
    # Always include account_id in response for debugging
    if result.get("success"):
        response_data = {
            "success": True, 
            "portfolio": result.get("portfolio", {}),
            "account_id": account_id.strip()  # Always include account_id in response
        }
        # Include message if present (e.g., "No positions found for account X")
        if result.get("message"):
            response_data["message"] = result.get("message")
        else:
            # If no message but no positions, add one
            portfolio = result.get("portfolio", {})
            positions = portfolio.get("Position", [])
            if not positions:
                response_data["message"] = f"No positions found for account {account_id.strip()}"
        return jsonify(response_data), 200
    
    # Include account_id in error response too
    error_msg = result.get("error", "Failed to get portfolio")
    return jsonify({
        "success": False, 
        "error": f"{error_msg} (account_id: {account_id.strip()})",
        "account_id": account_id.strip()
    }), 400


@app.route('/api/webull/portfolio', methods=['GET'])
def webull_get_portfolio_query():
    """Alternative portfolio endpoint that accepts account_id as query parameter."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get account_id from query parameter
    account_id = request.args.get('account_id') or request.args.get('accountId')
    
    logger.info(f"Portfolio request received with account_id from query: '{account_id}'")
    
    if not account_id or account_id.strip() == "":
        # Try to use default account
        account_id = webull_api.default_account_id
        logger.info(f"No account_id in query, using default: '{account_id}'")
        if not account_id:
            return jsonify({
                "success": False,
                "error": "No account ID provided. Please provide account_id as query parameter or select a default account.",
                "account_id": None
            }), 400
    
    # Use the account_id
    result = webull_api.get_account_portfolio(account_id.strip())
    
    # Always include account_id in response
    if result.get("success"):
        response_data = {
            "success": True,
            "portfolio": result.get("portfolio", {}),
            "account_id": account_id.strip()
        }
        if result.get("message"):
            response_data["message"] = result.get("message")
        else:
            portfolio = result.get("portfolio", {})
            positions = portfolio.get("Position", [])
            if not positions:
                response_data["message"] = f"No positions found for account {account_id.strip()}"
        return jsonify(response_data), 200
    
    error_msg = result.get("error", "Failed to get portfolio")
    return jsonify({
        "success": False,
        "error": f"{error_msg} (account_id: {account_id.strip()})",
        "account_id": account_id.strip()
    }), 400


@app.route('/api/webull/accounts/<account_id>/orders', methods=['GET'])
def webull_get_orders(account_id):
    result = webull_api.get_orders(account_id)
    if result.get("success"):
        return jsonify({"success": True, "orders": result.get("orders", [])}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get orders")}), 400


@app.route('/api/webull/accounts/<account_id>/place-order', methods=['POST'])
def webull_place_order(account_id):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🟠 PLACE ORDER: account_id from URL: '{account_id}'")
    # Debug logging disabled - uncomment if needed for troubleshooting
    # print(f"[WEBULL_DEBUG] Place order called with account_id: '{account_id}'", flush=True)
    
    payload = request.get_json() or {}
    logger.info(f"🟠 PLACE ORDER: payload: {payload}")
    
    if not payload.get("symbol"):
        return jsonify({"success": False, "error": "symbol is required"}), 400
    
    # Ensure account_id is valid
    if not account_id or account_id.strip() == "" or account_id == "undefined" or account_id == "null":
        return jsonify({"success": False, "error": f"Invalid account_id: '{account_id}'. Please select an account first."}), 400
    
    result = webull_api.place_order(account_id.strip(), payload)
    if result.get("success"):
        # Return both order_id and orderId for frontend compatibility
        order_id = result.get("order_id") or result.get("order", {}).get("PlaceOrderResponse", {}).get("Order", {}).get("orderId")
        return jsonify({
            "success": True, 
            "order_id": order_id,
            "orderId": order_id,  # Also return camelCase for frontend
            "order": result.get("order", {}),
            "message": result.get("message", "Order placed successfully")
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to place order")}), 400


@app.route('/api/webull/accounts/<account_id>/cancel-order', methods=['POST'])
def webull_cancel_order(account_id):
    data = request.get_json() or {}
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"success": False, "error": "Order ID required"}), 400
    result = webull_api.cancel_order(account_id, order_id)
    return jsonify(result), 200 if result.get("success") else 400


@app.route('/api/webull/accounts/<account_id>/order-status/<order_id>', methods=['GET'])
def webull_get_order_status(account_id, order_id):
    result = webull_api.get_order_status(order_id)
    if result.get("success"):
        return jsonify({
            "success": True,
            "status": result.get("status"),
            "filled_quantity": result.get("filled_quantity"),
            "average_price": result.get("average_price"),
        }), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get order status")}), 400


@app.route('/api/webull/quote/<symbol>', methods=['GET'])
def webull_get_quote(symbol):
    import sys
    import json
    sys.stderr.write(f"FLASK_ENDPOINT_DEBUG: /api/webull/quote/{symbol} called\n")
    sys.stderr.flush()
    result = webull_api.get_quote(symbol)
    sys.stderr.write(f"FLASK_ENDPOINT_DEBUG: get_quote returned, success={result.get('success')}\n")
    sys.stderr.flush()
    if result.get("success"):
        quote_data = result.get("quote", {})
        # Debug: Log what we're returning (use stderr so it shows in logcat)
        sys.stderr.write(f"WEBULL_QUOTE_DEBUG: Returning quote for {symbol}\n")
        sys.stderr.write(f"WEBULL_QUOTE_DEBUG: Quote type: {type(quote_data)}\n")
        sys.stderr.write(f"WEBULL_QUOTE_DEBUG: Quote keys: {list(quote_data.keys()) if isinstance(quote_data, dict) else 'NOT DICT'}\n")
        if isinstance(quote_data, dict) and "QuoteResponse" in quote_data:
            quote_response = quote_data.get("QuoteResponse", {})
            quote_data_obj = quote_response.get("QuoteData", {})
            sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData type: {type(quote_data_obj)}\n")
            sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData keys: {list(quote_data_obj.keys()) if isinstance(quote_data_obj, dict) else 'NOT DICT'}\n")
            if isinstance(quote_data_obj, dict):
                sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData lastPrice: {quote_data_obj.get('lastPrice', 'MISSING')}\n")
                sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData symbol: {quote_data_obj.get('symbol', 'MISSING')}\n")
                sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData change: {quote_data_obj.get('change', 'MISSING')}\n")
                # Show first 500 chars of full quote data
                quote_json = json.dumps(quote_data_obj, default=str)[:500]
                sys.stderr.write(f"WEBULL_QUOTE_DEBUG: QuoteData (first 500 chars): {quote_json}\n")
        sys.stderr.flush()
        return jsonify({"success": True, "quote": quote_data}), 200
    sys.stderr.write(f"WEBULL_QUOTE_DEBUG: Failed to get quote for {symbol}: {result.get('error', 'Unknown error')}\n")
    sys.stderr.flush()
    return jsonify({"success": False, "error": result.get("error", "Failed to get quote")}), 400


@app.route('/api/webull/options/chain', methods=['GET'])
def webull_get_option_chain():
    symbol = request.args.get('symbol')
    expiry_date = request.args.get('expiryDate') or request.args.get('expiry_date')
    strike_price_near = request.args.get('strikePriceNear') or request.args.get('strike_price_near')
    count = request.args.get('count', 10, type=int)

    if not symbol:
        return jsonify({"success": False, "error": "symbol is required"}), 400

    try:
        strike_price_near_val = float(strike_price_near) if strike_price_near else None
    except ValueError:
        return jsonify({"success": False, "error": "Invalid strike_price_near value"}), 400

    result = webull_api.get_option_chain(
        symbol,
        expiry_date=expiry_date,
        strike_price_near=strike_price_near_val,
        count=count,
    )
    if result.get("success"):
        return jsonify({"success": True, "chain": result.get("chain", {})}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to get option chain")}), 400


@app.route('/api/smart-executor/enabled', methods=['POST'])
def smart_executor_set_enabled():
    """Set Smart Executor enabled state."""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        enabled = data.get("enabled", True)
        db.save_setting("smart_executor_enabled", "true" if enabled else "false")
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/executor/execute', methods=['POST'])
def executor_execute_trade():
    """Execute a smart trade with validation and incremental filling"""
    data = request.get_json() or {}
    
    platform = data.get("platform", "etrade")
    signal_data = data.get("signal_data", {})
    
    if not signal_data:
        return jsonify({"success": False, "error": "signal_data is required"}), 400
    
    # Execute trade
    result = trade_executor.execute_trade(signal_data, platform)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/executor/history', methods=['GET'])
def executor_get_history():
    """Get execution history"""
    limit = request.args.get('limit', 50, type=int)
    executions = db.get_execution_attempts(limit=limit)
    return jsonify({"success": True, "executions": executions}), 200


@app.route('/api/executor/history/<int:execution_id>', methods=['DELETE'])
def executor_delete_execution(execution_id):
    """Delete a specific execution attempt."""
    try:
        success = db.delete_execution_attempt(execution_id)
        if success:
            return jsonify({"success": True, "message": "Execution deleted successfully"}), 200
        else:
            return jsonify({"success": False, "error": "Execution not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/executor/history/clear', methods=['DELETE'])
def executor_clear_history():
    """Clear all execution history."""
    try:
        print(f"[DEBUG] executor_clear_history called")
        success = db.clear_execution_attempts()
        print(f"[DEBUG] clear_execution_attempts returned: {success}")
        if success:
            return jsonify({"success": True, "message": "All execution history cleared successfully"}), 200
        else:
            return jsonify({"success": False, "error": "Failed to clear execution history"}), 500
    except Exception as e:
        print(f"[ERROR] Exception in executor_clear_history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Budget Filters API Endpoints ====================

@app.route('/api/executor/budget-filters', methods=['GET'])
def executor_get_budget_filters():
    """Get budget filter configurations."""
    try:
        filters_json = db.get_setting("executor_budget_filters", "[]")
        import json
        filters = json.loads(filters_json)
        return jsonify({"success": True, "filters": filters}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/executor/budget-filters', methods=['POST'])
def executor_save_budget_filters():
    """Save budget filter configurations."""
    try:
        data = request.get_json() or {}
        filters = data.get('filters', [])
        import json
        db.save_setting("executor_budget_filters", json.dumps(filters))
        return jsonify({"success": True, "message": "Budget filters saved"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Selling Strategy Filters API Endpoints ====================

@app.route('/api/executor/selling-filters', methods=['GET'])
def executor_get_selling_filters():
    """Get selling strategy filter configurations."""
    try:
        filters_json = db.get_setting("executor_selling_filters", "[]")
        import json
        filters = json.loads(filters_json)
        return jsonify({"success": True, "filters": filters}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/executor/selling-filters', methods=['POST'])
def executor_save_selling_filters():
    """Save selling strategy filter configurations."""
    try:
        data = request.get_json() or {}
        filters = data.get('filters', [])
        import json
        db.save_setting("executor_selling_filters", json.dumps(filters))
        return jsonify({"success": True, "message": "Selling filters saved"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== TradingView Executor API Endpoints ====================

@app.route('/api/tradingview-executor/config', methods=['GET'])
def tradingview_executor_get_config():
    """Get TradingView executor configuration."""
    try:
        config = tradingview_executor.get_config()
        return jsonify({"success": True, "config": config}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/config', methods=['POST'])
def tradingview_executor_save_config():
    """Save TradingView executor configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        config = {
            "platform": data.get("platform", "snaptrade"),
            "position_size": float(data.get("position_size", 1.0)),
            "bid_delta": float(data.get("bid_delta", 0.01)),
            "ask_delta": float(data.get("ask_delta", 0.01)),
            "increments": float(data.get("increments", 0.01)),
        }
        
        success = tradingview_executor.save_config(config)
        if success:
            return jsonify({"success": True, "config": config}), 200
        else:
            return jsonify({"success": False, "error": "Failed to save configuration"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/execute', methods=['POST'])
def tradingview_executor_execute():
    """Manually execute a TradingView signal."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        signal_data = {
            "symbol": data.get("symbol", "").upper(),
            "action": data.get("action", "").upper(),
            "price": float(data.get("price", 0)),
        }
        
        account_id = data.get("account_id")
        result = tradingview_executor.execute_signal(signal_data, account_id)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/history', methods=['GET'])
def tradingview_executor_get_history():
    """Get TradingView executor execution history."""
    try:
        limit = int(request.args.get('limit', 20))
        history = tradingview_executor.get_execution_history(limit)
        return jsonify({"success": True, "history": history}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/history/clear', methods=['DELETE'])
def tradingview_executor_clear_history():
    """Clear TradingView executor execution history."""
    try:
        success = tradingview_executor.clear_execution_history()
        if success:
            return jsonify({"success": True, "message": "History cleared"}), 200
        else:
            return jsonify({"success": False, "error": "Failed to clear history"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/enabled', methods=['GET'])
def tradingview_executor_get_enabled():
    """Get TradingView executor enabled state."""
    try:
        enabled = db.get_setting("tradingview_executor_enabled", "true").lower() == "true"
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tradingview-executor/enabled', methods=['POST'])
def tradingview_executor_set_enabled():
    """Set TradingView executor enabled state."""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        enabled = data.get("enabled", True)
        db.save_setting("tradingview_executor_enabled", "true" if enabled else "false")
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Discord API Endpoints ====================

@app.route('/api/discord/config', methods=['GET'])
def discord_get_config():
    """Get Discord configuration."""
    try:
        config = discord_api.get_config()
        return jsonify({"success": True, "config": config}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discord/config', methods=['POST'])
def discord_save_config():
    """Save Discord configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        bot_token = data.get("bot_token", "").strip()
        channel_id = data.get("channel_id", "").strip()
        channel_management_channel_id = data.get("channel_management_channel_id", "").strip() or None
        commentary_channel_id = data.get("commentary_channel_id", "").strip() or None
        
        if not bot_token or not channel_id:
            return jsonify({"success": False, "error": "Bot token and channel ID are required"}), 400
        
        success = discord_api.save_config(bot_token, channel_id, channel_management_channel_id, commentary_channel_id)
        if success:
            config_response = {"bot_token": "***", "channel_id": channel_id}
            if channel_management_channel_id:
                config_response["channel_management_channel_id"] = channel_management_channel_id
            if commentary_channel_id:
                config_response["commentary_channel_id"] = commentary_channel_id
            return jsonify({"success": True, "config": config_response}), 200
        else:
            return jsonify({"success": False, "error": "Failed to save configuration"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discord/test', methods=['POST'])
def discord_send_test_message():
    """Send a test message to Discord channel."""
    try:
        if not discord_api.is_enabled():
            return jsonify({"success": False, "error": "Discord module is disabled"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        message = data.get("message", "🧪 Test message from TradeIQ!").strip()
        channel_id = data.get("channel_id", "").strip() or None
        
        if not message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400
        
        # If channel_id is provided, use it; otherwise use default channel
        result = discord_api.send_message(message, channel_id=channel_id)
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discord/enabled', methods=['GET'])
def discord_get_enabled():
    """Get Discord enabled state."""
    try:
        enabled = db.get_setting("discord_enabled", "true").lower() == "true"
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discord/enabled', methods=['POST'])
def discord_set_enabled():
    """Set Discord enabled state."""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        enabled = data.get("enabled", True)
        db.save_setting("discord_enabled", "true" if enabled else "false")
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x-bot-keywords', methods=['GET'])
def get_x_bot_keywords():
    """Get X bot filter keywords configuration."""
    try:
        keywords = db.get_setting("x_bot_keywords", '"flow-bot" OR "uwhale-news-bot" OR "x-news-bot"')
        return jsonify({"success": True, "keywords": keywords}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x-bot-keywords', methods=['POST'])
def save_x_bot_keywords():
    """Save X bot filter keywords configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        keywords = data.get("keywords", "").strip()
        if not keywords:
            return jsonify({"success": False, "error": "Keywords cannot be empty"}), 400
        
        db.save_setting("x_bot_keywords", keywords)
        return jsonify({"success": True, "keywords": keywords}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== X (Twitter) API Endpoints ====================

@app.route('/api/x/config', methods=['GET'])
def x_get_config():
    """Get X (Twitter) configuration."""
    try:
        config = x_api.get_config()
        # Mask sensitive values for display
        masked_config = {
            "api_key": "***" if config.get("api_key") else "",
            "api_secret": "***" if config.get("api_secret") else "",
            "access_token": "***" if config.get("access_token") else "",
            "access_token_secret": "***" if config.get("access_token_secret") else "",
            "bearer_token": "***" if config.get("bearer_token") else "",
        }
        return jsonify({"success": True, "config": config}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/config', methods=['POST'])
def x_save_config():
    """Save X (Twitter) configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Safely extract and strip values, handling None
        api_key = (data.get("api_key") or "").strip() if data.get("api_key") else ""
        api_secret = (data.get("api_secret") or "").strip() if data.get("api_secret") else ""
        access_token = (data.get("access_token") or "").strip() if data.get("access_token") else ""
        access_token_secret = (data.get("access_token_secret") or "").strip() if data.get("access_token_secret") else ""
        bearer_token_value = data.get("bearer_token")
        bearer_token = bearer_token_value.strip() if bearer_token_value else None
        
        if not api_key or not api_secret or not access_token or not access_token_secret:
            return jsonify({"success": False, "error": "API Key, API Secret, Access Token, and Access Token Secret are required"}), 400
        
        success = x_api.save_config(api_key, api_secret, access_token, access_token_secret, bearer_token)
        if success:
            # Try to verify credentials after saving
            try:
                if x_api.api:
                    x_api.api.verify_credentials()
                    return jsonify({
                        "success": True, 
                        "config": {"api_key": "***", "api_secret": "***", "access_token": "***", "access_token_secret": "***"},
                        "message": "Configuration saved and credentials verified successfully"
                    }), 200
                else:
                    return jsonify({
                        "success": True, 
                        "config": {"api_key": "***", "api_secret": "***", "access_token": "***", "access_token_secret": "***"},
                        "message": "Configuration saved. Note: API not initialized - credentials will be verified on first use."
                    }), 200
            except Exception as e:
                # Save succeeded but verification failed
                return jsonify({
                    "success": True,
                    "config": {"api_key": "***", "api_secret": "***", "access_token": "***", "access_token_secret": "***"},
                    "warning": f"Configuration saved but credential verification failed: {str(e)}. Please check your credentials."
                }), 200
        else:
            return jsonify({"success": False, "error": "Failed to save configuration"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/test', methods=['POST'])
def x_send_test_tweet():
    """Post a test tweet to X (Twitter)."""
    try:
        if not x_api.is_enabled():
            return jsonify({"success": False, "error": "X module is disabled"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        text = data.get("text", "🧪 Test tweet from TradeIQ!").strip()
        if not text:
            return jsonify({"success": False, "error": "Tweet text cannot be empty"}), 400
        
        result = x_api.post_tweet(text)
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/enabled', methods=['GET'])
def x_get_enabled():
    """Get X enabled state."""
    try:
        enabled = db.get_setting("x_enabled", "true").lower() == "true"
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/enabled', methods=['POST'])
def x_set_enabled():
    """Set X enabled state."""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        enabled = data.get("enabled", True)
        db.save_setting("x_enabled", "true" if enabled else "false")
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== X Signal Processing Endpoints ====================

@app.route('/api/x/signals/analyze/<int:signal_id>', methods=['POST'])
def analyze_x_signal(signal_id):
    """Analyze an X channel signal and generate tweet variants"""
    try:
        # Get signal from database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, message, received_at 
            FROM trade_signals 
            WHERE id = ? AND channel_name = 'x'
        """, (signal_id,))
        
        signal = cursor.fetchone()
        conn.close()
        
        if not signal:
            return jsonify({"success": False, "error": "Signal not found"}), 404
        
        # Analyze signal
        analysis = x_signal_processor.analyze_signal(
            signal_id=signal[0],
            title=signal[1],
            message=signal[2],
            received_at=signal[3]
        )
        
        if 'error' in analysis:
            return jsonify({"success": False, "error": analysis['error']}), 500
        
        # Store analysis in database
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Insert analysis
            cursor.execute("""
                INSERT OR REPLACE INTO x_signal_analysis 
                (signal_id, signal_type, engagement_score, score_breakdown, 
                 recommendation, star_rating, entities, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                analysis['signal_type'],
                analysis['score'],
                json.dumps(analysis['score_breakdown']),
                analysis['recommendation'],
                analysis['star_rating'],
                json.dumps(analysis['entities']),
                datetime.now().isoformat()
            ))
            
            analysis_id = cursor.lastrowid
            
            # Insert variants
            for variant in analysis['variants']:
                cursor.execute("""
                    INSERT INTO x_tweet_variants 
                    (signal_id, analysis_id, variant_type, tweet_text, 
                     predicted_engagement, style_description, is_recommended, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    analysis_id,
                    variant['type'],
                    variant['text'],
                    variant['predicted_engagement'],
                    variant['style'],
                    variant['recommended'],
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            
        finally:
            conn.close()
        
        # Send push notification if engagement score >= 0.5 and tweet variant exists
        if analysis.get('score', 0) >= 0.5 and analysis.get('variants') and len(analysis['variants']) > 0:
            try:
                tweet_text = analysis['variants'][0].get('text', '')
                if tweet_text:
                    # Truncate tweet for notification body (max 100 chars)
                    notification_body = tweet_text[:100] + ('...' if len(tweet_text) > 100 else '')
                    
                    push_manager.send_notification_to_all(
                        title="News",
                        body=notification_body,
                        data={
                            "url": "/",
                            "signal_id": signal_id,
                            "action": "view_signal",
                            "tab": "x"
                        },
                        tag=f"signal-{signal_id}",  # Tag to replace previous notifications for same signal
                        requireInteraction=False
                    )
                    logger.info(f"Push notification sent for signal {signal_id} (score: {analysis['score']})")
            except Exception as e:
                logger.error(f"Error sending push notification for signal {signal_id}: {e}")
                # Don't fail the analysis if notification fails
        
        return jsonify({"success": True, "analysis": analysis}), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/signals/<int:signal_id>/analysis', methods=['GET'])
def get_signal_analysis(signal_id):
    """Get analysis data for a signal"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get analysis
        cursor.execute("""
            SELECT id, signal_type, engagement_score, score_breakdown,
                   recommendation, star_rating, entities, analyzed_at
            FROM x_signal_analysis
            WHERE signal_id = ?
        """, (signal_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Analysis not found"}), 404
        
        analysis_id = row[0]
        
        # Get variants
        cursor.execute("""
            SELECT id, variant_type, tweet_text, predicted_engagement,
                   style_description, is_recommended, is_selected
            FROM x_tweet_variants
            WHERE analysis_id = ?
            ORDER BY is_recommended DESC, predicted_engagement DESC
        """, (analysis_id,))
        
        variants = []
        for v in cursor.fetchall():
            variants.append({
                'id': v[0],
                'type': v[1],
                'text': v[2],
                'predicted_engagement': v[3],
                'style': v[4],
                'recommended': bool(v[5]),
                'selected': bool(v[6])
            })
        
        conn.close()
        
        analysis = {
            'signal_id': signal_id,
            'signal_type': row[1],
            'score': row[2],
            'score_breakdown': json.loads(row[3]) if row[3] else {},
            'recommendation': row[4],
            'star_rating': row[5],
            'entities': json.loads(row[6]) if row[6] else {},
            'analyzed_at': row[7],
            'variants': variants
        }
        
        return jsonify({"success": True, "analysis": analysis}), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/analytics', methods=['GET'])
def get_x_analytics():
    """Get analytics data for X module"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get today's date range
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        # Count today's signals in "x" channel
        cursor.execute("""
            SELECT COUNT(*) 
            FROM trade_signals 
            WHERE channel_name = 'x' 
            AND datetime(received_at) >= datetime(?)
        """, (today_start,))
        today_signals = cursor.fetchone()[0] or 0
        
        # Count analyzed signals today
        cursor.execute("""
            SELECT COUNT(DISTINCT s.id)
            FROM trade_signals s
            INNER JOIN x_signal_analysis a ON s.id = a.signal_id
            WHERE s.channel_name = 'x'
            AND datetime(s.received_at) >= datetime(?)
        """, (today_start,))
        analyzed_signals = cursor.fetchone()[0] or 0
        
        # Count posted tweets today
        cursor.execute("""
            SELECT COUNT(*) 
            FROM x_posted_tweets 
            WHERE datetime(posted_at) >= datetime(?)
        """, (today_start,))
        posted_tweets = cursor.fetchone()[0] or 0
        
        # Calculate average engagement from posted tweets today
        cursor.execute("""
            SELECT AVG(actual_likes + actual_retweets + actual_replies) as avg_engagement
            FROM x_posted_tweets 
            WHERE datetime(posted_at) >= datetime(?)
            AND (actual_likes IS NOT NULL OR actual_retweets IS NOT NULL OR actual_replies IS NOT NULL)
        """, (today_start,))
        avg_result = cursor.fetchone()
        avg_engagement = int(avg_result[0]) if avg_result and avg_result[0] is not None else 0
        
        # Calculate prediction accuracy (predicted vs actual engagement)
        cursor.execute("""
            SELECT 
                AVG(ABS(predicted_engagement - (COALESCE(actual_likes, 0) + COALESCE(actual_retweets, 0) + COALESCE(actual_replies, 0)))) as avg_diff,
                AVG(predicted_engagement) as avg_predicted
            FROM x_posted_tweets 
            WHERE datetime(posted_at) >= datetime(?)
            AND predicted_engagement IS NOT NULL
            AND (actual_likes IS NOT NULL OR actual_retweets IS NOT NULL OR actual_replies IS NOT NULL)
        """, (today_start,))
        accuracy_result = cursor.fetchone()
        
        avg_diff = 0
        prediction_accuracy = 0
        if accuracy_result and accuracy_result[0] is not None and accuracy_result[1] is not None:
            avg_diff = int(accuracy_result[0])
            avg_predicted = accuracy_result[1]
            if avg_predicted > 0:
                # Accuracy = 100% - (error percentage)
                error_pct = (avg_diff / avg_predicted) * 100
                prediction_accuracy = max(0, 100 - error_pct)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "today_signals": today_signals,
            "analyzed_signals": analyzed_signals,
            "posted_tweets": posted_tweets,
            "avg_engagement": avg_engagement,
            "prediction_accuracy": prediction_accuracy,
            "avg_engagement_diff": avg_diff
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/signals/<int:signal_id>/modify', methods=['POST'])
def modify_signal_tweet(signal_id):
    """Modify a tweet based on user instructions"""
    try:
        data = request.get_json()
        modifications = data.get('modifications', '').strip()
        
        if not modifications:
            return jsonify({"success": False, "error": "No modification instructions provided"}), 400
        
        # Get signal and current analysis
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, message, received_at 
            FROM trade_signals 
            WHERE id = ? AND channel_name = 'x'
        """, (signal_id,))
        
        signal = cursor.fetchone()
        
        if not signal:
            conn.close()
            return jsonify({"success": False, "error": "Signal not found"}), 404
        
        # Get current tweet variant
        cursor.execute("""
            SELECT tv.id, tv.tweet_text
            FROM x_tweet_variants tv
            INNER JOIN x_signal_analysis sa ON tv.analysis_id = sa.id
            WHERE sa.signal_id = ?
            ORDER BY tv.is_recommended DESC, tv.predicted_engagement DESC
            LIMIT 1
        """, (signal_id,))
        
        variant_row = cursor.fetchone()
        conn.close()
        
        if not variant_row:
            return jsonify({"success": False, "error": "No tweet variant found. Please analyze the signal first."}), 404
        
        variant_id = variant_row[0]
        current_tweet = variant_row[1]
        
        # Use Grok API to modify the tweet
        if not grok_api.is_enabled():
            return jsonify({"success": False, "error": "Grok API is not enabled. Please configure it in Settings."}), 400
        
        # Get entities for context
        entities = x_signal_processor.extract_entities(signal[2])
        
        # Build modification prompt
        tickers_str = ", ".join(entities.get('tickers', [])[:5]) or "None"
        
        # Get stock prices if available
        stock_prices_info = ""
        if alphavantage_api and alphavantage_api.is_enabled() and entities.get('tickers'):
            price_data_list = []
            for ticker in entities.get('tickers', [])[:3]:
                price_data = alphavantage_api.get_stock_price(ticker)
                if price_data.get("success"):
                    price_info = alphavantage_api.format_price_data_for_prompt(price_data)
                    price_data_list.append(price_info)
                import time
                time.sleep(0.2)
            
            if price_data_list:
                stock_prices_info = "\n\nCURRENT STOCK PRICES (from Alpha Vantage API):\n" + "\n".join(price_data_list)
        
        modify_prompt = f"""You are an expert at modifying X (Twitter) posts to improve engagement and clarity.

ORIGINAL TWEET:
{current_tweet}

USER'S MODIFICATION REQUEST:
{modifications}

CONTEXT:
- Tickers: {tickers_str}{stock_prices_info}

TASK:
Modify the original tweet according to the user's request. Keep the core message and facts, but apply the requested changes.

REQUIREMENTS:
- Apply the modifications requested by the user
- Keep the tweet under 280 characters
- Maintain the personal opinion/analysis tone
- Use exact stock prices if provided
- Keep 1-2 relevant emojis
- Ensure the modified tweet is ready to post

Format response as JSON:
{{
    "modified_tweet": "<the modified tweet text>",
    "changes_made": "<brief description of what was changed>"
}}"""
        
        # Call Grok API
        response = grok_api._make_request(
            "chat/completions",
            {
                "model": grok_api.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at modifying tweets based on user feedback. You apply modifications while maintaining the core message and engagement potential. Stock prices are provided from Alpha Vantage API - use those exact prices."
                    },
                    {
                        "role": "user",
                        "content": modify_prompt
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
        )
        
        if not response or "choices" not in response:
            return jsonify({"success": False, "error": "Failed to get response from Grok API"}), 500
        
        content = response["choices"][0]["message"]["content"]
        
        # Parse JSON response
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content
            
            result = json.loads(json_str)
            modified_tweet = result.get("modified_tweet", "").strip()
            
            if not modified_tweet:
                return jsonify({"success": False, "error": "Grok did not generate a modified tweet"}), 500
            
            # Update the variant in database
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE x_tweet_variants
                SET tweet_text = ?, created_at = ?
                WHERE id = ?
            """, (modified_tweet, datetime.now().isoformat(), variant_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "success": True,
                "modified_tweet": modified_tweet,
                "changes_made": result.get("changes_made", "Tweet modified as requested")
            }), 200
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Grok response: {e}")
            # Try to extract tweet from plain text
            import re
            tweet_match = re.search(r'"modified_tweet":\s*"([^"]+)"', content)
            if tweet_match:
                modified_tweet = tweet_match.group(1)
                
                # Update the variant
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE x_tweet_variants
                    SET tweet_text = ?, created_at = ?
                    WHERE id = ?
                """, (modified_tweet, datetime.now().isoformat(), variant_id))
                
                conn.commit()
                conn.close()
                
                return jsonify({
                    "success": True,
                    "modified_tweet": modified_tweet,
                    "changes_made": "Tweet modified as requested"
                }), 200
            
            return jsonify({"success": False, "error": "Failed to parse modification response"}), 500
        
    except Exception as e:
        import traceback
        logger.error(f"Error modifying tweet: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/x/signals/<int:signal_id>/post', methods=['POST'])
def post_signal_tweet(signal_id):
    """Post a tweet from a signal variant"""
    try:
        data = request.get_json()
        variant_id = data.get('variant_id')
        custom_text = data.get('custom_text')
        
        # Get variant text or use custom
        if custom_text:
            tweet_text = custom_text
        elif variant_id:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT tweet_text, predicted_engagement FROM x_tweet_variants WHERE id = ?", (variant_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return jsonify({"success": False, "error": "Variant not found"}), 404
            
            tweet_text = row[0]
            predicted_engagement = row[1]
        else:
            return jsonify({"success": False, "error": "No tweet text provided"}), 400
        
        # Post tweet
        result = x_api.post_tweet(tweet_text)
        
        if result.get("success"):
            # Store in posted tweets table
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO x_posted_tweets 
                (signal_id, variant_id, tweet_id, tweet_text, predicted_engagement, posted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                variant_id if variant_id else None,
                result.get('tweet_id'),
                tweet_text,
                predicted_engagement if variant_id else 0,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({"success": True, "result": result}), 200
        else:
            return jsonify({"success": False, "error": result.get('error')}), 400
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Grok API Endpoints ====================

@app.route('/api/grok/config', methods=['GET'])
def grok_get_config():
    """Get Grok API configuration"""
    try:
        config = grok_api.get_config()
        return jsonify({"success": True, "config": config}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/config', methods=['POST'])
def grok_save_config():
    """Save Grok API configuration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        api_key = data.get("api_key", "").strip()
        model = data.get("model", "grok-2-1212").strip()
        
        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400
        
        success = grok_api.save_config(api_key, model)
        
        if success:
            # Reload config to ensure instance is fully updated
            grok_api._load_config()
            
            return jsonify({
                "success": True,
                "config": {"api_key": "***", "model": model},
                "message": f"Grok API configuration saved successfully (model: {model})"
            }), 200
        else:
            return jsonify({"success": False, "error": "Failed to save configuration"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/test', methods=['POST'])
def grok_test_connection():
    """Test Grok API connection"""
    try:
        result = grok_api.test_connection()
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/enabled', methods=['GET'])
def grok_get_enabled():
    """Get Grok enabled state"""
    try:
        enabled = db.get_setting("grok_enabled", "true").lower() == "true"
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/enabled', methods=['POST'])
def grok_set_enabled():
    """Set Grok enabled state"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        enabled = data.get("enabled", True)
        db.save_setting("grok_enabled", "true" if enabled else "false")
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/predict/<int:signal_id>', methods=['POST'])
def grok_predict_engagement(signal_id):
    """Use Grok to predict engagement for a signal variant"""
    try:
        data = request.get_json()
        variant_id = data.get('variant_id')
        
        if not variant_id:
            return jsonify({"success": False, "error": "variant_id required"}), 400
        
        # Get variant and signal data
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.tweet_text, a.entities, a.engagement_score
            FROM x_tweet_variants v
            JOIN x_signal_analysis a ON v.analysis_id = a.id
            WHERE v.id = ?
        """, (variant_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"success": False, "error": "Variant not found"}), 404
        
        tweet_text = row[0]
        entities = json.loads(row[1]) if row[1] else {}
        base_score = row[2]
        
        # Get Grok prediction
        result = grok_api.predict_engagement(tweet_text, entities, base_score)
        
        # Store prediction
        if result.get("success"):
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO x_grok_analyses 
                (signal_id, analysis_type, response, predicted_engagement, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                'engagement_prediction',
                json.dumps(result),
                result.get('predicted_engagement', 0),
                result.get('confidence', 0),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
        
        return jsonify(result), 200 if result.get("success") else 400
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/grok/trends', methods=['POST'])
def grok_analyze_trends():
    """Use Grok to analyze current trends"""
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        keywords = data.get('keywords', [])
        
        result = grok_api.analyze_trends(tickers, keywords)
        return jsonify(result), 200 if result.get("success") else 400
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Push Notification Routes ====================

@app.route('/sw.js')
def service_worker():
    """Serve service worker file"""
    return app.send_static_file('sw.js'), 200, {'Content-Type': 'application/javascript'}

@app.route('/api/push/vapid-public-key', methods=['GET'])
def get_vapid_public_key():
    """Get VAPID public key for subscription"""
    try:
        public_key = push_manager.get_vapid_public_key()
        if public_key:
            return jsonify({"success": True, "public_key": public_key}), 200
        else:
            return jsonify({"success": False, "error": "VAPID keys not configured"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/push/subscribe', methods=['POST'])
def subscribe_push():
    """Save push subscription"""
    try:
        data = request.get_json()
        subscription = data.get('subscription')
        
        if not subscription:
            return jsonify({"success": False, "error": "Subscription data required"}), 400
        
        if push_manager.save_subscription(subscription):
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "error": "Failed to save subscription"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/push/unsubscribe', methods=['POST'])
def unsubscribe_push():
    """Remove push subscription"""
    try:
        data = request.get_json() or {}
        endpoint = data.get('endpoint')
        
        if endpoint:
            push_manager.remove_subscription(endpoint)
        
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/push/vapid-keys/generate', methods=['POST'])
def generate_vapid_keys_endpoint():
    """Generate new VAPID keys"""
    try:
        from generate_vapid_keys import generate_vapid_keys
        import sys
        from io import StringIO
        
        # Capture stdout to prevent print statements from interfering
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            # Generate keys without verbose output
            keys = generate_vapid_keys(verbose=False)
        finally:
            # Restore stdout
            sys.stdout = old_stdout
        
        return jsonify({
            "success": True,
            "private_key": keys['private_key'],
            "public_key_pem": keys['public_key_pem'],
            "public_key_base64": keys['public_key_base64']
        }), 200
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({"success": False, "error": error_msg}), 500

@app.route('/api/push/vapid-keys', methods=['GET'])
def get_vapid_keys():
    """Get current VAPID keys configuration"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        private_key = None
        public_key = None
        email = None
        
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'vapid_private_key'")
        row = cursor.fetchone()
        if row:
            private_key = row[0]
        
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'vapid_public_key'")
        row = cursor.fetchone()
        if row:
            public_key = row[0]
        
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'vapid_email'")
        row = cursor.fetchone()
        if row:
            email = row[0]
        
        conn.close()
        
        return jsonify({
            "success": True,
            "configured": private_key is not None and public_key is not None,
            "private_key": private_key,
            "public_key": public_key,
            "email": email
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/push/vapid-keys/test', methods=['POST'])
def test_vapid_keys_endpoint():
    """Test VAPID keys validity"""
    if not CRYPTOGRAPHY_AVAILABLE:
        return jsonify({
            "success": False,
            "message": "Cryptography library not available - VAPID key validation disabled",
            "details": ["⚠ Cryptography not installed - key validation skipped"]
        }), 503

    try:
        data = request.get_json()
        private_key_pem = data.get('private_key', '').strip()
        public_key_pem = data.get('public_key', '').strip()
        email = data.get('email', 'mailto:tradeiq@example.com').strip()
        
        results = {
            "success": True,
            "message": "All VAPID key tests passed!",
            "details": [],
            "private_key_format_valid": False,
            "public_key_format_valid": False,
            "keys_match": False,
            "public_key_base64": None,
            "email_valid": False
        }
        
        # 1. Validate Private Key Format
        if private_key_pem.startswith('-----BEGIN PRIVATE KEY-----') and private_key_pem.endswith('-----END PRIVATE KEY-----'):
            results["private_key_format_valid"] = True
            results["details"].append("✓ Private key format: Valid")
        else:
            results["success"] = False
            results["details"].append("✗ Private key format: Invalid (must be PEM format)")
        
        # 2. Validate Public Key Format
        if public_key_pem.startswith('-----BEGIN PUBLIC KEY-----') and public_key_pem.endswith('-----END PUBLIC KEY-----'):
            results["public_key_format_valid"] = True
            results["details"].append("✓ Public key format: Valid")
        else:
            results["success"] = False
            results["details"].append("✗ Public key format: Invalid (must be PEM format)")
        
        # 3. Validate Key Pair Match and Base64 Conversion
        if results["private_key_format_valid"] and results["public_key_format_valid"]:
            try:
                private_key = serialization.load_pem_private_key(
                    private_key_pem.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
                
                # Check if the public key derived from private key matches the provided public key
                derived_public_key = private_key.public_key()
                if derived_public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ) == public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ):
                    results["keys_match"] = True
                    results["details"].append("✓ Key pair match: Valid")
                    
                    # Convert public key to base64 URL-safe format
                    if isinstance(public_key, ec.EllipticCurvePublicKey):
                        public_numbers = public_key.public_numbers()
                        # P-256 requires exactly 32 bytes for X and Y coordinates
                        x_bytes = public_numbers.x.to_bytes(32, 'big')
                        y_bytes = public_numbers.y.to_bytes(32, 'big')
                        public_key_bytes = b'\x04' + x_bytes + y_bytes
                        # Keep the 0x04 prefix - browser expects full 65 bytes
                        results["public_key_base64"] = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
                        results["details"].append(f"✓ Public key base64: {results['public_key_base64'][:50]}...")
                else:
                    results["success"] = False
                    results["details"].append("✗ Key pair match: Invalid (private and public keys do not match)")
            except Exception as e:
                results["success"] = False
                results["details"].append(f"✗ Key pair validation error: {str(e)}")
        else:
            results["success"] = False
            results["details"].append("✗ Key pair match: Skipped due to invalid key formats")
        
        # 4. Validate Email Format
        if re.match(r"^mailto:[\w\.-]+@[\w\.-]+\.\w+$", email):
            results["email_valid"] = True
            results["details"].append("✓ Email format: Valid")
        else:
            results["success"] = False
            results["details"].append("✗ Email format: Invalid (must start with 'mailto:' and be a valid email)")
        
        if not results["success"]:
            results["message"] = "VAPID Keys Test Failed"
        
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/push/vapid-keys', methods=['POST'])
def save_vapid_keys_endpoint():
    """Save VAPID keys to database"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        private_key = data.get('private_key', '').strip()
        public_key = data.get('public_key', '').strip()
        public_key_base64 = data.get('public_key_base64', '').strip()  # Optional base64 format
        email = data.get('email', 'mailto:tradeiq@example.com').strip()
        
        if not private_key or not public_key:
            return jsonify({"success": False, "error": "Private key and public key are required"}), 400
        
        if not email.startswith('mailto:'):
            return jsonify({"success": False, "error": "Email must start with 'mailto:'"}), 400
        
        if push_manager.save_vapid_keys(private_key, public_key, email, public_key_base64 if public_key_base64 else None):
            return jsonify({"success": True, "message": "VAPID keys saved successfully"}), 200
        else:
            return jsonify({"success": False, "error": "Failed to save VAPID keys"}), 500
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({"success": False, "error": error_msg}), 500

@app.route('/api/push/send-test', methods=['POST'])
def send_test_notification():
    """Send test push notification to all subscribers"""
    try:
        data = request.get_json() or {}
        title = data.get('title', 'TradeIQ Test Notification')
        body = data.get('body', 'This is a test notification!')
        
        results = push_manager.send_notification_to_all(
            title=title,
            body=body,
            icon=data.get('icon'),
            badge=data.get('badge'),
            data=data.get('data', {})
        )
        
        return jsonify({
            "success": True,
            "sent": results["success"],
            "failed": results["failed"]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def init_db_if_needed():
    """Initialize database if not already done. Called from Android."""
    try:
        db.init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        raise

def run_flask_server(host='127.0.0.1', port=5000, debug=False):
    """
    Wrapper function to start Flask server.
    Can be called from Android/Chaquopy with explicit parameters.
    
    Args:
        host: Host to bind to (default: '127.0.0.1' for Android)
        port: Port to bind to (default: 5000)
        debug: Enable debug mode (default: False for Android)
    """
    import sys
    try:
        # Reduced logging - only show essential startup messages
        print(f"[FLASK] Starting server on {host}:{port}", file=sys.stderr, flush=True)
        
        # Initialize database if needed (this function handles checking if already initialized)
        try:
            init_db_if_needed()
        except Exception as db_error:
            print(f"[FLASK] Database warning: {db_error}", file=sys.stderr, flush=True)
            # Continue anyway - database might already be initialized
        
        print(f"[FLASK] Server ready at http://{host}:{port}", file=sys.stderr, flush=True)
        
        # Start Flask server
        # Note: app.run() is blocking, so this will run until server stops
        app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("[FLASK] Server stopped", file=sys.stderr, flush=True)
    except Exception as e:
        import traceback
        error_msg = f"[FLASK] ERROR: {str(e)}"
        print(error_msg, file=sys.stderr, flush=True)
        # Only print full traceback if it's a critical error
        traceback.print_exc(file=sys.stderr)
        # Re-raise to let Android service know there was an error
        raise


# ==================== Ngrok API Endpoints ====================

# Ngrok configuration file path (for communication between Flask and Android)
ngrok_config_file = os.path.join(app_files_dir if is_android else BASE_DIR, 'ngrok_config.json') if is_android else None
ngrok_command_file = os.path.join(app_files_dir if is_android else BASE_DIR, 'ngrok_command.json') if is_android else None

# Pre-configure ngrok auth token on Android
if is_android and ngrok_config_file:
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(ngrok_config_file), exist_ok=True)
        
        # Check if config file exists
        if not os.path.exists(ngrok_config_file):
            # Set default ngrok auth token
            default_config = {
                "auth_token": "371nJgStvsTc0kcWpnhQIDZUt81_6WZ3bfQVkbezeDAPsqrX5",
                "running": False,
                "url": None
            }
            with open(ngrok_config_file, 'w') as f:
                json.dump(default_config, f)
            print(f"DEBUG: Pre-configured ngrok auth token in {ngrok_config_file}")
    except Exception as e:
        print(f"DEBUG: Failed to pre-configure ngrok auth token: {e}")

@app.route('/api/ngrok/status', methods=['GET'])
def get_ngrok_status():
    """Get ngrok tunnel status and URL"""
    try:
        if not is_android or not ngrok_config_file:
            return jsonify({
                "running": False,
                "url": None,
                "message": "Ngrok is only available on Android"
            }), 200
        
        # Read ngrok status from config file
        if os.path.exists(ngrok_config_file):
            with open(ngrok_config_file, 'r') as f:
                config = json.load(f)
                return jsonify({
                    "running": config.get("running", False),
                    "url": config.get("url"),
                    "message": "Ngrok tunnel active" if config.get("running") else "Ngrok tunnel stopped"
                }), 200
        else:
            return jsonify({
                "running": False,
                "url": None,
                "message": "Ngrok not configured"
            }), 200
        
    except Exception as e:
        print(f"Error getting ngrok status: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "running": False,
            "url": None,
            "error": str(e)
        }), 500


@app.route('/api/ngrok/start', methods=['POST'])
def start_ngrok():
    """Start ngrok tunnel"""
    try:
        if not is_android or not ngrok_command_file:
            return jsonify({
                "success": False,
                "error": "Ngrok is only available on Android"
            }), 400
        
        # Write start command to file for Android to pick up
        command = {
            "action": "start",
            "timestamp": datetime.now().isoformat()
        }
        
        with open(ngrok_command_file, 'w') as f:
            json.dump(command, f)
        
        print(f"DEBUG: Ngrok start command written to {ngrok_command_file}")
        
        return jsonify({
            "success": True,
            "message": "Ngrok start command sent. Please wait a few seconds for the tunnel to establish."
        }), 200
            
    except Exception as e:
        print(f"Error starting ngrok: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/ngrok/stop', methods=['POST'])
def stop_ngrok():
    """Stop ngrok tunnel"""
    try:
        if not is_android or not ngrok_command_file:
            return jsonify({
                "success": False,
                "error": "Ngrok is only available on Android"
            }), 400
        
        # Write stop command to file for Android to pick up
        command = {
            "action": "stop",
            "timestamp": datetime.now().isoformat()
        }
        
        with open(ngrok_command_file, 'w') as f:
            json.dump(command, f)
        
        print(f"DEBUG: Ngrok stop command written to {ngrok_command_file}")
        
        return jsonify({
            "success": True,
            "message": "Ngrok stop command sent"
        }), 200
        
    except Exception as e:
        print(f"Error stopping ngrok: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/ngrok/config', methods=['GET'])
def get_ngrok_config():
    """Get ngrok configuration (auth token masked)"""
    try:
        if not is_android or not ngrok_config_file:
            return jsonify({
                "auth_token": None,
                "has_auth_token": False
            }), 200
        
        # Read ngrok config from file
        if os.path.exists(ngrok_config_file):
            with open(ngrok_config_file, 'r') as f:
                config = json.load(f)
                
            auth_token = config.get("auth_token")
            has_token = auth_token is not None and len(str(auth_token)) > 0
            
            # Mask the token for display (show first 8 and last 4 characters)
            masked_token = None
            if has_token:
                token_str = str(auth_token)
                if len(token_str) > 12:
                    masked_token = token_str[:8] + "..." + token_str[-4:]
                else:
                    masked_token = "***"
            
            return jsonify({
                "auth_token": masked_token,
                "has_auth_token": has_token
            }), 200
        else:
            return jsonify({
                "auth_token": None,
                "has_auth_token": False
            }), 200
        
    except Exception as e:
        print(f"Error getting ngrok config: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "auth_token": None,
            "has_auth_token": False,
            "error": str(e)
        }), 500


@app.route('/api/ngrok/config', methods=['POST'])
def update_ngrok_config():
    """Update ngrok configuration (save auth token)"""
    try:
        if not is_android or not ngrok_config_file:
            return jsonify({
                "success": False,
                "error": "Ngrok is only available on Android"
            }), 400
        
        data = request.get_json()
        if not data or 'auth_token' not in data:
            return jsonify({
                "success": False,
                "error": "Auth token is required"
            }), 400
        
        auth_token = data['auth_token'].strip()
        if not auth_token:
            return jsonify({
                "success": False,
                "error": "Auth token cannot be empty"
            }), 400
        
        # Read existing config or create new
        config = {}
        if os.path.exists(ngrok_config_file):
            with open(ngrok_config_file, 'r') as f:
                config = json.load(f)
        
        # Update auth token
        config["auth_token"] = auth_token
        
        # Write back to config file
        with open(ngrok_config_file, 'w') as f:
            json.dump(config, f)
        
        print(f"DEBUG: Ngrok auth token saved to {ngrok_config_file}")
        
        return jsonify({
            "success": True,
            "message": "Ngrok auth token saved successfully"
        }), 200
        
    except Exception as e:
        print(f"Error updating ngrok config: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== Webhook URL Configuration ====================

@app.route('/api/webhook/config', methods=['GET'])
def get_webhook_config():
    """Get webhook URL configuration"""
    try:
        webhook_url = os.getenv('WEBHOOK_BASE_URL', '')
        return jsonify({
            "webhook_url": webhook_url,
            "full_endpoint": f"{webhook_url.rstrip('/')}/api/signals/receive" if webhook_url else None
        }), 200
    except Exception as e:
        print(f"Error getting webhook config: {e}")
        return jsonify({
            "webhook_url": None,
            "error": str(e)
        }), 500


@app.route('/api/webhook/config', methods=['POST'])
def update_webhook_config():
    """Update webhook URL configuration"""
    try:
        data = request.get_json()
        if not data or 'webhook_url' not in data:
            return jsonify({
                "success": False,
                "error": "Webhook URL is required"
            }), 400
        
        webhook_url = data['webhook_url'].strip()
        
        # Update environment variable
        os.environ['WEBHOOK_BASE_URL'] = webhook_url
        
        # Save to .env file
        env_path = env_file_path
        env_dir = os.path.dirname(env_path)
        if env_dir:
            os.makedirs(env_dir, exist_ok=True)
        
        # Read existing .env file
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Update or add WEBHOOK_BASE_URL
        updated = False
        new_lines = []
        for line in env_lines:
            if line.strip().startswith('WEBHOOK_BASE_URL='):
                new_lines.append(f'WEBHOOK_BASE_URL={webhook_url}\n')
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            new_lines.append(f'WEBHOOK_BASE_URL={webhook_url}\n')
        
        # Write back to file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"DEBUG: Webhook URL saved: {webhook_url}")
        
        return jsonify({
            "success": True,
            "message": "Webhook URL saved successfully",
            "full_endpoint": f"{webhook_url.rstrip('/')}/api/signals/receive"
        }), 200
        
    except Exception as e:
        print(f"Error updating webhook config: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== API endpoints for read/unread tracking ====================
# These routes must be defined outside of if __name__ == '__main__' block
# so they're registered when Flask is started programmatically (e.g., on Android)

@app.route('/api/signals/<int:signal_id>/mark-dashboard-read', methods=['POST'])
def mark_dashboard_read(signal_id):
    """Mark a signal as read in Dashboard module"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trade_signals 
            SET dashboard_read = 1 
            WHERE id = ?
        """, (signal_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/api/signals/<int:signal_id>/mark-x-read', methods=['POST'])
def mark_x_read(signal_id):
    """Mark a signal as read in X module"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trade_signals 
            SET x_read = 1 
            WHERE id = ?
        """, (signal_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/api/dashboard/unread-count', methods=['GET'])
def get_dashboard_unread_count():
    """Get count of unread channel management signals (only signals less than 1 hour old)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Count unread signals from all channels except special channels (x, TradingView, UNMATCHED)
        # Only count signals received within the last 1 hour
        cursor.execute("""
            SELECT COUNT(*) 
            FROM trade_signals 
            WHERE channel_name IS NOT NULL 
            AND channel_name != ''
            AND channel_name NOT IN ('x', 'TradingView', 'UNMATCHED')
            AND (dashboard_read = 0 OR dashboard_read IS NULL)
            AND received_at > datetime('now', '-1 hour')
        """)
        
        count = cursor.fetchone()[0] or 0
        conn.close()
        return jsonify({"count": count}), 200
    except Exception as e:
        return jsonify({"count": 0, "error": str(e)}), 500
    
@app.route('/api/x/unread-count', methods=['GET'])
def get_x_unread_count():
    """Get count of unread high-engagement X signals (only signals less than 1 hour old)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT s.id)
            FROM trade_signals s
            INNER JOIN x_signal_analysis a ON s.id = a.signal_id
            WHERE s.channel_name = 'x' 
            AND (s.x_read = 0 OR s.x_read IS NULL)
            AND a.engagement_score >= 0.5
            AND s.received_at > datetime('now', '-1 hour')
        """)
        count = cursor.fetchone()[0] or 0
        conn.close()
        return jsonify({"count": count}), 200
    except Exception as e:
        return jsonify({"count": 0, "error": str(e)}), 500
    
@app.route('/api/dashboard/mark-all-read', methods=['POST'])
def mark_all_dashboard_read():
    """Mark all channel management signals as read"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Mark all signals from all channels except special channels (x, TradingView, UNMATCHED) as read
        cursor.execute("""
            UPDATE trade_signals 
            SET dashboard_read = 1 
            WHERE channel_name IS NOT NULL 
            AND channel_name != ''
            AND channel_name NOT IN ('x', 'TradingView', 'UNMATCHED')
        """)
        
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/api/x/mark-all-read', methods=['POST'])
def mark_all_x_read():
    """Mark all X signals with high engagement as read"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trade_signals 
            SET x_read = 1 
            WHERE channel_name = 'x'
            AND id IN (
                SELECT DISTINCT s.id
                FROM trade_signals s
                INNER JOIN x_signal_analysis a ON s.id = a.signal_id
                WHERE a.engagement_score >= 0.5
            )
        """)
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Android Native Notifications API ====================

# File to communicate Android notification requests
android_notification_file = os.path.join(app_files_dir if is_android else BASE_DIR, 'android_notification.json') if is_android else None

def send_android_notification(title: str, body: str):
    """
    Helper function to send Android native notification.
    Checks if Android notifications are enabled before sending.
    """
    if not is_android:
        return False
    
    try:
        # Check if Android notifications are enabled
        enabled = False
        if android_notification_file and os.path.exists(android_notification_file):
            try:
                with open(android_notification_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    enabled = config.get('enabled', False)
            except:
                enabled = False
        
        if not enabled:
            return False
        
        # Write notification request to file for Android service to pick up
        notification_request_file = os.path.join(app_files_dir, 'android_notification_request.json')
        os.makedirs(os.path.dirname(notification_request_file), exist_ok=True)
        
        request_data = {
            "action": "show_notification",
            "title": title,
            "body": body,
            "channel": "user_notifications_channel",  # Must match USER_NOTIFICATIONS_CHANNEL_ID in FlaskService.kt
            "timestamp": datetime.now().isoformat()
        }
        
        with open(notification_request_file, 'w', encoding='utf-8') as f:
            json.dump(request_data, f)
        
        print(f"✅ Android notification request sent: {title}")
        return True
    except Exception as e:
        print(f"⚠️ Error sending Android notification: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/api/android/notifications/status', methods=['GET'])
def get_android_notifications_status():
    """Get Android notifications enabled status"""
    try:
        if not is_android:
            return jsonify({
                "enabled": False,
                "error": "Android notifications are only available on Android devices"
            }), 200
        
        # Check if enabled flag exists in file
        enabled = False
        if android_notification_file and os.path.exists(android_notification_file):
            try:
                with open(android_notification_file, 'r') as f:
                    config = json.load(f)
                    enabled = config.get('enabled', False)
            except:
                enabled = False
        
        return jsonify({"enabled": enabled}), 200
    except Exception as e:
        return jsonify({"enabled": False, "error": str(e)}), 500

@app.route('/api/android/notifications/toggle', methods=['POST'])
def toggle_android_notifications():
    """Enable or disable Android notifications"""
    try:
        if not is_android:
            return jsonify({
                "success": False,
                "error": "Android notifications are only available on Android devices"
            }), 400
        
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # Save to file for Android service to read
        if android_notification_file:
            os.makedirs(os.path.dirname(android_notification_file), exist_ok=True)
            with open(android_notification_file, 'w') as f:
                json.dump({"enabled": enabled, "updated_at": datetime.now().isoformat()}, f)
        
        return jsonify({"success": True, "enabled": enabled}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/android/notifications/test', methods=['POST'])
def send_android_test_notification():
    """Send a test Android notification"""
    try:
        if not is_android:
            return jsonify({
                "success": False,
                "error": "Android notifications are only available on Android devices"
            }), 400
        
        data = request.get_json()
        title = data.get('title', 'TradeIQ Test Notification')
        body = data.get('body', 'This is a test notification from TradeIQ! 🎉')
        channel = data.get('channel', 'user_notifications')
        
        # Write notification request to file for Android service to pick up
        notification_request_file = os.path.join(app_files_dir, 'android_notification_request.json')
        os.makedirs(os.path.dirname(notification_request_file), exist_ok=True)
        
        request_data = {
            "action": "show_notification",
            "title": title,
            "body": body,
            "channel": "user_notifications_channel",  # Must match USER_NOTIFICATIONS_CHANNEL_ID in FlaskService.kt
            "timestamp": datetime.now().isoformat()
        }
        
        with open(notification_request_file, 'w') as f:
            json.dump(request_data, f)
        
        return jsonify({"success": True, "message": "Notification request sent"}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    db.init_db()
    print("✓ Database initialized")
    
    # Start the Flask app
    port = int(os.getenv('API_PORT', 5000))
    print(f"\n🚀 TradeIQ API starting on port {port}...")
    print(f"📊 UI available at http://localhost:{port}")
    print(f"🔧 Execution Model: {execution_model}")
    print(f"🏗️  Builder Model: {builder_model}")
    print(f"💰 Trading Mode (Webull removed)\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
