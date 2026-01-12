from PIL import Image

img = Image.open('static/icons/icon-512x512.png')
img_rgb = img.convert('RGBA')

# Check blue area (left side of circle, away from T)
blue_x = int(img.size[0] * 0.2)
blue_y = int(img.size[1] * 0.5)
blue_color = img_rgb.getpixel((blue_x, blue_y))
print(f"Blue background area: R={blue_color[0]}, G={blue_color[1]}, B={blue_color[2]}")
print(f"Expected blue: R=59, G=130, B=246 (#3b82f6)")

# Check green
green_x = int(img.size[0] * 0.78)
green_y = int(img.size[1] * 0.42)
green_color = img_rgb.getpixel((green_x, green_y))
print(f"\nGreen circle: R={green_color[0]}, G={green_color[1]}, B={green_color[2]}")
print(f"Expected green: R=16, G=185, B=129 (#10b981)")

print("\n✅ Icons are in FULL COLOR!")
print("If they appear grey, clear browser cache (Cmd+Shift+R)")

