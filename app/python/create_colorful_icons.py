#!/usr/bin/env python3
"""
Create colorful icons using PIL/Pillow to ensure full color preservation
"""
from PIL import Image, ImageDraw
import os

os.makedirs('static/icons', exist_ok=True)

def create_colorful_icon(size, output_path):
    # Create transparent image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Blue circular gradient background (simplified as solid blue with highlight)
    center = size // 2
    radius = int(size * 0.47)
    
    # Draw blue circle
    draw.ellipse([center-radius, center-radius, center+radius, center+radius], 
                 fill=(59, 130, 246, 255))  # Blue #3b82f6
    
    # Draw highlight
    highlight_radius = int(radius * 0.7)
    highlight_offset = int(size * 0.1)
    draw.ellipse([center-highlight_radius+highlight_offset, center-highlight_radius+highlight_offset, 
                  center+highlight_radius+highlight_offset, center+highlight_radius+highlight_offset],
                 fill=(96, 165, 250, 100))  # Light blue with transparency
    
    # Draw white T letter
    t_thickness = int(size * 0.12)
    t_horizontal_y = int(size * 0.27)
    t_vertical_x = int(size * 0.44)
    
    # T horizontal bar
    draw.rounded_rectangle([int(size*0.31), t_horizontal_y, int(size*0.69), t_horizontal_y + t_thickness],
                          radius=int(size*0.02), fill=(255, 255, 255, 255))
    
    # T vertical bar
    draw.rounded_rectangle([t_vertical_x, t_horizontal_y + t_thickness, 
                           t_vertical_x + t_thickness, int(size*0.66)],
                          radius=int(size*0.02), fill=(255, 255, 255, 255))
    
    # Draw two green circles (IQ)
    circle_radius = int(size * 0.05)
    circle_x = int(size * 0.78)
    circle_y1 = int(size * 0.42)
    circle_y2 = int(size * 0.54)
    
    # Top green circle (I)
    draw.ellipse([circle_x - circle_radius, circle_y1 - circle_radius,
                  circle_x + circle_radius, circle_y1 + circle_radius],
                 fill=(16, 185, 129, 255))  # Green #10b981
    
    # Bottom green circle (Q)
    draw.ellipse([circle_x - circle_radius, circle_y2 - circle_radius,
                  circle_x + circle_radius, circle_y2 + circle_radius],
                 fill=(16, 185, 129, 255))  # Green #10b981
    
    # Q tail/pointer
    tail_size = int(size * 0.02)
    draw.ellipse([circle_x + circle_radius - tail_size, circle_y2 + circle_radius - tail_size,
                  circle_x + circle_radius + tail_size*2, circle_y2 + circle_radius + tail_size*2],
                 fill=(16, 185, 129, 255))
    
    # Draw white wavy line graph
    line_thickness = max(1, int(size * 0.008))
    start_x = int(size * 0.33)
    start_y = int(size * 0.71)
    points = [
        (start_x, start_y),
        (int(size * 0.37), int(size * 0.67)),
        (int(size * 0.41), int(size * 0.69)),
        (int(size * 0.45), int(size * 0.65)),
        (int(size * 0.49), int(size * 0.67)),
        (int(size * 0.53), int(size * 0.66)),
        (int(size * 0.57), int(size * 0.67))
    ]
    
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=(255, 255, 255, 255), width=line_thickness)
    
    # Draw dots at start and end
    dot_radius = max(1, int(size * 0.006))
    draw.ellipse([points[0][0] - dot_radius, points[0][1] - dot_radius,
                  points[0][0] + dot_radius, points[0][1] + dot_radius],
                 fill=(255, 255, 255, 255))
    draw.ellipse([points[-1][0] - dot_radius, points[-1][1] - dot_radius,
                  points[-1][0] + dot_radius, points[-1][1] + dot_radius],
                 fill=(255, 255, 255, 255))
    
    img.save(output_path, 'PNG')
    print(f"✅ Created {output_path} ({size}x{size})")

# Create all sizes
sizes = {
    'icon-1024x1024.png': 1024,
    'icon-512x512.png': 512,
    'icon-192x192.png': 192,
    'icon-180x180.png': 180,
    'icon-152x152.png': 152,
    'icon-120x120.png': 120,
    'icon-76x76.png': 76,
    'apple-touch-icon.png': 180,
    'favicon-32x32.png': 32,
    'favicon-16x16.png': 16,
}

print("🎨 Creating colorful icons with PIL/Pillow...")
print("")

for filename, size in sizes.items():
    create_colorful_icon(size, f'static/icons/{filename}')

# Create favicon.ico
img32 = Image.open('static/icons/favicon-32x32.png')
img32.save('static/icons/favicon.ico', format='ICO', sizes=[(32, 32)])

print("")
print("✅ All colorful icons created with PIL!")
print("🎨 Icons feature:")
print("   - Blue circular background (full color)")
print("   - White 'T' letter")
print("   - Green circles (IQ) - bright green")
print("   - White wavy line graph")
print("   - Transparent background")
print("   - Full RGB color (not grayscale!)")

