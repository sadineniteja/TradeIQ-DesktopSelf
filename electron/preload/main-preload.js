const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer (main TradeIQ UI)
contextBridge.exposeInMainWorld('electronAPI', {
  // API request handler (replaces fetch)
  apiRequest: async (method, apiPath, body, headers) => {
    return await ipcRenderer.invoke('api-request', method, apiPath, body, headers);
  },
  
  // Window control functions
  windowMinimize: () => ipcRenderer.send('window-minimize'),
  windowMaximize: () => ipcRenderer.send('window-maximize'),
  windowClose: () => ipcRenderer.send('window-close'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  
  // Open Discord browser
  openDiscordBrowser: () => {
    ipcRenderer.send('open-discord-browser');
  },
  
  // Close Discord browser
  closeDiscordBrowser: () => {
    ipcRenderer.send('close-discord-browser');
  },
  
  // Show Discord browser (when switching to Discord tab)
  showDiscordBrowser: () => {
    ipcRenderer.send('show-discord-browser');
  },
  
  // Hide Discord browser (when switching away from Discord tab)
  hideDiscordBrowser: () => {
    ipcRenderer.send('hide-discord-browser');
  },
  
  // Check if running in Electron
  isElectron: true,
  
  // Listen for Discord loaded event
  onDiscordLoaded: (callback) => {
    ipcRenderer.on('discord-loaded', callback);
  },
  
  // Send Discord notification to main process (with response callback)
  sendDiscordNotification: async (notification) => {
    return new Promise((resolve, reject) => {
      // Use invoke instead of send to get a response
      ipcRenderer.invoke('discord-notification', notification)
        .then(result => {
          console.log('📥 [Renderer] Backend response:', result);
          resolve(result);
        })
        .catch(error => {
          console.error('❌ [Renderer] Error sending notification:', error);
          reject(error);
        });
    });
  },
  
  // Get preload script path for webviews
  getPreloadPath: (filename) => {
    return ipcRenderer.invoke('get-preload-path', filename);
  },
  
  // Save Discord session manually
  saveDiscordSession: async () => {
    return await ipcRenderer.invoke('save-discord-session');
  }
});

console.log('TradeIQ main preload script loaded');

