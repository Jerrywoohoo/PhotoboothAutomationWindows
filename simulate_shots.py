"""
simulate_shots.py
Generates synthetic photo booth camera shots (3:2 ratio) with procedural patterns,
gradients, noise, and clear labels. Simulates Sony Imaging Edge tethered capture.
"""

import os
import sys
import time
import random
from PIL import Image, ImageDraw, ImageFont


def _get_font(size):
    """Safely loads a TrueType font on macOS, or falls back to default font."""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def create_synthetic_photo(output_path, shot_number=1, total_shots=3):
    """
    Creates a simulated 3:2 camera photo (3000 x 2000 px) with colorful gradient,
    subtle texture/noise, frame border, and clear text labels.
    """
    width, height = 3000, 2000
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Pick distinctive background colors per shot
    color_schemes = [
        ((40, 60, 140), (220, 80, 110)),   # Blue to Coral
        ((20, 120, 90), (230, 180, 50)),   # Teal to Gold
        ((90, 40, 130), (50, 180, 230)),   # Purple to Cyan
        ((130, 40, 60), (240, 140, 40)),   # Crimson to Amber
    ]
    c1, c2 = color_schemes[(shot_number - 1) % len(color_schemes)]

    # Draw smooth gradient
    for y in range(0, height, 2):
        factor = y / float(height)
        r = int(c1[0] * (1 - factor) + c2[0] * factor)
        g = int(c1[1] * (1 - factor) + c2[1] * factor)
        b = int(c1[2] * (1 - factor) + c2[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b), width=2)

    # Decorative frame
    margin = 80
    draw.rectangle([margin, margin, width - margin, height - margin], outline=(255, 255, 255), width=16)

    # Fonts (sized generously for crisp legibility at both thumbnail and full-screen zoom)
    font_title = _get_font(96)
    font_sub = _get_font(62)
    font_badge = _get_font(150)

    # Header and info text (All pure ASCII to avoid any font encoding bugs)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Subtle dark header backing bar for maximum contrast
    draw.rectangle([margin + 8, margin + 8, width - margin - 8, margin + 280], fill=(18, 18, 24))
    draw.text((margin + 55, margin + 45), f"PHOTO BOOTH SHOT #{shot_number} OF {total_shots}", fill=(255, 255, 255), font=font_title)
    draw.text((margin + 55, margin + 175), f"Captured: {timestamp}  |  3000x2000 HD (3:2 Ratio)", fill=(200, 220, 255), font=font_sub)

    # Bottom info bar
    draw.rectangle([margin + 8, height - margin - 140, width - margin - 8, height - margin - 8], fill=(18, 18, 24))
    draw.text((margin + 55, height - margin - 105), "Canon SELPHY CP1500  |  100x148 mm Postcard Fullbleed (Lossless)", fill=(255, 255, 255), font=font_sub)

    # Central crisp target & resolution rings
    center_x, center_y = width // 2, height // 2 + 40
    for r_ring in (440, 410):
        draw.ellipse(
            [center_x - r_ring, center_y - r_ring, center_x + r_ring, center_y + r_ring],
            outline=(255, 255, 255), width=8
        )
    r_badge = 370
    draw.ellipse(
        [center_x - r_badge, center_y - r_badge, center_x + r_badge, center_y + r_badge],
        fill=(255, 255, 255), outline=(25, 25, 30), width=10
    )
    draw.text((center_x - 210, center_y - 165), "SHOT", fill=(20, 20, 25), font=font_badge)
    draw.text((center_x - 115, center_y + 10), f"#{shot_number}", fill=(10, 110, 240), font=font_badge)

    img.save(output_path, "JPEG", quality=96, subsampling=0)
    return output_path


def simulate_camera_session(target_folder, count=3, delay=0.8):
    """
    Simulates taking 'count' photos on camera with delay in between,
    saving directly into the watched folder.
    """
    os.makedirs(target_folder, exist_ok=True)
    created_files = []
    print(f"\n📸 Simulating {count} camera shots saved to: {target_folder}")

    session_id = int(time.time()) % 10000
    for i in range(1, count + 1):
        filename = f"DSC_TEST_{session_id}_{i:02d}.JPG"
        file_path = os.path.join(target_folder, filename)
        create_synthetic_photo(file_path, shot_number=i, total_shots=count)
        created_files.append(file_path)
        print(f" -> Shot #{i} saved: {filename}")
        if i < count:
            time.sleep(delay)

    print("✅ All simulated shots generated!\n")
    return created_files


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Simulate camera shots for Photo Booth testing")
    parser.add_argument("folder", nargs="?", default=os.path.expanduser("~/Pictures"), help="Target folder (default: ~/Pictures)")
    parser.add_argument("--count", "-c", type=int, default=3, help="Number of photos to generate (default: 3)")
    parser.add_argument("--delay", "-d", type=float, default=0.8, help="Delay between shots in seconds (default: 0.8)")
    args = parser.parse_args()

    simulate_camera_session(args.folder, count=args.count, delay=args.delay)
