// PWA Push Notification Handler for TradeIQ
// Based on working iOS example: https://github.com/andreinwald/webpush-ios-example

class PWAPushManager {
  constructor() {
    this.vapidPublicKey = null;
    this.subscription = null;
    this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
  }

  // Check if running as PWA on iOS
  isIOSStandalone() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isStandalone = window.navigator.standalone || 
                        window.matchMedia('(display-mode: standalone)').matches;
    return isIOS && isStandalone;
  }

  // Check if PWA is installed (for iOS)
  isPWAInstalled() {
    // iOS specific check
    if (window.navigator.standalone) {
      return true;
    }
    // Other platforms
    if (window.matchMedia('(display-mode: standalone)').matches) {
      return true;
    }
    return false;
  }

  // Get VAPID public key from backend
  async getVapidPublicKey() {
    if (this.vapidPublicKey) {
      return this.vapidPublicKey;
    }

    try {
      const response = await fetch('/api/push/vapid-public-key');
      const data = await response.json();
      
      if (data.success && data.public_key) {
        this.vapidPublicKey = data.public_key;
        return this.vapidPublicKey;
      }
      
      throw new Error('VAPID public key not available');
    } catch (error) {
      console.error('[PWA] Error fetching VAPID key:', error);
      throw error;
    }
  }

  // Convert VAPID key from base64 URL-safe to Uint8Array
  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/\-/g, '+')
      .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    
    return outputArray;
  }

  // Register service worker (simple, direct - based on working example)
  async registerServiceWorker() {
    if (!this.isSupported) {
      throw new Error('Service Worker or Push Manager not supported');
    }

    try {
      const registration = await navigator.serviceWorker.register('/sw.js');
      console.log('[PWA] Service worker registered:', registration.scope);
      return registration;
    } catch (error) {
      console.error('[PWA] Service worker registration failed:', error);
      throw error;
    }
  }

  // Subscribe to push notifications (based on working example)
  async subscribe() {
    if (!this.isSupported) {
      return { success: false, error: 'Push notifications not supported' };
    }

    // Check if iOS PWA is installed
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS && !window.navigator.standalone) {
      return {
        success: false,
        error: 'iOS requires PWA installation. Please add to Home Screen first.',
        requiresInstall: true
      };
    }

    try {
      // Step 1: Register service worker (simple, direct)
      await this.registerServiceWorker();

      // Step 2: Wait for service worker to be ready
      const registration = await navigator.serviceWorker.ready;

      // Step 3: Check if already subscribed
      this.subscription = await registration.pushManager.getSubscription();
      if (this.subscription) {
        console.log('[PWA] Already subscribed');
        return { success: true, subscription: this.subscription, alreadySubscribed: true };
      }

      // Step 4: Request notification permission
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        return { success: false, error: 'Notification permission denied' };
      }

      // Step 5: Get VAPID public key
      const vapidPublicKey = await this.getVapidPublicKey();
      if (!vapidPublicKey) {
        return { success: false, error: 'VAPID public key not available' };
      }

      // Step 6: Convert VAPID key to Uint8Array
      const applicationServerKey = this.urlBase64ToUint8Array(vapidPublicKey);

      // Step 7: Subscribe (simple, direct - exactly like working example)
      const subscriptionOptions = {
        userVisibleOnly: true,  // Required for iOS
        applicationServerKey: applicationServerKey
      };

      this.subscription = await registration.pushManager.subscribe(subscriptionOptions);
      
      console.log('[PWA] Subscription successful:', this.subscription.toJSON());

      // Step 8: Send subscription to backend
      await this.sendSubscriptionToBackend(this.subscription);

      return { success: true, subscription: this.subscription };
    } catch (error) {
      console.error('[PWA] Subscription error:', error);
      return { success: false, error: error.message };
    }
  }

  // Send subscription to backend
  async sendSubscriptionToBackend(subscription) {
    try {
      const response = await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          subscription: subscription.toJSON()
        })
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'Failed to save subscription');
      }

      console.log('[PWA] Subscription saved to backend');
      return data;
    } catch (error) {
      console.error('[PWA] Error saving subscription:', error);
      throw error;
    }
  }

  // Unsubscribe from push notifications
  async unsubscribe() {
    try {
      if (this.subscription) {
        await this.subscription.unsubscribe();
        this.subscription = null;
      }

      // Also get current subscription from service worker
      const registration = await navigator.serviceWorker.ready;
      const currentSubscription = await registration.pushManager.getSubscription();
      if (currentSubscription) {
        await currentSubscription.unsubscribe();
      }

      // Remove from backend
      await fetch('/api/push/unsubscribe', {
        method: 'POST'
      });

      return { success: true };
    } catch (error) {
      console.error('[PWA] Unsubscribe error:', error);
      return { success: false, error: error.message };
    }
  }

  // Check subscription status
  async getSubscriptionStatus() {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      
      if (subscription) {
        this.subscription = subscription;
        return {
          subscribed: true,
          subscription: subscription.toJSON()
        };
      }

      return { subscribed: false };
    } catch (error) {
      console.error('[PWA] Error checking subscription:', error);
      return { subscribed: false, error: error.message };
    }
  }
}

// Global instance
window.pwaPushManager = new PWAPushManager();
