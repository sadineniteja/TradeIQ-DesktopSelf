#!/usr/bin/env python3
"""
Generate VAPID keys for PWA push notifications
Based on working iOS example: https://github.com/andreinwald/webpush-ios-example
"""

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64

def generate_vapid_keys(verbose=True):
    """Generate VAPID public and private keys"""
    if verbose:
        print("Generating VAPID keys for push notifications...")
        print()
    
    # Generate a new elliptic curve private key
    private_key = ec.generate_private_key(
        ec.SECP256R1(),  # P-256 curve, recommended for WebPush
        default_backend()
    )
    
    # Get the public key
    public_key = private_key.public_key()
    
    # Serialize private key to PEM format
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Serialize public key to PEM format
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    # Serialize public key to uncompressed point bytes (for base64url encoding)
    # Get the public numbers (x, y coordinates)
    public_numbers = public_key.public_numbers()
    
    # P-256 requires exactly 32 bytes for X and Y coordinates
    # Pad to exactly 32 bytes if needed (to_bytes will pad with leading zeros)
    x_bytes = public_numbers.x.to_bytes(32, 'big')
    y_bytes = public_numbers.y.to_bytes(32, 'big')
    public_key_bytes_raw = b'\x04' + x_bytes + y_bytes
    
    # Keep the 0x04 prefix - browser expects full 65 bytes (0x04 + 32 + 32)
    public_key_base64 = base64.urlsafe_b64encode(public_key_bytes_raw).decode('utf-8').rstrip('=')
    
    if verbose:
        print("=" * 60)
        print("VAPID Keys Generated Successfully!")
        print("=" * 60)
        print()
        print("PRIVATE KEY (keep this secret!):")
        print("-" * 60)
        print(private_key_pem)
        print()
        print("PUBLIC KEY (PEM format):")
        print("-" * 60)
        print(public_key_pem)
        print()
        print("PUBLIC KEY (Base64 URL-safe format for web push):")
        print("-" * 60)
        print(public_key_base64)
        print()
        print("=" * 60)
        print("Next Steps:")
        print("=" * 60)
        print("1. Copy the PRIVATE KEY and save it securely")
        print("2. Copy the PUBLIC KEY (Base64) and use it in your app")
        print("3. Go to TradeIQ Settings → Push Notifications")
        print("4. Configure VAPID keys in the backend")
        print()
        print("⚠️  IMPORTANT: Keep the private key secret! Never commit it to git.")
        print()
    
    return {
        'private_key': private_key_pem,
        'public_key_pem': public_key_pem,
        'public_key_base64': public_key_base64
    }

if __name__ == '__main__':
    generate_vapid_keys()
