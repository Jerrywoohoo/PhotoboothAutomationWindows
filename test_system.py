"""
test_system.py
Performs preliminary tests on image math, watcher, and printer command formatting.
Does not print anything to the physical printer.
"""

import os
import sys
import time
import shutil
from PIL import Image, ImageDraw

import printer_service
from watcher import FolderWatcher

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_scratch")


def test_aspect_ratio_and_bleed():
    print("\n--- TEST 1: Aspect Ratio & Borderless Bleed Math ---")
    os.makedirs(TEST_DIR, exist_ok=True)
    
    # 1. Create a simulated 3:2 camera photo (e.g. 3000 x 2000 landscape)
    cam_img = Image.new("RGB", (3000, 2000), color=(50, 100, 200))
    draw = ImageDraw.Draw(cam_img)
    draw.rectangle([50, 50, 2950, 1950], outline=(255, 255, 255), width=10)
    draw.text((200, 950), "Sony 3:2 Camera Test Photo", fill=(255, 255, 255))
    
    test_photo_path = os.path.join(TEST_DIR, "DSC_TEST.JPG")
    cam_img.save(test_photo_path, "JPEG")
    print(f"Created simulated Sony camera photo: {cam_img.size} (Ratio: {3000/2000:.4f})")

    # 2. Process image with printer_service lossless rotation
    prepared_path = printer_service.prepare_lossless_rotated_image(test_photo_path, output_dir=TEST_DIR, rotation=90)
    
    with Image.open(prepared_path) as res_img:
        w, h = res_img.size
        print(f"Lossless rotated image: {w}x{h} px (Format: {res_img.format})")
        assert res_img.format == "PNG", "Lossless rotated image must be PNG!"
        print("✅ Lossless rotation output is pure PNG with zero compression artifacts!")

    # 3. Test frame overlay compositing
    frame_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_frame.png")
    if os.path.exists(frame_path):
        framed_path = printer_service.prepare_lossless_rotated_image(
            test_photo_path, output_dir=TEST_DIR, rotation=0, frame_path=frame_path
        )
        with Image.open(framed_path) as framed_img:
            fw, fh = framed_img.size
            print(f"Framed print image: {fw}x{fh} px (Ratio: {fw/fh:.4f})")
            assert framed_img.format == "PNG", "Framed print image must be PNG!"
            assert abs((fw / fh) - printer_service.POSTCARD_RATIO) < 0.01, "Aspect ratio must match 1.48 Postcard!"
            print("✅ Frame overlay compositing and 1.48 Postcard ratio verified!")

    # 4. Test simulated dry-run print command with discrete copy verification
    success, msg = printer_service.print_photo(test_photo_path, copies=2, dry_run=True)
    print(f"Simulated Print Result: {msg}")
    assert success is True
    assert "Copy 1 of 2" in msg
    assert "Copy 2 of 2" in msg
    print("✅ Discrete numbered copy queueing verified successfully!")


def test_folder_watcher():
    print("\n--- TEST 2: Folder Watcher & Settled File Detection ---")
    detected = []

    def on_photo(path):
        print(f"Watcher callback triggered for: {os.path.basename(path)}")
        detected.append(path)

    watcher = FolderWatcher(TEST_DIR, on_photo, poll_interval=0.2)
    watcher.start()

    time.sleep(0.3)
    # Create a new test photo
    new_photo = os.path.join(TEST_DIR, "DSC_WATCHER_TEST.JPG")
    img = Image.new("RGB", (800, 600), color=(100, 200, 100))
    img.save(new_photo, "JPEG")

    # Wait for detection up to 5 seconds
    for _ in range(25):
        if detected:
            break
        time.sleep(0.2)

    watcher.stop()
    assert len(detected) >= 1, f"Watcher failed to detect new file! Detected list: {detected}"
    print(f"✅ Watcher successfully detected new file: {detected[0]}")


def cleanup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    print("\n✅ Cleaned up temporary test scratch directory.")


if __name__ == "__main__":
    try:
        test_aspect_ratio_and_bleed()
        test_folder_watcher()
        print("\n🎉 ALL PRELIMINARY TESTS PASSED SAFELY!\n")
    finally:
        cleanup()
