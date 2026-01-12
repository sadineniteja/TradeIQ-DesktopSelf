const { app, BrowserWindow, BrowserView, ipcMain, session, protocol } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const IPCBridge = require('./ipc-bridge');

let mainWindow;
let discordView;
let ipcBridge;
let httpServer;
let httpPort;

function createWindow() {
  const isMac = process.platform === 'darwin';
  
  // Configure persistent session for Discord webview partition BEFORE creating window
  // This ensures cookies, localStorage, and IndexedDB persist across app restarts
  const discordSession = session.fromPartition('persist:discord');
  
  // CRITICAL: Remove any quota limits that might prevent storage
  discordSession.clearStorageData({ storages: [] }).catch(() => {}); // Clear only if needed
  
  // Set up session permissions - ALLOW EVERYTHING Discord needs
  discordSession.setPermissionRequestHandler((webContents, permission, callback) => {
    console.log('[Discord Session] Permission requested:', permission);
    callback(true); // Allow all permissions
  });
  
  // Log storage activity
  let cookieCount = 0;
  discordSession.cookies.on('changed', async (event, cookie, cause, removed) => {
    cookieCount++;
    if (cookieCount % 10 === 0) {
      console.log('[Discord Session] Cookies updated, count:', cookieCount);
    }
  });
  
  console.log('[Discord Session] ✅ Configured with FULL storage persistence');
  console.log('[Discord Session] Storage path:', app.getPath('userData'));
  
  // Auto-save Discord session every 1 hour
  setInterval(async () => {
    try {
      console.log('[Discord Session] ⏰ Auto-save triggered (1 hour interval)...');
      await discordSession.flushStorageData();
      const cookies = await discordSession.cookies.get({});
      console.log('[Discord Session] ✅ Auto-saved', cookies.length, 'cookies');
    } catch (err) {
      console.error('[Discord Session] ❌ Auto-save error:', err);
    }
  }, 60 * 60 * 1000); // 1 hour in milliseconds
  
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    frame: false,  // Frameless window for native feel
    titleBarStyle: isMac ? 'hiddenInset' : 'hidden',  // macOS: keep traffic lights
    trafficLightPosition: isMac ? { x: 15, y: 12 } : undefined,
    backgroundColor: '#0f172a',  // Match header color
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,  // Enable webview for Discord embedding
      preload: path.join(__dirname, 'preload', 'main-preload.js')
    },
    icon: path.join(__dirname, '../app/static/icons/icon-192x192.png'),
    title: 'TradeIQ Desktop'
  });
  
  // Set Content Security Policy to address security warning
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: http://127.0.0.1:* https://discord.com https://*.discord.com https://*.discordapp.com; " +
          "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://discord.com https://*.discord.com https://*.discordapp.com; " +
          "style-src 'self' 'unsafe-inline' https://discord.com https://*.discord.com; " +
          "img-src 'self' data: blob: https: http:; " +
          "connect-src 'self' http://127.0.0.1:* https://discord.com https://*.discord.com https://*.discordapp.com; " +
          "frame-src 'self' https://discord.com https://*.discord.com;"
        ]
      }
    });
  });

  // Start IPC bridge (replaces Flask HTTP server)
  ipcBridge = new IPCBridge();
  
  // Start local HTTP server for UI (random port, localhost only)
  startLocalServer();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  
  // Add electron-app class when DOM is ready
  mainWindow.webContents.on('dom-ready', () => {
    // Add electron-app class
    mainWindow.webContents.executeJavaScript(`
      console.log('[Electron] DOM ready, adding classes...');
      console.log('[Electron] electronAPI available:', !!window.electronAPI);
      console.log('[Electron] electronAPI.isElectron:', window.electronAPI ? window.electronAPI.isElectron : 'N/A');
      document.body.classList.add('electron-app');
      document.body.classList.add('platform-${process.platform}');
    `);
  });
  
  // Log page load events
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error('[Window] Failed to load:', errorCode, errorDescription, validatedURL);
  });
  
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('[Window] Page loaded successfully');
  });
  
  // Handle IPC from renderer for Discord browser and API calls
  setupIPC();
}

// Start local HTTP server for UI (localhost only, random port)
function startLocalServer() {
  const appDir = path.join(__dirname, '..');
  const templatesDir = path.join(appDir, 'app', 'templates');
  const staticDir = path.join(appDir, 'app', 'static');
  
  httpServer = http.createServer((req, res) => {
    let filePath;
    
    if (req.url === '/' || req.url === '/index.html') {
      // Serve processed HTML
      const htmlPath = path.join(templatesDir, 'index.html');
      fs.readFile(htmlPath, 'utf8', (err, html) => {
        if (err) {
          res.writeHead(500);
          res.end('Error loading template');
          return;
        }
        
        // Replace Flask url_for with local paths
        const processedHtml = html
          .replace(/\{\{\s*url_for\(['"]static['"],\s*filename=['"]([^'"]+)['"]\)\s*\}\}/g, '/static/$1')
          .replace(/\{\{\s*url_for\(['"]static['"],\s*filename=['"]([^'"]+)['"]\)\s*\?\s*v=\d+\.\d+\s*\}\}/g, '/static/$1');
        
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(processedHtml);
      });
    } else if (req.url === '/sw.js' || req.url.startsWith('/sw.js')) {
      // Serve service worker
      const swPath = path.join(staticDir, 'sw.js');
      fs.readFile(swPath, (err, data) => {
        if (err) {
          console.log(`[Server] Service worker not found: ${swPath}`);
          res.writeHead(404);
          res.end('Service worker not found');
          return;
        }
        res.writeHead(200, { 
          'Content-Type': 'application/javascript',
          'Service-Worker-Allowed': '/'
        });
        res.end(data);
      });
    } else if (req.url.startsWith('/static/')) {
      // Serve static files - strip query string first
      const urlWithoutQuery = req.url.split('?')[0];
      const relativePath = urlWithoutQuery.replace('/static/', '');
      filePath = path.join(staticDir, relativePath);
      
      // Security check
      const resolvedPath = path.resolve(filePath);
      const resolvedStaticDir = path.resolve(staticDir);
      
      if (!resolvedPath.startsWith(resolvedStaticDir)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }
      
      fs.readFile(filePath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('Not found');
          return;
        }
        
        // Determine content type
        const ext = path.extname(filePath);
        const contentTypes = {
          '.js': 'application/javascript',
          '.css': 'text/css',
          '.png': 'image/png',
          '.jpg': 'image/jpeg',
          '.jpeg': 'image/jpeg',
          '.svg': 'image/svg+xml',
          '.ico': 'image/x-icon',
          '.json': 'application/json'
        };
        
        res.writeHead(200, { 'Content-Type': contentTypes[ext] || 'text/plain' });
        res.end(data);
      });
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  });
  
  // Find random available port
  httpServer.listen(0, '127.0.0.1', () => {
    httpPort = httpServer.address().port;
    const url = `http://127.0.0.1:${httpPort}/`;
    console.log(`[Server] Local HTTP server started on port ${httpPort}`);
    console.log(`[Server] URL: ${url}`);
    
    // Wait a moment for server to be ready, then load
    setTimeout(() => {
      console.log(`[Window] Loading: ${url}`);
      mainWindow.loadURL(url).catch(err => {
        console.error('[Window] Load error:', err);
      });
    }, 200);
  });
  
  httpServer.on('error', (err) => {
    console.error('[Server] Error:', err);
  });
  
  httpServer.on('request', (req, res) => {
    console.log(`[Server] Request: ${req.method} ${req.url}`);
  });
}

function setupIPC() {
  // Handle API calls from renderer
  ipcMain.handle('api-request', async (event, method, path, body, headers) => {
    if (!ipcBridge) {
      throw new Error('IPC bridge not initialized');
    }
    return await ipcBridge.sendRequest(method, path, body, headers);
  });
  
  // Window control handlers
  ipcMain.on('window-minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });
  
  ipcMain.on('window-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });
  
  ipcMain.on('window-close', () => {
    if (mainWindow) mainWindow.close();
  });
  
  // Get platform info
  ipcMain.handle('get-platform', () => {
    return process.platform;
  });
  
  // Get preload script path for webviews
  ipcMain.handle('get-preload-path', (event, filename) => {
    return path.join(__dirname, 'preload', filename);
  });
  
  // Save Discord session manually
  ipcMain.handle('save-discord-session', async (event) => {
    try {
      const discordSession = session.fromPartition('persist:discord');
      console.log('[Discord Session] 💾 Manual save triggered...');
      
      // Flush all storage to disk
      await discordSession.flushStorageData();
      
      // Get cookie count
      const cookies = await discordSession.cookies.get({});
      console.log('[Discord Session] ✅ Saved', cookies.length, 'cookies');
      
      return { 
        success: true, 
        cookieCount: cookies.length,
        message: `Session saved! ${cookies.length} cookies stored.`
      };
    } catch (err) {
      console.error('[Discord Session] ❌ Save error:', err);
      return { 
        success: false, 
        error: err.message 
      };
    }
  });
  
  // Handle opening Discord browser
  ipcMain.on('open-discord-browser', (event) => {
    console.log('[IPC] Received: open-discord-browser');
    openDiscordBrowser();
  });
  
  // Handle closing Discord browser (hide, don't destroy)
  ipcMain.on('close-discord-browser', (event) => {
    hideDiscordBrowser();
  });
  
  // Handle showing Discord browser (when switching to Discord tab)
  ipcMain.on('show-discord-browser', (event) => {
    if (discordView) {
      showDiscordBrowser();
    } else {
      openDiscordBrowser();
    }
  });
  
  // Handle hiding Discord browser (when switching away from Discord tab)
  ipcMain.on('hide-discord-browser', (event) => {
    hideDiscordBrowser();
  });
  
  // Handle notification from Discord browser (changed to handle for response)
  ipcMain.handle('discord-notification', async (event, data) => {
    console.log('🔔 [Main] Received Discord notification IPC:', JSON.stringify(data, null, 2));
    const result = await forwardToTradeBot(data);
    return result;
  });
}

function openDiscordBrowser() {
  console.log('[Discord] openDiscordBrowser called');
  
  if (discordView) {
    console.log('[Discord] Already exists, showing...');
    mainWindow.addBrowserView(discordView);
    updateDiscordBounds();
    return;
  }
  
  console.log('[Discord] Creating new BrowserView...');
  discordView = new BrowserView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload', 'discord-preload.js'),
      partition: 'persist:discord'
    }
  });
  
  mainWindow.addBrowserView(discordView);
  
  // Position Discord in the content area (below title bar and nav)
  updateDiscordBounds();
  
  discordView.setAutoResize({
    width: true,
    height: true
  });
  
  // Handle resize (set up once)
  mainWindow.on('resize', () => {
    updateDiscordBounds();
  });
  
  // Hide placeholder when Discord loads
  discordView.webContents.on('did-finish-load', () => {
    console.log('[Discord] Discord page loaded successfully');
    mainWindow.webContents.send('discord-loaded');
  });
  
  discordView.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('[Discord] Failed to load:', errorCode, errorDescription);
  });
  
  // Handle resize (set up once)
  mainWindow.on('resize', () => {
    updateDiscordBounds();
  });
  
  // Hide placeholder when Discord loads
  discordView.webContents.on('did-finish-load', () => {
    console.log('[Discord] Discord page loaded successfully');
    mainWindow.webContents.send('discord-loaded');
  });
  
  discordView.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('[Discord] Failed to load:', errorCode, errorDescription);
  });
  
  // Load Discord
  console.log('[Discord] Loading Discord URL...');
  discordView.webContents.loadURL('https://discord.com/app');
}

function updateDiscordBounds() {
  if (!discordView || !mainWindow) return;
  
  const bounds = mainWindow.getBounds();
  // Position Discord in the scrollable container area (600px height box)
  discordView.setBounds({
    x: 20,  // Left padding
    y: 220,  // Below title bar, header, and nav
    width: bounds.width - 40,  // Full width minus padding
    height: 600  // Fixed height matching the container
  });
}

function hideDiscordBrowser() {
  if (discordView && mainWindow) {
    mainWindow.removeBrowserView(discordView);
    // Don't destroy - keep it so we can show again quickly
  }
}

function showDiscordBrowser() {
  if (discordView && mainWindow) {
    mainWindow.addBrowserView(discordView);
    updateDiscordBounds();
  }
}

async function forwardToTradeBot(notification) {
  try {
    const payload = {
      title: notification.title || '',
      message: notification.body || notification.message || '',
      source: 'discord_browser'
    };
    
    console.log('📤 [Main] Forwarding to TradeBot:', JSON.stringify(payload, null, 2));
    
    if (!ipcBridge) {
      console.error('❌ [Main] IPC bridge not initialized');
      return;
    }
    
    console.log('📡 [Main] Sending request via IPC bridge...');
    const response = await ipcBridge.sendRequest('POST', '/api/signals/receive', payload, {
      'Content-Type': 'application/json'
    });
    
    console.log('📥 [Main] Response received:', {
      status: response.status,
      data: response.data,
      headers: response.headers
    });
    
    if (response.status === 200 || response.status === 201) {
      console.log('✅ [Main] Notification forwarded to TradeBot successfully');
      if (response.data) {
        console.log('📋 [Main] Response data:', JSON.stringify(response.data, null, 2));
      }
      // Return response to renderer
      return {
        success: true,
        status: response.status,
        data: response.data,
        signal_id: response.data?.signal_id || null
      };
    } else {
      console.error('❌ [Main] TradeBot API returned error:', response.status);
      if (response.data) {
        console.error('📋 [Main] Error response data:', JSON.stringify(response.data, null, 2));
      }
      return {
        success: false,
        status: response.status,
        error: response.data || 'Unknown error'
      };
    }
  } catch (error) {
    console.error('❌ [Main] Error forwarding to TradeBot:', error);
    console.error('❌ [Main] Error stack:', error.stack);
    return {
      success: false,
      error: error.message || 'Unknown error'
    };
  }
}

// Register custom protocol for static files
function registerProtocol() {
  protocol.registerFileProtocol('tradeiq', (request, callback) => {
    try {
      const url = request.url.replace('tradeiq://', '');
      const filePath = path.join(__dirname, '..', url);
      
      // Security: Only allow files from app directory
      const appDir = path.join(__dirname, '..');
      const resolvedPath = path.resolve(filePath);
      
      console.log('[Protocol] Request:', request.url, '→', resolvedPath);
      
      if (!resolvedPath.startsWith(appDir)) {
        console.error('[Protocol] Access denied:', resolvedPath);
        callback({ error: -6 }); // ACCESS_DENIED
        return;
      }
      
      // Check if file exists
      const fs = require('fs');
      if (!fs.existsSync(resolvedPath)) {
        console.error('[Protocol] File not found:', resolvedPath);
        callback({ error: -6 }); // FILE_NOT_FOUND
        return;
      }
      
      console.log('[Protocol] Serving:', resolvedPath);
      callback({ path: resolvedPath });
    } catch (error) {
      console.error('[Protocol] Error:', error);
      callback({ error: -6 });
    }
  });
  
  console.log('[Protocol] tradeiq:// protocol registered');
}

app.whenReady().then(() => {
  // Register custom protocol before creating window
  registerProtocol();
  
  // Small delay to ensure protocol is registered
  setTimeout(() => {
    createWindow();
  }, 100);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (ipcBridge) {
    ipcBridge.stop();
  }
  
  if (httpServer) {
    httpServer.close();
  }
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', async (event) => {
  // Prevent quit until storage is flushed
  event.preventDefault();
  
  console.log('[App] Quitting - saving Discord session...');
  
  try {
    const discordSession = session.fromPartition('persist:discord');
    
    // Force flush all storage to disk
    await discordSession.flushStorageData();
    console.log('[Discord Session] ✅ Storage flushed to disk');
    
    // Get cookie count for verification
    const cookies = await discordSession.cookies.get({});
    console.log('[Discord Session] ✅ Saved', cookies.length, 'cookies');
    
  } catch (err) {
    console.error('[Discord Session] ❌ Error saving:', err);
  }
  
  if (ipcBridge) {
    ipcBridge.stop();
  }
  
  if (httpServer) {
    httpServer.close();
  }
  
  // Now actually quit
  app.exit(0);
});
