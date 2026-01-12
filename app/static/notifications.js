// Notifications Tab UI Logic
// Based on working iOS push notification example

let notificationStatusCheckInterval = null;

// Initialize notifications tab
document.addEventListener('DOMContentLoaded', function() {
    // Check if using HTTPS (required for service workers and push notifications)
    if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        const resultDiv = document.getElementById('notification-result');
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.className = 'result-box error show';
            resultDiv.innerHTML = `
                <strong>⚠️ HTTPS Required for Push Notifications!</strong><br>
                Service workers and push notifications require HTTPS.<br>
                Please use ngrok or another HTTPS tunnel.<br>
                <br>
                <strong>Quick Start:</strong><br>
                1. Run: <code>./start-ngrok.sh</code><br>
                2. Use the HTTPS URL shown (e.g., https://abc123.ngrok.io)
            `;
        }
    }

    // Register service worker on page load (skip in Electron - not needed)
    if ('serviceWorker' in navigator && !(window.electronAPI && window.electronAPI.isElectron)) {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('[Notifications] Service worker registered:', registration.scope);
            })
            .catch((error) => {
                console.error('[Notifications] Service worker registration failed:', error);
                // Show error if not HTTPS
                if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
                    const resultDiv = document.getElementById('notification-result');
                    if (resultDiv) {
                        resultDiv.style.display = 'block';
                        resultDiv.className = 'result-box error show';
                        resultDiv.innerHTML = `
                            <strong>❌ Service Worker Registration Failed</strong><br>
                            Service workers require HTTPS (except localhost).<br>
                            Please use ngrok: <code>./start-ngrok.sh</code>
                        `;
                    }
                }
            });
    } else if (window.electronAPI && window.electronAPI.isElectron) {
        console.log('[Notifications] Skipping service worker registration in Electron (not needed)');
    }

    // Check status when notifications tab is opened
    const notificationsTab = document.getElementById('notifications-tab');
    if (notificationsTab) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (notificationsTab.classList.contains('active')) {
                        checkNotificationStatus();
                        loadVapidKeys();
                    }
                }
            });
        });
        observer.observe(notificationsTab, { attributes: true });
    }

    // Initial status check
    checkNotificationStatus();
});

// Check all notification statuses
async function checkNotificationStatus() {
    await checkPWAInstallStatus();
    await checkNotificationPermission();
    await checkSubscriptionStatus();
}

// Check if PWA is installed
async function checkPWAInstallStatus() {
    const statusEl = document.getElementById('pwa-install-status');
    if (!statusEl) return;

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isStandalone = window.navigator.standalone || 
                        window.matchMedia('(display-mode: standalone)').matches;

    if (isIOS) {
        if (window.navigator.standalone) {
            statusEl.textContent = '✅ Installed as PWA (iOS)';
            statusEl.style.color = '#10b981';
        } else {
            statusEl.textContent = '❌ Not installed - Add to Home Screen required';
            statusEl.style.color = '#ef4444';
        }
    } else {
        if (isStandalone) {
            statusEl.textContent = '✅ Installed as PWA';
            statusEl.style.color = '#10b981';
        } else {
            statusEl.textContent = '⚠️ Not in PWA mode (optional for desktop)';
            statusEl.style.color = '#f59e0b';
        }
    }
}

// Check notification permission
async function checkNotificationPermission() {
    const statusEl = document.getElementById('notification-permission-status');
    if (!statusEl) return;

    if (!('Notification' in window)) {
        statusEl.textContent = '❌ Not supported';
        statusEl.style.color = '#ef4444';
        return;
    }

    const permission = Notification.permission;
    switch (permission) {
        case 'granted':
            statusEl.textContent = '✅ Permission granted';
            statusEl.style.color = '#10b981';
            break;
        case 'denied':
            statusEl.textContent = '❌ Permission denied';
            statusEl.style.color = '#ef4444';
            break;
        default:
            statusEl.textContent = '⏳ Permission not requested';
            statusEl.style.color = '#f59e0b';
    }
}

// Check subscription status
async function checkSubscriptionStatus() {
    const statusEl = document.getElementById('subscription-status');
    const subscribeBtn = document.getElementById('subscribe-btn');
    const unsubscribeBtn = document.getElementById('unsubscribe-btn');
    
    if (!statusEl) return;

    try {
        const status = await window.pwaPushManager.getSubscriptionStatus();
        
        if (status.subscribed) {
            statusEl.textContent = '✅ Subscribed';
            statusEl.style.color = '#10b981';
            if (subscribeBtn) subscribeBtn.style.display = 'none';
            if (unsubscribeBtn) unsubscribeBtn.style.display = 'inline-block';
        } else {
            statusEl.textContent = '❌ Not subscribed';
            statusEl.style.color = '#ef4444';
            if (subscribeBtn) subscribeBtn.style.display = 'inline-block';
            if (unsubscribeBtn) unsubscribeBtn.style.display = 'none';
        }
    } catch (error) {
        statusEl.textContent = '❌ Error checking status';
        statusEl.style.color = '#ef4444';
        console.error('[Notifications] Error checking subscription:', error);
    }
}

// Subscribe to notifications
async function subscribeToNotifications() {
    const resultDiv = document.getElementById('notification-result');
    const subscribeBtn = document.getElementById('subscribe-btn');
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Subscribing to push notifications...';
    }

    if (subscribeBtn) {
        subscribeBtn.disabled = true;
        subscribeBtn.textContent = 'Subscribing...';
    }

    try {
        const result = await window.pwaPushManager.subscribe();

        if (result.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                if (result.alreadySubscribed) {
                    resultDiv.textContent = '✅ Already subscribed to notifications!';
                } else {
                    resultDiv.textContent = '✅ Successfully subscribed to push notifications!';
                }
            }
            await checkSubscriptionStatus();
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                let errorMsg = result.error || 'Unknown error';
                
                if (result.requiresInstall) {
                    errorMsg = '❌ iOS requires PWA installation. Please add this app to your Home Screen first, then open it from the home screen icon.';
                }
                
                resultDiv.textContent = errorMsg;
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Subscribe error:', error);
    } finally {
        if (subscribeBtn) {
            subscribeBtn.disabled = false;
            subscribeBtn.textContent = '🔔 Subscribe to Notifications';
        }
    }
}

// Unsubscribe from notifications
async function unsubscribeFromNotifications() {
    if (!confirm('Are you sure you want to unsubscribe from push notifications?')) {
        return;
    }

    const resultDiv = document.getElementById('notification-result');
    const unsubscribeBtn = document.getElementById('unsubscribe-btn');

    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Unsubscribing...';
    }

    if (unsubscribeBtn) {
        unsubscribeBtn.disabled = true;
    }

    try {
        const result = await window.pwaPushManager.unsubscribe();

        if (result.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.textContent = '✅ Successfully unsubscribed from push notifications.';
            }
            await checkSubscriptionStatus();
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (result.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Unsubscribe error:', error);
    } finally {
        if (unsubscribeBtn) {
            unsubscribeBtn.disabled = false;
        }
    }
}

// Generate VAPID keys
async function generateVapidKeys() {
    const resultDiv = document.getElementById('vapid-keys-result');
    const privateKeyField = document.getElementById('vapid-private-key');
    const publicKeyField = document.getElementById('vapid-public-key');
    const generateBtn = document.querySelector('button[onclick*="generateVapidKeys"]');
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Generating VAPID keys...';
    }

    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = 'Generating...';
    }

    try {
        console.log('[Notifications] Calling /api/push/vapid-keys/generate');
        const response = await fetch('/api/push/vapid-keys/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        console.log('[Notifications] Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('[Notifications] Response data:', data);

        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.textContent = '✅ VAPID keys generated successfully! Keys are now in the form fields below.';
            }
            
            // Fill in the form fields
            if (privateKeyField) {
                privateKeyField.value = data.private_key || '';
            }
            if (publicKeyField) {
                publicKeyField.value = data.public_key_pem || '';
            }
            
            // Store base64 key in a data attribute for later use
            if (publicKeyField && data.public_key_base64) {
                publicKeyField.setAttribute('data-base64-key', data.public_key_base64);
            }
            
            // Set default email if not set
            const emailField = document.getElementById('vapid-email');
            if (emailField && !emailField.value) {
                emailField.value = 'mailto:tradeiq@example.com';
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (data.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Generate VAPID keys error:', error);
    } finally {
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.textContent = '🔑 Generate New VAPID Keys';
        }
    }
}

// Load existing VAPID keys
async function loadVapidKeys() {
    const resultDiv = document.getElementById('vapid-keys-result');
    const statusDiv = document.getElementById('vapid-keys-status');
    const statusText = document.getElementById('vapid-status-text');
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Loading VAPID keys...';
    }

    try {
        const response = await fetch('/api/push/vapid-keys', {
            method: 'GET'
        });

        const data = await response.json();

        if (data.success) {
            if (data.configured) {
                if (resultDiv) {
                    resultDiv.className = 'result-box success show';
                    resultDiv.textContent = '✅ VAPID keys loaded from database.';
                }
                
                // Fill in the form fields
                const privateKeyField = document.getElementById('vapid-private-key');
                const publicKeyField = document.getElementById('vapid-public-key');
                const emailField = document.getElementById('vapid-email');
                
                if (privateKeyField && data.private_key) {
                    privateKeyField.value = data.private_key;
                }
                if (publicKeyField && data.public_key) {
                    publicKeyField.value = data.public_key;
                }
                if (emailField && data.email) {
                    emailField.value = data.email;
                }
                
                if (statusDiv) statusDiv.style.display = 'block';
                if (statusText) {
                    statusText.textContent = '✅ VAPID keys are configured';
                    statusText.style.color = '#10b981';
                }
            } else {
                if (resultDiv) {
                    resultDiv.className = 'result-box warning show';
                    resultDiv.textContent = '⚠️ No VAPID keys configured. Generate new keys or enter existing ones.';
                }
                
                if (statusDiv) statusDiv.style.display = 'block';
                if (statusText) {
                    statusText.textContent = '❌ VAPID keys not configured';
                    statusText.style.color = '#ef4444';
                }
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (data.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Load VAPID keys error:', error);
    }
}

// Test VAPID keys
async function testVapidKeys() {
    const resultDiv = document.getElementById('vapid-keys-result');
    const privateKeyField = document.getElementById('vapid-private-key');
    const publicKeyField = document.getElementById('vapid-public-key');
    const emailField = document.getElementById('vapid-email');
    
    const privateKey = privateKeyField ? privateKeyField.value.trim() : '';
    const publicKey = publicKeyField ? publicKeyField.value.trim() : '';
    const email = emailField ? emailField.value.trim() : '';
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Testing VAPID keys...';
    }

    if (!privateKey || !publicKey) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Please enter both private and public keys first, or generate new keys.';
        }
        return;
    }

    try {
        const response = await fetch('/api/push/vapid-keys/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                private_key: privateKey,
                public_key: publicKey,
                email: email || 'mailto:tradeiq@example.com'
            })
        });

        const data = await response.json();

        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                let message = '✅ VAPID keys are valid!\n\n';
                message += `✓ Private key format: Valid\n`;
                message += `✓ Public key format: Valid\n`;
                message += `✓ Keys match: ${data.keys_match ? 'Yes' : 'No'}\n`;
                message += `✓ Email format: ${data.email_valid ? 'Valid' : 'Invalid'}\n`;
                if (data.public_key_base64) {
                    message += `\n📋 Public Key (Base64):\n${data.public_key_base64}`;
                }
                resultDiv.innerHTML = '<pre style="white-space: pre-wrap; margin: 0;">' + message + '</pre>';
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                let errorMsg = '❌ VAPID Keys Test Failed:\n\n';
                if (data.details && data.details.length > 0) {
                    errorMsg += data.details.join('\n');
                } else {
                    errorMsg += data.error || 'Unknown error';
                }
                resultDiv.innerHTML = '<pre style="white-space: pre-wrap; margin: 0;">' + errorMsg + '</pre>';
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Test VAPID keys error:', error);
    }
}

// Save VAPID keys
async function saveVapidKeys(event) {
    event.preventDefault();
    
    const resultDiv = document.getElementById('vapid-keys-result');
    const privateKeyField = document.getElementById('vapid-private-key');
    const publicKeyField = document.getElementById('vapid-public-key');
    const emailField = document.getElementById('vapid-email');
    
    const privateKey = privateKeyField ? privateKeyField.value.trim() : '';
    const publicKey = publicKeyField ? publicKeyField.value.trim() : '';
    const publicKeyBase64 = publicKeyField ? (publicKeyField.getAttribute('data-base64-key') || '') : '';
    const email = emailField ? emailField.value.trim() : 'mailto:tradeiq@example.com';
    
    if (!privateKey || !publicKey) {
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Private key and public key are required';
        }
        return;
    }
    
    if (!email.startsWith('mailto:')) {
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Email must start with "mailto:" (e.g., mailto:tradeiq@example.com)';
        }
        return;
    }
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Saving VAPID keys...';
    }

    try {
        const response = await fetch('/api/push/vapid-keys', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                private_key: privateKey,
                public_key: publicKey,
                public_key_base64: publicKeyBase64,  // Include base64 if available from generation
                email: email
            })
        });

        const data = await response.json();

        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.textContent = '✅ VAPID keys saved successfully! You can now subscribe to push notifications.';
            }
            
            // Update status
            const statusDiv = document.getElementById('vapid-keys-status');
            const statusText = document.getElementById('vapid-status-text');
            if (statusDiv) statusDiv.style.display = 'block';
            if (statusText) {
                statusText.textContent = '✅ VAPID keys are configured';
                statusText.style.color = '#10b981';
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (data.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Save VAPID keys error:', error);
    }
}

// Send test notification
async function sendTestNotification() {
    const resultDiv = document.getElementById('notification-result');
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Sending test notification...';
    }

    try {
        const response = await fetch('/api/push/send-test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: 'TradeIQ Test Notification',
                body: 'This is a test notification from TradeIQ! 🎉',
                icon: '/static/icons/icon-192x192.png'
            })
        });

        const data = await response.json();

        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.textContent = '✅ Test notification sent! Check your device.';
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (data.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Send test error:', error);
    }
}

// ==================== Android Native Notifications ====================

// Check Android notifications status
async function checkAndroidNotificationsStatus() {
    const statusEl = document.getElementById('android-notifications-status');
    const statusText = document.getElementById('android-notifications-status-text');
    const checkbox = document.getElementById('android-notifications-enabled');
    
    if (!statusEl || !statusText) return;
    
    try {
        const response = await fetch('/api/android/notifications/status');
        const data = await response.json();
        
        statusEl.style.display = 'block';
        
        if (data.enabled) {
            statusText.textContent = '✅ Android notifications are enabled';
            statusText.style.color = '#10b981';
            if (checkbox) checkbox.checked = true;
        } else {
            statusText.textContent = '❌ Android notifications are disabled';
            statusText.style.color = '#ef4444';
            if (checkbox) checkbox.checked = false;
        }
    } catch (error) {
        statusEl.style.display = 'block';
        statusText.textContent = '⚠️ Unable to check status';
        statusText.style.color = '#f59e0b';
        console.error('[Notifications] Error checking Android notifications status:', error);
    }
}

// Toggle Android notifications
async function toggleAndroidNotifications() {
    const checkbox = document.getElementById('android-notifications-enabled');
    const statusText = document.getElementById('android-notifications-status-text');
    const enabled = checkbox ? checkbox.checked : false;
    
    try {
        const response = await fetch('/api/android/notifications/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (statusText) {
                if (enabled) {
                    statusText.textContent = '✅ Android notifications enabled';
                    statusText.style.color = '#10b981';
                } else {
                    statusText.textContent = '❌ Android notifications disabled';
                    statusText.style.color = '#ef4444';
                }
            }
        } else {
            // Revert checkbox on error
            if (checkbox) checkbox.checked = !enabled;
            alert('Failed to update Android notifications: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        // Revert checkbox on error
        if (checkbox) checkbox.checked = !enabled;
        alert('Error updating Android notifications: ' + error.message);
        console.error('[Notifications] Error toggling Android notifications:', error);
    }
}

// Send Android test notification
async function sendAndroidTestNotification() {
    const resultDiv = document.getElementById('android-notification-result');
    const testBtn = document.getElementById('android-test-btn');
    
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info';
        resultDiv.textContent = 'Sending test Android notification...';
    }
    
    if (testBtn) {
        testBtn.disabled = true;
        testBtn.textContent = 'Sending...';
    }
    
    try {
        const response = await fetch('/api/android/notifications/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: 'TradeIQ Test Notification',
                body: 'This is a test notification from TradeIQ! 🎉',
                channel: 'user_notifications'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.textContent = '✅ Test notification sent! Check your phone\'s notification tray.';
            }
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.textContent = '❌ Error: ' + (data.error || 'Unknown error');
            }
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.textContent = '❌ Error: ' + error.message;
        }
        console.error('[Notifications] Send Android test error:', error);
    } finally {
        if (testBtn) {
            testBtn.disabled = false;
            testBtn.textContent = '📤 Send Test Android Notification';
        }
    }
}

// Check Android notifications status when notifications tab is opened
document.addEventListener('DOMContentLoaded', function() {
    const notificationsTab = document.getElementById('notifications-tab');
    if (notificationsTab) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (notificationsTab.classList.contains('active')) {
                        checkAndroidNotificationsStatus();
                    }
                }
            });
        });
        observer.observe(notificationsTab, { attributes: true });
        
        // Also check immediately if tab is already active
        if (notificationsTab.classList.contains('active')) {
            checkAndroidNotificationsStatus();
        }
    }
    
    // Initial check after a short delay to ensure DOM is ready
    setTimeout(() => {
        checkAndroidNotificationsStatus();
    }, 1000);
});

// Make all functions globally accessible (must be after all function definitions)
window.subscribeToNotifications = subscribeToNotifications;
window.unsubscribeFromNotifications = unsubscribeFromNotifications;
window.generateVapidKeys = generateVapidKeys;
window.loadVapidKeys = loadVapidKeys;
window.testVapidKeys = testVapidKeys;
window.saveVapidKeys = saveVapidKeys;
window.sendTestNotification = sendTestNotification;
window.toggleAndroidNotifications = toggleAndroidNotifications;
window.sendAndroidTestNotification = sendAndroidTestNotification;
window.checkAndroidNotificationsStatus = checkAndroidNotificationsStatus;

console.log('[Notifications] All functions registered globally');
