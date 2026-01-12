# TradeIQ Premium Icons

## Premium Logo Design

The TradeIQ logo features a premium, million-dollar app aesthetic with:

- **Gold gradient "T" letter** - Represents premium trading and wealth
- **Emerald green "IQ" spheres** - Symbolizes intelligence and analytics
- **3D depth effects** - Multiple shadow layers and highlights for premium appearance
- **Trading chart element** - Shows the app's core functionality
- **Professional color scheme** - Blue sphere background with gold and emerald accents

## Icon Files

All icons are generated from `tradeiq-logo-premium.svg`:

### PWA Icons (Required)
- `icon-192x192.png` - 192x192 (PWA standard)
- `icon-512x512.png` - 512x512 (PWA standard)

### iOS Icons
- `icon-180x180.png` - 180x180 (iPhone)
- `icon-152x152.png` - 152x152 (iPad)
- `icon-120x120.png` - 120x120 (iPhone small)
- `icon-76x76.png` - 76x76 (iPad small)
- `apple-touch-icon.png` - 180x180 (iOS home screen)

### App Store
- `icon-1024x1024.png` - 1024x1024 (App Store requirement)

### Web Favicons
- `favicon.ico` - 32x32 (Browser favicon)
- `favicon-32x32.png` - 32x32 (Modern browsers)
- `favicon-16x16.png` - 16x16 (Legacy browsers)

## Source Files

- `tradeiq-logo-premium.svg` - Premium 3D-style logo (source)
- `tradeiq-logo.svg` - Modern flat 3D style (alternative)
- `tradeiq-logo-3d-style.svg` - Enhanced 3D style (alternative)

## Usage

All icons are automatically configured in:
- `manifest.json` - PWA manifest
- `templates/index.html` - HTML head section

## Regenerating Icons

To regenerate all icons from the SVG source:

```bash
# Using ImageMagick
magick static/icons/tradeiq-logo-premium.svg -resize 192x192 static/icons/icon-192x192.png
magick static/icons/tradeiq-logo-premium.svg -resize 512x512 static/icons/icon-512x512.png
# ... repeat for other sizes
```

## Design Notes

The premium logo design emphasizes:
- **Luxury** - Gold gradients and metallic effects
- **Intelligence** - Emerald green IQ spheres
- **Professionalism** - Clean 3D effects and depth
- **Trading Focus** - Chart elements and financial aesthetics
