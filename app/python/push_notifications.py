"""
Push Notification Manager for TradeIQ PWA
Handles subscription storage and sending push notifications
"""

import json
import logging
from typing import Optional, Dict, Any
from database import Database
import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

logger = logging.getLogger(__name__)


class PushNotificationManager:
    def __init__(self, db: Database):
        self.db = db
        self.vapid_private_key = None
        self.vapid_public_key = None
        self.vapid_email = None
        self._load_vapid_keys()

    def _load_vapid_keys(self):
        """Load VAPID keys from database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT setting_value FROM settings 
                WHERE setting_key = 'vapid_private_key'
            """)
            row = cursor.fetchone()
            if row:
                self.vapid_private_key = row[0]

            cursor.execute("""
                SELECT setting_value FROM settings 
                WHERE setting_key = 'vapid_public_key'
            """)
            row = cursor.fetchone()
            if row:
                self.vapid_public_key = row[0]

            cursor.execute("""
                SELECT setting_value FROM settings 
                WHERE setting_key = 'vapid_email'
            """)
            row = cursor.fetchone()
            if row:
                self.vapid_email = row[0]
            conn.close()
        except Exception as e:
            logger.error(f"Error loading VAPID keys: {e}")

    def save_vapid_keys(self, private_key: str, public_key: str, email: str, public_key_base64: Optional[str] = None) -> bool:
        """Save VAPID keys to database
        
        Args:
            private_key: Private key in PEM format
            public_key: Public key in PEM format
            email: Contact email (mailto: format)
            public_key_base64: Optional - Public key in base64 URL-safe format (if not provided, will be converted from PEM)
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Helper function to save a setting
            def save_setting(key, value):
                cursor.execute("""
                    UPDATE settings 
                    SET setting_value = ?, updated_at = datetime('now')
                    WHERE setting_key = ?
                """, (value, key))
                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO settings (setting_key, setting_value, updated_at)
                        VALUES (?, ?, datetime('now'))
                    """, (key, value))
            
            # Convert PEM to base64 if not provided
            if not public_key_base64 and public_key.startswith('-----BEGIN'):
                try:
                    public_key_obj = serialization.load_pem_public_key(
                        public_key.encode('utf-8'),
                        backend=default_backend()
                    )
                    from cryptography.hazmat.primitives.asymmetric import ec
                    if isinstance(public_key_obj, ec.EllipticCurvePublicKey):
                        public_numbers = public_key_obj.public_numbers()
                        # P-256 requires exactly 32 bytes for X and Y coordinates
                        x_bytes = public_numbers.x.to_bytes(32, 'big')
                        y_bytes = public_numbers.y.to_bytes(32, 'big')
                        public_key_bytes_raw = b'\x04' + x_bytes + y_bytes
                        # Keep the 0x04 prefix - browser expects full 65 bytes
                        public_key_base64 = base64.urlsafe_b64encode(public_key_bytes_raw).decode('utf-8').rstrip('=')
                except Exception as e:
                    logger.warning(f"Could not convert PEM to base64, will convert on retrieval: {e}")
            
            # Save all keys
            save_setting('vapid_private_key', private_key)
            save_setting('vapid_public_key', public_key)
            if public_key_base64:
                save_setting('vapid_public_key_base64', public_key_base64)
            save_setting('vapid_email', email)
            
            conn.commit()
            conn.close()
            
            # Update instance variables
            self.vapid_private_key = private_key
            self.vapid_public_key = public_key
            self.vapid_email = email
            
            logger.info("VAPID keys saved successfully")
            return True
        except Exception as e:
            import traceback
            logger.error(f"Error saving VAPID keys: {e}")
            traceback.print_exc()
            return False

    def get_vapid_public_key(self) -> Optional[str]:
        """Get VAPID public key in base64 URL-safe format for web push"""
        if not self.vapid_public_key:
            return None
        
        # First, try to get the stored base64 format
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT setting_value FROM settings 
                WHERE setting_key = 'vapid_public_key_base64'
            """)
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception as e:
            logger.debug(f"Could not load base64 format, will convert: {e}")
        
        # If it's already in base64 format (no BEGIN/END markers), return as is
        if not self.vapid_public_key.startswith('-----BEGIN'):
            return self.vapid_public_key
        
        # Convert PEM format to base64 URL-safe format
        try:
            public_key_obj = serialization.load_pem_public_key(
                self.vapid_public_key.encode('utf-8'),
                backend=default_backend()
            )
            # Get the public numbers (x, y coordinates)
            from cryptography.hazmat.primitives.asymmetric import ec
            if isinstance(public_key_obj, ec.EllipticCurvePublicKey):
                public_numbers = public_key_obj.public_numbers()
                
                # P-256 requires exactly 32 bytes for X and Y coordinates
                x_bytes = public_numbers.x.to_bytes(32, 'big')
                y_bytes = public_numbers.y.to_bytes(32, 'big')
                public_key_bytes_raw = b'\x04' + x_bytes + y_bytes
                
                # Keep the 0x04 prefix - browser expects full 65 bytes (0x04 + 32 + 32)
                public_key_base64 = base64.urlsafe_b64encode(public_key_bytes_raw).decode('utf-8').rstrip('=')
                return public_key_base64
            else:
                logger.error("VAPID public key is not an elliptic curve key")
                return None
        except Exception as e:
            logger.error(f"Error converting VAPID public key from PEM to Base64: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_subscription(self, subscription_data: Dict[str, Any]) -> bool:
        """Save push subscription to database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Extract endpoint and keys
            endpoint = subscription_data.get('endpoint', '')
            p256dh = subscription_data.get('keys', {}).get('p256dh', '')
            auth = subscription_data.get('keys', {}).get('auth', '')
            
            # Save subscription
            cursor.execute("""
                INSERT OR REPLACE INTO push_subscriptions 
                (endpoint, p256dh, auth, subscription_data, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (endpoint, p256dh, auth, json.dumps(subscription_data)))
            
            conn.commit()
            conn.close()
            logger.info(f"Push subscription saved: {endpoint[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
            return False

    def remove_subscription(self, endpoint: str) -> bool:
        """Remove push subscription from database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM push_subscriptions WHERE endpoint = ?
            """, (endpoint,))
            conn.commit()
            conn.close()
            logger.info(f"Push subscription removed: {endpoint[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error removing subscription: {e}")
            return False

    def get_all_subscriptions(self) -> list:
        """Get all push subscriptions"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT subscription_data FROM push_subscriptions
            """)
            rows = cursor.fetchall()
            subscriptions = []
            for row in rows:
                try:
                    sub_data = json.loads(row[0])
                    subscriptions.append(sub_data)
                except:
                    pass
            conn.close()
            return subscriptions
        except Exception as e:
            logger.error(f"Error getting subscriptions: {e}")
            return []

    def send_notification(self, subscription_data: Dict[str, Any], 
                         title: str, body: str, **options) -> bool:
        """Send push notification to a single subscription"""
        if not self.vapid_private_key or not self.vapid_public_key:
            logger.error("VAPID keys not configured")
            return False

        try:
            # Load the private key from PEM format
            # pywebpush's Vapid.from_string() expects base64url-encoded DER, not PEM
            try:
                private_key_obj = serialization.load_pem_private_key(
                    self.vapid_private_key.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
            except Exception as e:
                logger.error(f"Error loading private key from PEM: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # Convert to DER format, then to base64url (what py_vapid expects)
            private_key_der = private_key_obj.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Encode DER bytes to base64url (what Vapid.from_string expects)
            # Remove padding as base64url typically doesn't use it
            private_key_base64url = base64.urlsafe_b64encode(private_key_der).decode('utf-8').rstrip('=')

            vapid_claims = {
                "sub": self.vapid_email or "mailto:tradeiq@example.com"
            }

            notification_data = {
                "title": title,
                "body": body,
                "icon": options.get('icon', '/static/icons/icon-192x192.png'),
                "badge": options.get('badge', '/static/icons/icon-192x192.png'),
                "data": options.get('data', {}),
                "tag": options.get('tag'),
                "requireInteraction": options.get('requireInteraction', False)
            }

            if options.get('image'):
                notification_data['image'] = options.get('image')

            # Pass the base64url-encoded DER format to pywebpush
            # This is what Vapid.from_string() expects internally
            pywebpush.webpush(
                subscription_info=subscription_data,
                data=json.dumps(notification_data),
                vapid_private_key=private_key_base64url,  # Pass base64url-encoded DER
                vapid_claims=vapid_claims
            )
            
            logger.info(f"Push notification sent: {title}")
            return True
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error sending push notification: {e}")
            
            # Check if subscription is expired/unregistered (410 Gone)
            # If so, remove it from the database to avoid future delays
            if "410" in error_str or "Gone" in error_str or "Unregistered" in error_str:
                endpoint = subscription_data.get("endpoint") if isinstance(subscription_data, dict) else None
                if endpoint:
                    logger.warning(f"Removing expired subscription: {endpoint[:50]}...")
                    self.remove_subscription(endpoint)
            
            import traceback
            traceback.print_exc()
            return False

    def send_notification_to_all(self, title: str, body: str, **options) -> Dict[str, int]:
        """Send push notification to all subscribers"""
        subscriptions = self.get_all_subscriptions()
        results = {"success": 0, "failed": 0}
        
        for subscription in subscriptions:
            if self.send_notification(subscription, title, body, **options):
                results["success"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"Sent notifications: {results['success']} success, {results['failed']} failed")
        return results
