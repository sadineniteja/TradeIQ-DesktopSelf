# IPC Migration Complete ✅

## What Changed

The app has been converted from **HTTP-based (Flask on port 5000)** to **IPC-based (direct Electron ↔ Python communication)**.

### Key Benefits:
- ✅ **No HTTP port exposed** - Truly native desktop app feel
- ✅ **No browser access** - Can't access via `localhost:5000` anymore
- ✅ **Faster communication** - Direct process-to-process communication
- ✅ **More secure** - No network exposure

## Files Created/Modified

### New Files:
1. **`electron/ipc-bridge.js`** - Handles Electron ↔ Python IPC communication
2. **`app/python/app_ipc.py`** - Python IPC handler (replaces Flask HTTP server)
3. **`app/static/api-wrapper.js`** - JavaScript wrapper that replaces `fetch()` calls with IPC

### Modified Files:
1. **`electron/main.js`** - Now uses IPC bridge instead of Flask HTTP server
2. **`electron/preload/main-preload.js`** - Exposes IPC API to renderer
3. **`app/templates/index.html`** - Added api-wrapper.js script

## How It Works

```
┌─────────────────────────────────────────┐
│         Electron Renderer (UI)           │
│  ┌──────────────────────────────────┐  │
│  │  JavaScript (fetch('/api/...'))   │  │
│  └──────────────┬───────────────────┘  │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐  │
│  │  api-wrapper.js (intercepts)    │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼───────────────────────┘
                  │ IPC (ipcRenderer.invoke)
                  ▼
┌─────────────────────────────────────────┐
│      Electron Main Process               │
│  ┌──────────────────────────────────┐  │
│  │  ipc-bridge.js                   │  │
│  │  - Receives IPC from renderer    │  │
│  │  - Sends JSON to Python via stdin│  │
│  │  - Receives JSON from Python     │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼───────────────────────┘
                  │ stdin/stdout pipes
                  ▼
┌─────────────────────────────────────────┐
│      Python Process                      │
│  ┌──────────────────────────────────┐  │
│  │  app_ipc.py                      │  │
│  │  - Reads JSON from stdin         │  │
│  │  - Processes via Flask app       │  │
│  │  - Writes JSON to stdout         │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## API Calls

All `fetch('/api/...')` calls are automatically intercepted by `api-wrapper.js` and converted to IPC calls. **No changes needed to existing JavaScript code!**

## Testing

1. Start the app: `npm start`
2. Verify no port 5000: `lsof -i :5000` (should return nothing)
3. App should work exactly as before, but with native feel

## Rollback

If you need to go back to HTTP mode:
1. Use `./scripts/start_mac.sh` instead of `npm start`
2. This starts Flask on port 5000 as before

## Notes

- The IPC handler (`app_ipc.py`) uses the same Flask app instance, so all routes work the same
- Static files are served via custom `tradeiq://` protocol
- Discord browser integration still works via IPC

