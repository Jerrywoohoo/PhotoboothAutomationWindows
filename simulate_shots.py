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
    """Safely loads a TrueType font on macOS/Windows, or falls back to default font."""
    font_paths = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
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
    Creates a clean simulated 3:2 camera photo (3000 x 2000 px) with:
    1. Plain smooth gradient background (no misleading black bars or text details).
    2. A thin boundary line at the centered 1.48 printable area (2960 x 2000 px, x=20..2979),
       which is visible when inspecting the raw 3:2 file and covered by the frame overlay in preview.
    3. A dead-center circle at (1500, 1000) indicating the shot number (#1, #2, etc.).
    """
    width, height = 3000, 2000
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Pick distinctive background gradient colors per shot
    color_schemes = [
        ((40, 60, 140), (220, 80, 110)),   # Blue to Coral
        ((20, 120, 90), (230, 180, 50)),   # Teal to Gold
        ((90, 40, 130), (50, 180, 230)),   # Purple to Cyan
        ((130, 40, 60), (240, 140, 40)),   # Crimson to Amber
    ]
    c1, c2 = color_schemes[(shot_number - 1) % len(color_schemes)]

    # 1. Plain smooth gradient across full 3000x2000 (3:2) canvas
    for y in range(0, height, 2):
        factor = y / float(height)
        r = int(c1[0] * (1 - factor) + c2[0] * factor)
        g = int(c1[1] * (1 - factor) + c2[1] * factor)
        b = int(c1[2] * (1 - factor) + c2[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b), width=2)

    # 2. Not-so-thick line indicating the real centered 1.48 printable area (2960x2000 inside 3000x2000)
    printable_w = round(height * (148.0 / 100.0))  # 2960 px
    crop_left = (width - printable_w) // 2         # 20 px from left edge
    crop_right = crop_left + printable_w - 1       # 2979 px (20 px from right edge)
    draw.rectangle(
        [crop_left, 2, crop_right, height - 3],
        outline=(255, 255, 255),
        width=5
    )

    # 3. Dead-center circle indicating the shot number
    center_x, center_y = width // 2, height // 2
    r_ring = 380
    draw.ellipse(
        [center_x - r_ring, center_y - r_ring, center_x + r_ring, center_y + r_ring],
        outline=(255, 255, 255), width=6
    )
    r_badge = 330
    draw.ellipse(
        [center_x - r_badge, center_y - r_badge, center_x + r_badge, center_y + r_badge],
        fill=(255, 255, 255), outline=(25, 25, 30), width=8
    )

    font_num = _get_font(220)
    label = f"#{shot_number}"
    bbox = draw.textbbox((0, 0), label, font=font_num)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = center_x - tw // 2 - bbox[0]
    ty = center_y - th // 2 - bbox[1]
    draw.text((tx, ty), label, fill=(10, 110, 240), font=font_num)

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
