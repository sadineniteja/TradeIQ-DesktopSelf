# TradeIQ Desktop

Desktop version of TradeIQ trading application for macOS and Windows with **integrated Discord browser**.

## Features

- **Integrated Discord Browser**: Built-in Discord with automatic notification capture - no Chrome extension needed!
- **Signal Processing**: Receive and process trade signals from Discord, X (Twitter), and other sources
- **AI Analysis**: Powered by OpenAI GPT models for intelligent trade analysis
- **Trading Execution**: Execute trades via E*TRADE and SnapTrade
- **Smart Executor**: Intelligent order execution with validation and incremental filling
- **Real-time Dashboard**: Monitor signals, positions, and execution history
- **Options Trading**: Full support for options chain and options trading

## Requirements

- **Python 3.8+** (Python 3.10+ recommended)
- **Node.js 18+** (for Electron desktop app with Discord browser)
- **macOS 10.15+** or **Windows 10+**
- **Internet connection** for API access

## Quick Start

### Option 1: Electron Desktop App (Recommended - includes Discord Browser)

1. Install Node.js if not already installed:
   - macOS: `brew install node`
   - Windows: Download from [nodejs.org](https://nodejs.org/)

2. Install dependencies:
   ```bash
   cd ~/Desktop/TradeIQ-Desktop
   npm install
   ```

3. Install Python dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Configure your API keys:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. Run the Electron app:
   ```bash
   npm start
   ```

The app will open with TradeIQ on the left. Click "Discord Browser" in the More menu to open Discord in a split view!

### Option 2: Browser-Based (No Discord Browser integration)

#### macOS

```bash
cd ~/Desktop/TradeIQ-Desktop
chmod +x scripts/start_mac.sh
./scripts/start_mac.sh
```

Then open: `http://127.0.0.1:5000`

#### Windows

```cmd
cd C:\Users\YourUsername\Desktop\TradeIQ-Desktop
scripts\start_windows.bat
```

Then open: `http://127.0.0.1:5000`

## Discord Browser Integration

The desktop app includes an **integrated Discord browser** that:

1. Opens Discord in a split view alongside TradeIQ
2. Automatically captures Discord notifications
3. Forwards signals directly to TradeIQ's Dashboard
4. No Chrome extension needed - everything is built-in!

### How to Use:

1. Launch the Electron app with `npm start`
2. Go to "More" → "Discord Browser"
3. Click "Open Discord"
4. Log in to Discord (one-time)
5. Navigate to your trading channels
6. Signals will automatically appear in your Dashboard!

## Configuration

Edit `.env` with your API keys:

```
# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key

# E*TRADE (optional)
ETRADE_CONSUMER_KEY=your_key
ETRADE_CONSUMER_SECRET=your_secret

# SnapTrade (optional)
SNAPTRADE_CLIENT_ID=your_client_id
SNAPTRADE_CONSUMER_KEY=your_consumer_key
```

## Project Structure

```
TradeIQ-Desktop/
├── app/
│   ├── python/              # 23 Python files (Flask backend)
│   │   ├── app.py           # Main Flask application
│   │   ├── trade_executor.py # Smart trade executor
│   │   └── ...
│   ├── static/              # Frontend assets
│   │   ├── discord-browser.js  # Discord browser integration
│   │   └── ...
│   └── templates/           # HTML templates
├── electron/                # Electron app
│   ├── main.js              # Main process (handles Discord browser)
│   └── preload/
│       ├── main-preload.js  # Main window preload
│       └── discord-preload.js # Discord notification interceptor
├── scripts/
│   ├── start_mac.sh         # macOS launcher (browser mode)
│   └── start_windows.bat    # Windows launcher (browser mode)
├── package.json             # Node.js/Electron config
├── requirements.txt         # Python dependencies
└── README.md
```

## Trading Platforms

- **E*TRADE**: Full integration for equity and options trading
- **SnapTrade**: Aggregator for multiple brokerages (via proxy)

## Signal Sources

- **Discord Browser** (Integrated): Built-in Discord with auto-capture
- **Discord Webhooks**: Webhook-based signal reception
- **X (Twitter)**: Real-time signal monitoring
- **Chrome Extension**: Manual browser extension (alternative)
- **Manual Entry**: Direct signal input via UI

## Troubleshooting

### Flask Server Won't Start
- Make sure Python 3.8+ is installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Check port 5000 isn't in use

### Discord Browser Not Working
- Make sure you're running the Electron app (`npm start`), not browser mode
- Check console for errors (View → Toggle Developer Tools)
- Try logging out and back into Discord

### Notifications Not Captured
- Make sure Discord has notification permission
- Check that you're subscribed to the channels you want signals from
- Verify signals appear in Dashboard after posting in Discord

## Building Distributable

### macOS DMG
```bash
npm run build:mac
```

### Windows Installer
```bash
npm run build:win
```

Built files will be in the `dist/` folder.

## Notes

- This desktop version does NOT include Webull API support (due to Android compatibility issues)
- All trading is done via E*TRADE or SnapTrade
- The app runs locally on your machine - no cloud deployment needed
- Database is stored locally in `tradeiq.db`
- Discord login is stored securely in Electron's session storage

## Support

For issues or questions, check the logs in the terminal where you started the app.
