const { ipcRenderer } = require('electron');

// Discord notification interceptor
// This script runs in the Discord browser context and intercepts notifications

(function() {
  'use strict';
  
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
    console.log('Options:', options);
    
    // Create unique key for deduplication
    const key = `${title}_${options?.body || ''}_${Math.floor(Date.now() / 1000)}`;
    
    if (!processedNotifications.has(key)) {
      processedNotifications.add(key);
      
      // Remove from set after 2 seconds
      setTimeout(() => processedNotifications.delete(key), 2000);
      
      // Send to host (webview's parent renderer process)
      // For webviews, we use sendToHost() which sends to the parent page
      try {
        ipcRenderer.sendToHost('discord-notification', {
          title: title || '',
          body: options?.body || '',
          tag: options?.tag || '',
          icon: options?.icon || '',
          timestamp: Date.now()
        });
        console.log('✅ Notification sent to TradeIQ (via sendToHost)');
      } catch (error) {
        console.error('❌ Error sending notification:', error);
      }
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
  
  // Also intercept MutationObserver for Discord's custom notification system
  // Discord sometimes uses DOM-based notifications
  const observeDiscordNotifications = () => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Check for Discord notification elements
            if (node.matches && (
              node.matches('[class*="toast"]') ||
              node.matches('[class*="notification"]') ||
              node.matches('[class*="message-"]')
            )) {
              // Extract notification content
              const title = node.querySelector('[class*="title"]')?.textContent || '';
              const body = node.querySelector('[class*="body"]')?.textContent || 
                          node.querySelector('[class*="content"]')?.textContent || '';
              
              if (title || body) {
                const key = `dom_${title}_${body}_${Math.floor(Date.now() / 1000)}`;
                if (!processedNotifications.has(key)) {
                  processedNotifications.add(key);
                  setTimeout(() => processedNotifications.delete(key), 2000);
                  
                  console.log('🔔 Discord DOM notification detected:', { title, body });
                  ipcRenderer.sendToHost('discord-notification', {
                    title: title,
                    body: body,
                    timestamp: Date.now(),
                    source: 'dom'
                  });
                }
              }
            }
          }
        });
      });
    });
    
    // Start observing when DOM is ready
    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
      console.log('✅ Discord DOM observer started');
    } else {
      document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, {
          childList: true,
          subtree: true
        });
        console.log('✅ Discord DOM observer started (delayed)');
      });
    }
  };
  
  observeDiscordNotifications();
  
})();

console.log('Discord preload script loaded');

