// Discord Browser Module for TradeIQ Desktop
// This module provides an integrated Discord browser with automatic signal forwarding

(function() {
  'use strict';
  
  // Check if running in Electron - DYNAMIC check (not at load time)
  function isElectron() {
    return !!(window.electronAPI && window.electronAPI.isElectron);
  }
  
  // Discord browser state
  let discordBrowserOpen = false;
  let discordInitialized = false;
  
  // Initialize Discord Browser module
  function initDiscordBrowser() {
    console.log('Discord Browser module initialized');
    console.log('Running in Electron:', isElectron());
    
    // Note: Discord Browser button is already in HTML (More dropdown)
    // No need to add it programmatically
    
    // Add Discord Browser section to the page
    addDiscordBrowserSection();
  }
  
  function addDiscordBrowserSection() {
    // Check if section already exists
    if (document.getElementById('discord-browser-section')) return;
    
    // Create the Discord Browser section
    const section = document.createElement('div');
    section.id = 'discord-browser-section';
    section.className = 'discord-browser-section';
    section.style.display = 'none';
    const inElectron = isElectron();
    section.innerHTML = `
      <div class="discord-browser-header">
        <h3>💬 Discord Browser</h3>
        <div class="discord-browser-controls">
          <span id="discord-status" class="status-indicator status-disconnected">
            ${inElectron ? 'Click Open to start' : 'Electron required'}
          </span>
          ${inElectron ? `
            <button id="open-discord-btn" class="btn btn-primary" onclick="window.discordBrowser.open()">
              Open Discord
            </button>
            <button id="close-discord-btn" class="btn btn-secondary" onclick="window.discordBrowser.close()" style="display:none;">
              Close Discord
            </button>
          ` : `
            <div class="electron-required-notice">
              <p>⚠️ Discord Browser requires the Electron desktop app.</p>
              <p>Run <code>npm start</code> to use this feature.</p>
            </div>
          `}
        </div>
      </div>
      
      ${inElectron ? `
        <div class="discord-browser-info">
          <p>📍 Discord will open in the content area when you switch to this tab.</p>
          <p>🔔 Notifications from Discord will be automatically captured and forwarded to TradeIQ.</p>
          <p>📊 Matched signals will appear in your Dashboard.</p>
        </div>
      ` : `
        <div class="discord-browser-fallback">
          <h4>Alternative: Use Chrome Extension</h4>
          <p>If you're running TradeIQ in a browser, you can use the Chrome extension to capture Discord notifications:</p>
          <ol>
            <li>Load the extension from <code>chrome-notifications-to-whatsapp</code> folder</li>
            <li>Configure the TradeBot URL to: <code>http://localhost:5000/api/signals/receive</code></li>
            <li>Open Discord in Chrome and enable notifications</li>
          </ol>
        </div>
      `}
      
      <div class="recent-discord-signals">
        <h4>Recent Discord Signals</h4>
        <div id="discord-signals-list">
          <p class="no-signals">No Discord signals received yet.</p>
        </div>
      </div>
    `;
    
    // Add styles
    const style = document.createElement('style');
    style.textContent = `
      .discord-browser-section {
        padding: 20px;
        background: var(--card-bg, #1e1e2e);
        border-radius: 12px;
        margin: 20px;
      }
      .discord-browser-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 10px;
      }
      .discord-browser-header h3 {
        margin: 0;
        color: var(--text-primary, #fff);
      }
      .discord-browser-controls {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .status-indicator {
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 12px;
      }
      .status-connected {
        background: rgba(78, 205, 196, 0.2);
        color: #4ecdc4;
      }
      .status-disconnected {
        background: rgba(255, 107, 107, 0.2);
        color: #ff6b6b;
      }
      .discord-browser-info {
        background: rgba(78, 205, 196, 0.1);
        border-left: 4px solid #4ecdc4;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
      }
      .discord-browser-info p {
        margin: 8px 0;
        color: var(--text-secondary, #aaa);
      }
      .discord-browser-fallback {
        background: rgba(255, 193, 7, 0.1);
        border-left: 4px solid #ffc107;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
      }
      .discord-browser-fallback h4 {
        color: #ffc107;
        margin-top: 0;
      }
      .electron-required-notice {
        background: rgba(255, 107, 107, 0.1);
        padding: 10px 15px;
        border-radius: 8px;
      }
      .electron-required-notice p {
        margin: 5px 0;
        font-size: 13px;
      }
      .recent-discord-signals {
        margin-top: 20px;
      }
      .recent-discord-signals h4 {
        color: var(--text-primary, #fff);
        margin-bottom: 10px;
      }
      #discord-signals-list {
        max-height: 300px;
        overflow-y: auto;
      }
      .no-signals {
        color: var(--text-secondary, #666);
        font-style: italic;
      }
      .discord-signal-item {
        background: rgba(255,255,255,0.05);
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 8px;
      }
      .discord-signal-item .title {
        font-weight: bold;
        color: #7289da;
      }
      .discord-signal-item .message {
        color: var(--text-secondary, #aaa);
        margin-top: 5px;
      }
      .discord-signal-item .time {
        font-size: 11px;
        color: #666;
        margin-top: 5px;
      }
    `;
    document.head.appendChild(style);
    
    // Find the main content area and add the section
    const mainContent = document.querySelector('.main-content') || 
                       document.querySelector('main') || 
                       document.body;
    mainContent.appendChild(section);
  }
  
  function toggleDiscordBrowser() {
    const section = document.getElementById('discord-browser-section');
    if (section) {
      section.style.display = section.style.display === 'none' ? 'block' : 'none';
    }
  }
  
  function openDiscord() {
    if (!isElectron()) {
      alert('Discord Browser requires the Electron desktop app. Run "npm start" to use this feature.');
      return;
    }
    
    console.log('Opening Discord in webview...');
    
    // Trigger tab activation which handles webview loading
    onTabActivated();
  }
  
  function closeDiscord() {
    // With webview, we don't really "close" - just update UI state
    console.log('Discord webview remains loaded');
    discordBrowserOpen = false;
    updateUIState(false);
  }
  
  function addSignalToList(signal) {
    const list = document.getElementById('discord-signals-list');
    if (!list) return;
    
    // Remove "no signals" message
    const noSignals = list.querySelector('.no-signals');
    if (noSignals) noSignals.remove();
    
    // Create signal item
    const item = document.createElement('div');
    item.className = 'discord-signal-item';
    item.innerHTML = `
      <div class="title">${escapeHtml(signal.title || 'Discord Notification')}</div>
      <div class="message">${escapeHtml(signal.message || signal.body || '')}</div>
      <div class="time">${new Date().toLocaleTimeString()}</div>
    `;
    
    // Add to top of list
    list.insertBefore(item, list.firstChild);
    
    // Keep only last 20 signals
    while (list.children.length > 20) {
      list.removeChild(list.lastChild);
    }
  }
  
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Expose API
  window.discordBrowser = {
    init: initDiscordBrowser,
    open: openDiscord,
    close: closeDiscord,
    toggle: toggleDiscordBrowser,
    addSignal: addSignalToList,
    isOpen: () => discordBrowserOpen
  };
  
  // Update UI based on environment
  function updateUIForEnvironment() {
    const electronContent = document.getElementById('discord-browser-electron-content');
    const webContent = document.getElementById('discord-browser-web-content');
    const saveButton = document.getElementById('save-discord-session-btn');
    
    console.log('Updating UI for environment. isElectron:', isElectron());
    
    if (electronContent && webContent) {
      if (isElectron()) {
        electronContent.style.display = 'block';
        webContent.style.display = 'none';
        if (saveButton) saveButton.style.display = 'inline-block';
        console.log('Electron content shown');
      } else {
        electronContent.style.display = 'none';
        webContent.style.display = 'block';
        if (saveButton) saveButton.style.display = 'none';
        console.log('Web content shown');
      }
    }
  }
  
  // Override open/close to update inline UI
  const originalOpen = openDiscord;
  function openDiscordWithUI() {
    originalOpen();
    
    const status = document.getElementById('discord-browser-status');
    if (status) {
      status.textContent = 'Connected';
      status.className = 'status-badge status-connected';
    }
    
    const openBtn = document.getElementById('btn-open-discord');
    const closeBtn = document.getElementById('btn-close-discord');
    if (openBtn) openBtn.style.display = 'none';
    if (closeBtn) closeBtn.style.display = 'inline-block';
  }
  
  const originalClose = closeDiscord;
  function closeDiscordWithUI() {
    originalClose();
    
    const status = document.getElementById('discord-browser-status');
    if (status) {
      status.textContent = 'Not Connected';
      status.className = 'status-badge status-disconnected';
    }
    
    const openBtn = document.getElementById('btn-open-discord');
    const closeBtn = document.getElementById('btn-close-discord');
    if (openBtn) openBtn.style.display = 'inline-block';
    if (closeBtn) closeBtn.style.display = 'none';
  }
  
  // Auto-initialize when DOM is ready
  function init() {
    initDiscordBrowser();
    updateUIForEnvironment();
    
    // ALWAYS auto-load Discord on app start if in Electron
    if (isElectron()) {
      console.log('🚀 Auto-loading Discord on app start...');
      setTimeout(() => {
        onTabActivated();
      }, 1500); // Delay to ensure DOM is ready
    }
    
    // Auto-load Discord when section is opened (if in Electron)
    const discordSection = document.querySelector('details.collapse-section summary');
    if (discordSection) {
      // Watch for when the Discord section is opened
      const discordDetails = discordSection.closest('details');
      if (discordDetails) {
        const observer = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'open') {
              if (discordDetails.hasAttribute('open')) {
                console.log('Discord section opened, initializing...');
                setTimeout(() => {
                  if (isElectron()) {
                    onTabActivated();
                  }
                }, 100);
              }
            }
          });
        });
        observer.observe(discordDetails, { attributes: true });
      }
    }
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  // Inject notification interceptor into the webview
  function injectNotificationInterceptor(webview) {
    if (!webview) return;
    
    const interceptorCode = `
      (function() {
        if (window.__notificationInterceptorInstalled) {
          console.log('🔔 Notification interceptor already installed');
          return;
        }
        window.__notificationInterceptorInstalled = true;
        
        console.log('🚀 Discord notification interceptor starting...');
        
        // Store original Notification
        const OriginalNotification = window.Notification;
        
        if (!OriginalNotification) {
          console.warn('Notification API not available');
          return;
        }
        
        // Track processed notifications to avoid duplicates
        const processedNotifications = new Set();
        
        // Override Notification constructor
        window.Notification = function(title, options) {
          console.log('🔔 Discord Notification intercepted!');
          console.log('Title:', title);
          console.log('Options:', JSON.stringify(options));
          
          // Create unique key for deduplication
          const key = title + '_' + (options?.body || '') + '_' + Math.floor(Date.now() / 1000);
          
          if (!processedNotifications.has(key)) {
            processedNotifications.add(key);
            
            // Remove from set after 2 seconds
            setTimeout(() => processedNotifications.delete(key), 2000);
            
            // Log notification data in JSON format for parent to parse
            console.log('__DISCORD_NOTIFICATION__' + JSON.stringify({
              title: title || '',
              body: options?.body || '',
              tag: options?.tag || '',
              timestamp: Date.now()
            }));
            
            console.log('✅ Notification logged for parent to capture');
          } else {
            console.log('⚠️ Duplicate notification, skipping');
          }
          
          // Create original notification so it still appears
          try {
            return new OriginalNotification(title, options);
          } catch (error) {
            console.error('Error creating original notification:', error);
            return {
              close: () => {},
              addEventListener: () => {},
              removeEventListener: () => {},
              onclick: null,
              onshow: null,
              onclose: null,
              onerror: null
            };
          }
        };
        
        // Copy static properties
        try {
          Object.setPrototypeOf(window.Notification, OriginalNotification);
          window.Notification.prototype = OriginalNotification.prototype;
          
          Object.defineProperty(window.Notification, 'permission', {
            get: () => OriginalNotification.permission,
            configurable: true,
            enumerable: true
          });
          
          if (OriginalNotification.requestPermission) {
            window.Notification.requestPermission = OriginalNotification.requestPermission.bind(OriginalNotification);
          }
          
          console.log('✅ Discord notification interceptor installed');
        } catch (error) {
          console.error('❌ Error setting up Notification properties:', error);
        }
      })();
    `;
    
    webview.executeJavaScript(interceptorCode)
      .then(() => {
        console.log('✅ Notification interceptor injected into Discord webview');
      })
      .catch(err => {
        console.error('❌ Failed to inject notification interceptor:', err);
      });
  }
  
  // Calculate and apply zoom factor to fit Discord in container
  function applyZoomFactor(webview) {
    if (!webview) return;
    
    const container = document.getElementById('discord-container');
    if (!container) return;
    
    // Discord works best at around 1280px width minimum
    const desiredWidth = 1280;
    const desiredHeight = 800;
    
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    
    // Calculate zoom factor based on both width and height, use the smaller one
    const widthZoom = containerWidth / desiredWidth;
    const heightZoom = containerHeight / desiredHeight;
    const zoomFactor = Math.min(widthZoom, heightZoom, 1); // Never zoom above 100%
    
    // Apply zoom factor (minimum 0.5 to keep it readable)
    const finalZoom = Math.max(zoomFactor, 0.5);
    webview.setZoomFactor(finalZoom);
    
    console.log(`Discord zoom factor set to ${finalZoom.toFixed(2)} (container: ${containerWidth}x${containerHeight})`);
  }
  
  // Called when Discord Browser tab becomes active
  function onTabActivated() {
    console.log('🔵 Discord Browser tab activated. isElectron:', isElectron());
    
    if (!isElectron()) {
      console.log('Not in Electron, skipping auto-open');
      return;
    }
    
    // Update environment UI first
    updateUIForEnvironment();
    
    // Show the electron content if in Electron
    const electronContent = document.getElementById('discord-browser-electron-content');
    if (electronContent && isElectron()) {
      electronContent.style.display = 'block';
    }
    
    // Load Discord in webview if not already loaded
    const webview = document.getElementById('discord-webview');
    const loading = document.getElementById('discord-loading');
    
    if (!webview) {
      console.error('❌ Discord webview element not found!');
      return;
    }
    
    if (!discordInitialized) {
      console.log('🚀 First time opening Discord, loading in webview...');
      discordInitialized = true;
      
      // Set up webview event listeners FIRST (before loading)
      webview.addEventListener('did-finish-load', () => {
        console.log('Discord webview loaded');
        if (loading) loading.style.display = 'none';
        discordBrowserOpen = true;
        updateUIState(true);
        
        // Apply zoom factor to fit container
        applyZoomFactor(webview);
        
        // Inject notification interceptor directly (preload doesn't work for dynamically set attributes)
        injectNotificationInterceptor(webview);
      });
      
      webview.addEventListener('did-fail-load', (event) => {
        console.error('Discord webview failed to load:', event);
        if (loading) {
          loading.innerHTML = '<p style="color: #ff6b6b;">Failed to load Discord</p><p>Check your internet connection</p>';
        }
      });
      
      // Intercept console messages from webview for notification detection
      webview.addEventListener('console-message', (event) => {
        const msg = event.message;
        
        // Check for our notification marker
        if (msg.startsWith('__DISCORD_NOTIFICATION__')) {
          try {
            const jsonStr = msg.replace('__DISCORD_NOTIFICATION__', '');
            const notificationData = JSON.parse(jsonStr);
            console.log('🔔 Captured Discord notification:', notificationData);
            
            // Forward to backend
            forwardNotificationToBackend(notificationData);
          } catch (e) {
            console.error('Failed to parse notification data:', e);
          }
        } else if (msg.includes('notification') || msg.includes('Notification') || 
                   msg.includes('interceptor') || msg.includes('🔔') || msg.includes('🚀')) {
          // Log notification-related messages for debugging
          console.log('[Discord Webview]', msg);
        }
      });
      
      // Function to forward notification to backend
      function forwardNotificationToBackend(notificationData) {
        const payload = {
          title: notificationData.title || '',
          message: notificationData.body || '',
          source: 'discord_browser'
        };
        
        console.log('📤 Forwarding notification to backend:', payload);
        
        // Use electronAPI if available (sends to main process which forwards to Python)
        if (window.electronAPI && window.electronAPI.sendDiscordNotification) {
          console.log('📡 Using electronAPI.sendDiscordNotification...');
          window.electronAPI.sendDiscordNotification(notificationData)
            .then(result => {
              console.log('📥 [Discord] Backend response received:', result);
              if (result && result.success) {
                console.log('✅ Signal created successfully! Signal ID:', result.signal_id);
                // Trigger dashboard refresh after a short delay
                setTimeout(() => {
                  if (typeof loadAllSignals === 'function') {
                    console.log('🔄 Refreshing dashboard to show new signal...');
                    loadAllSignals();
                  } else {
                    console.warn('⚠️ loadAllSignals function not available');
                  }
                }, 2000);
              } else {
                console.error('❌ Failed to create signal:', result?.error || 'Unknown error');
              }
            })
            .catch(error => {
              console.error('❌ Error sending notification:', error);
            });
        } else {
          // Fallback to fetch (should work with API wrapper)
          console.log('📡 Using fetch fallback...');
          fetch('/api/signals/receive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          }).then(response => {
            if (response.ok) {
              console.log('✅ Notification forwarded to backend via fetch');
              return response.json();
            } else {
              console.error('❌ Failed to forward notification:', response.status);
              return response.text().then(text => {
                console.error('Response body:', text);
              });
            }
          }).then(data => {
            if (data) {
              console.log('📋 Backend response:', JSON.stringify(data, null, 2));
              if (data.signal_id) {
                console.log('✅ Signal created with ID:', data.signal_id);
              }
            }
            // Trigger dashboard refresh
            setTimeout(() => {
              if (typeof loadAllSignals === 'function') {
                console.log('🔄 Refreshing dashboard to show new signal...');
                loadAllSignals();
              } else {
                console.warn('⚠️ loadAllSignals function not available');
                // Try to switch to dashboard tab and refresh
                if (typeof switchTab === 'function') {
                  switchTab('dashboard');
                  setTimeout(() => {
                    if (typeof loadAllSignals === 'function') {
                      loadAllSignals();
                    }
                  }, 500);
                }
              }
            }, 2000);
          }).catch(error => {
            console.error('❌ Error forwarding notification:', error);
          });
        }
      }
      
      // Listen for IPC messages from webview (notifications sent via sendToHost)
      webview.addEventListener('ipc-message', (event) => {
        console.log('📨 IPC message received from webview:', event.channel, event.args);
        if (event.channel === 'discord-notification') {
          const notificationData = event.args[0];
          console.log('🔔 Received Discord notification from webview:', notificationData);
          
          // Forward to main process via electronAPI
          if (window.electronAPI && window.electronAPI.sendDiscordNotification) {
            console.log('📤 Forwarding notification via electronAPI...');
            window.electronAPI.sendDiscordNotification(notificationData);
          } else {
            console.warn('⚠️ electronAPI.sendDiscordNotification not available, using fetch fallback');
            // Fallback: try to use fetch to send to backend
            const payload = {
              title: notificationData.title || '',
              message: notificationData.body || notificationData.message || '',
              source: 'discord_browser'
            };
            console.log('📤 Sending notification via fetch:', payload);
            fetch('/api/signals/receive', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
            }).then(response => {
              if (response.ok) {
                console.log('✅ Notification forwarded to backend via fetch');
                return response.json();
              } else {
                console.error('❌ Failed to forward notification:', response.status);
                return response.text().then(text => {
                  console.error('Response body:', text);
                });
              }
            }).catch(error => {
              console.error('❌ Error forwarding notification:', error);
            });
          }
        }
      });
      
      // Add resize listener to recalculate zoom when window changes
      let resizeTimeout;
      window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
          if (discordBrowserOpen) {
            applyZoomFactor(webview);
          }
        }, 200);
      });
      
      // Function to load Discord URL
      const loadDiscordUrl = () => {
        console.log('📡 Loading Discord URL...');
        // Check if webview already has a URL (might be logged in from previous session)
        if (webview.src && webview.src !== 'about:blank' && webview.src.includes('discord.com')) {
          console.log('Discord already loaded, reloading to check login status...');
          webview.reload();
        } else {
          webview.src = 'https://discord.com/app';
        }
      };
      
      // Set preload script path (must be absolute with file:// prefix) - WAIT before loading URL
      if (window.electronAPI && window.electronAPI.getPreloadPath) {
        console.log('🔧 Getting preload script path...');
        window.electronAPI.getPreloadPath('discord-preload.js').then(preloadPath => {
          if (preloadPath) {
            // Webview preload needs file:// prefix
            const preloadUrl = preloadPath.startsWith('file://') ? preloadPath : `file://${preloadPath}`;
            console.log('✅ Discord preload script set to:', preloadUrl);
            webview.setAttribute('preload', preloadUrl);
          } else {
            console.warn('⚠️ Preload path was empty');
          }
          // Load Discord AFTER preload is set
          loadDiscordUrl();
        }).catch(err => {
          console.error('❌ Failed to get preload path:', err);
          // Still load Discord even if preload fails
          loadDiscordUrl();
        });
      } else {
        console.warn('⚠️ electronAPI.getPreloadPath not available, loading without preload');
        loadDiscordUrl();
      }
    } else if (discordInitialized) {
      console.log('✅ Discord already initialized, ensuring it\'s visible');
      discordBrowserOpen = true;
      updateUIState(true);
      
      // Reapply zoom factor in case container size changed
      applyZoomFactor(webview);
      
      // Ensure webview is visible and loaded
      if (webview.src === 'about:blank' || !webview.src) {
        console.log('🔄 Loading Discord (src was blank)');
        webview.src = 'https://discord.com/app';
      } else {
        // Already has a URL, might be logged in - just ensure it's visible
        console.log('✅ Discord webview already has URL:', webview.src);
        if (loading) loading.style.display = 'none';
      }
    }
  }
  
  // Called when switching away from Discord Browser tab
  function onTabDeactivated() {
    // Webview stays in DOM, no need to hide
    console.log('Discord Browser tab deactivated');
  }
  
  function updateUIState(isOpen) {
    const status = document.getElementById('discord-browser-status');
    const openBtn = document.getElementById('btn-open-discord');
    const closeBtn = document.getElementById('btn-close-discord');
    
    if (status) {
      status.textContent = isOpen ? 'Connected' : 'Not Connected';
      status.className = isOpen ? 'status-badge status-connected' : 'status-badge status-disconnected';
    }
    if (openBtn) {
      openBtn.style.display = isOpen ? 'none' : 'inline-block';
      // Show button initially if in Electron
      if (isElectron() && !isOpen) {
        openBtn.style.display = 'inline-block';
      }
    }
    if (closeBtn) closeBtn.style.display = isOpen ? 'inline-block' : 'none';
  }
  
  // Update exposed API
  window.discordBrowser = {
    init: initDiscordBrowser,
    open: openDiscordWithUI,
    close: closeDiscordWithUI,
    toggle: toggleDiscordBrowser,
    addSignal: addSignalToList,
    isOpen: () => discordBrowserOpen,
    onTabActivated: onTabActivated,
    onTabDeactivated: onTabDeactivated
  };
  
})();

