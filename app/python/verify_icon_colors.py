#!/usr/bin/env python3
from PIL import Image
import os

# Check icons to verify colors
icons_to_check = ['icon-512x512.png', 'icon-192x192.png']

for icon_file in icons_to_check:
    path = f'static/icons/{icon_file}'
    if os.path.exists(path):
        img = Image.open(path)
        print(f"\n{icon_file}:")
        print(f"  Mode: {img.mode}")
        
        # Convert to RGB for color checking
        if img.mode == 'P':
            img_rgb = img.convert('RGBA')
        else:
            img_rgb = img
        
        # Sample center pixel (should be blue)
        center = (img.size[0]//2, img.size[1]//2)
        center_color = img_rgb.getpixel(center)
        print(f"  Center (blue): R={center_color[0]}, G={center_color[1]}, B={center_color[2]}")
        
        # Sample green circle area
        green_x = int(img.size[0] * 0.78)
        green_y = int(img.size[1] * 0.42)
        if green_x < img.size[0] and green_y < img.size[1]:
            green_color = img_rgb.getpixel((green_x, green_y))
            print(f"  Green circle: R={green_color[0]}, G={green_color[1]}, B={green_color[2]}")
        
        # Sample white T area
        white_x = int(img.size[0] * 0.5)
        white_y = int(img.size[1] * 0.3)
        white_color = img_rgb.getpixel((white_x, white_y))
        print(f"  White T: R={white_color[0]}, G={white_color[1]}, B={white_color[2]}")

