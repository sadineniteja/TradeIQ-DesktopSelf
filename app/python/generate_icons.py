#!/usr/bin/env python3
"""
Generate premium glossy app icons from SVG with solid backgrounds
"""
import cairosvg
import os

# Create icons directory if it doesn't exist
os.makedirs('static/icons', exist_ok=True)

# SVG file path
svg_file = 'static/icons/tradeiq-app-icon-premium.svg'

# Required sizes for different platforms
sizes = {
    'icon-192x192.png': 192,
    'icon-512x512.png': 512,
    'icon-180x180.png': 180,  # iOS
    'icon-152x152.png': 152,  # iPad
    'icon-120x120.png': 120,  # iPhone
    'icon-76x76.png': 76,     # iPad (small)
    'icon-1024x1024.png': 1024,  # App Store
    'favicon-32x32.png': 32,
    'favicon-16x16.png': 16,
    'apple-touch-icon.png': 180,  # iOS
}

print("🎨 Generating premium glossy icons with solid backgrounds...")
print("")

for filename, size in sizes.items():
    try:
        # Convert SVG to PNG with solid background
        # cairosvg handles gradients and colors properly
        png_data = cairosvg.svg2png(
            url=svg_file,
            output_width=size,
            output_height=size,
            background_color='#1e3a8a'  # Solid blue background
        )
        
        # Save to file
        output_path = f'static/icons/{filename}'
        with open(output_path, 'wb') as f:
            f.write(png_data)
        
        file_size = len(png_data) / 1024
        print(f"✅ Created {filename} ({size}x{size}) - {file_size:.1f}KB")
    except Exception as e:
        print(f"❌ Error creating {filename}: {e}")

print("")
print("✅ All premium glossy icons generated successfully!")
print("📱 Icons feature:")
print("   - Solid blue gradient background (no transparency)")
print("   - Premium gold glossy 'T' letter")
print("   - Emerald green 'IQ' spheres")
print("   - Professional glossy finish")

