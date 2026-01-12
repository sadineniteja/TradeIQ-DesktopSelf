// Service Worker for TradeIQ PWA
// Based on working iOS push notification example: https://github.com/andreinwald/webpush-ios-example

const CACHE_NAME = 'tradeiq-v1';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/x.js'
];

// Install event - cache resources
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching app shell');
        return cache.addAll(urlsToCache);
      })
      .catch((error) => {
        console.error('[SW] Cache failed:', error);
      })
  );
  self.skipWaiting(); // Activate immediately
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim(); // Take control of all pages immediately
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
      .catch(() => {
        // If both fail, return offline page if available
        return caches.match('/');
      })
  );
});

// Push event - CRITICAL for iOS: must show notification immediately
// Based on working example from: https://github.com/andreinwald/webpush-ios-example
self.addEventListener('push', (event) => {
  console.log('[SW] Push event received');
  
  let pushData = {
    title: 'TradeIQ Notification',
    body: 'You have a new notification',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-192x192.png',
    data: {
      url: '/'
    }
  };

  // Try to parse push data if available
  if (event.data) {
    try {
      const data = event.data.json();
      pushData = {
        title: data.title || pushData.title,
        body: data.body || pushData.body,
        icon: data.icon || pushData.icon,
        badge: data.badge || pushData.badge,
        image: data.image,
        data: data.data || pushData.data,
        tag: data.tag,
        requireInteraction: data.requireInteraction || false,
        actions: data.actions
      };
    } catch (e) {
      // If JSON parsing fails, try text
      const text = event.data.text();
      if (text) {
        pushData.body = text;
      }
    }
  }

  // CRITICAL: Use event.waitUntil() to ensure notification is shown
  // iOS Safari requires immediate notification display
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(pushData.title, pushData),
      // Update app icon badge count
      updateBadgeCount()
    ])
  );
});

// Global badge count for the service worker
let currentBadgeCount = 0;

// Update app icon badge count (increments by 1 for each push notification)
async function updateBadgeCount() {
  try {
    // Increment badge count
    currentBadgeCount = currentBadgeCount + 1;
    
    // Set badge on app icon
    if ('setAppBadge' in navigator) {
      await navigator.setAppBadge(currentBadgeCount);
      // Only log when count is set (not on every increment to reduce spam)
      // console.log('[SW] App badge updated to:', currentBadgeCount);
    } else if ('setClientBadge' in self.registration) {
      await self.registration.setClientBadge(currentBadgeCount);
      // console.log('[SW] App badge updated to:', currentBadgeCount);
    }
  } catch (error) {
    console.error('[SW] Error updating badge:', error);
  }
}

// Notification click event
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked');
  console.log('[SW] Notification data:', event.notification.data);
  
  event.notification.close();
  
  // Clear badge when notification is clicked (user is opening the app)
  currentBadgeCount = 0;
  clearBadge();

  const notificationData = event.notification.data || {};
  const signalId = notificationData.signal_id;
  const action = notificationData.action;
  const tab = notificationData.tab;
  // Include signal ID in URL hash for deep linking
  const urlToOpen = signalId ? `${notificationData.url || '/'}#signal-${signalId}` : (notificationData.url || '/');

  event.waitUntil(
    clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then((clientList) => {
      // Check if there's already a window/tab open
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if ('focus' in client) {
          // Focus the client and send message to navigate to signal
          client.focus();
          
          // Send message to navigate to signal if signal ID is provided
          if (signalId && action === 'view_signal') {
            client.postMessage({
              type: 'navigate_to_signal',
              signal_id: signalId,
              tab: tab || 'x'
            });
          }
          
          return Promise.resolve();
        }
      }
      // If no window is open, open a new one
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen).then((windowClient) => {
          // Wait a bit for the page to load, then send message
          if (windowClient && signalId && action === 'view_signal') {
            setTimeout(() => {
              windowClient.postMessage({
                type: 'navigate_to_signal',
                signal_id: signalId,
                tab: tab || 'x'
              });
            }, 1000);
          }
          return windowClient;
        });
      }
    })
  );
});

// Notification close event (optional, for analytics)
self.addEventListener('notificationclose', (event) => {
  console.log('[SW] Notification closed');
  // You can send analytics here if needed
});

// Clear app icon badge
async function clearBadge() {
  try {
    currentBadgeCount = 0;
    if ('clearAppBadge' in navigator) {
      await navigator.clearAppBadge();
      // Reduce logging - only log when actually clearing (not on every message)
      // console.log('[SW] App badge cleared');
    } else if ('clearClientBadge' in self.registration) {
      await self.registration.clearClientBadge();
      // console.log('[SW] App badge cleared');
    }
  } catch (error) {
    console.error('[SW] Error clearing badge:', error);
  }
}

// Listen for messages from main app to update badge
self.addEventListener('message', (event) => {
  // Only log non-badge messages to reduce console spam
  if (event.data && event.data.type !== 'update_badge' && event.data.type !== 'clear_badge') {
    console.log('[SW] Message received:', event.data);
  }
  
  if (event.data && event.data.type === 'update_badge') {
    const count = event.data.count || 0;
    // Only update if count actually changed
    if (count !== currentBadgeCount) {
      updateBadgeFromCount(count);
    }
  } else if (event.data && event.data.type === 'clear_badge') {
    if (currentBadgeCount > 0) {
      clearBadge();
    }
  }
});

// Update badge from a specific count
async function updateBadgeFromCount(count) {
  try {
    currentBadgeCount = count;
    if (count > 0) {
      if ('setAppBadge' in navigator) {
        await navigator.setAppBadge(count);
        // Only log when count changes significantly or is set (not cleared)
        console.log('[SW] App badge set to:', count);
      } else if ('setClientBadge' in self.registration) {
        await self.registration.setClientBadge(count);
        console.log('[SW] App badge set to:', count);
      }
    } else {
      await clearBadge();
    }
  } catch (error) {
    console.error('[SW] Error updating badge from count:', error);
  }
}
