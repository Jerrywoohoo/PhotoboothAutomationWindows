"""
interactive_test.py
Interactive end-to-end test script:
1. Generates 3 synthetic camera photos with distinct colors, noise patterns, and timestamps.
2. Launches the Photo Booth UI.
3. Lets you select, choose copies, and queue print jobs.
4. Allows you to open macOS Print Center to see the queued jobs with your own eyes.
5. Provides a clean command to clear the test queue afterwards.
"""

import os
import sys
import time
import subprocess
import shutil

import simulate_shots
import printer_service
import ui_booth

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interactive_test_photos")


def main():
    print("\n" + "=" * 65)
    print("🧪 PHOTO BOOTH INTERACTIVE TEST")
    print("=" * 65)
    print("This test will:")
    print(" 1. Create a test directory with 3 simulated Sony camera photos.")
    print(" 2. Launch the Photo Booth GUI.")
    print(" 3. Let you select photos, adjust copies, and click Print.")
    print(" 4. Queue the jobs into macOS Print Center (`Canon_SELPHY_CP1500`).")
    print(" 5. You can inspect the queue with your eyes in macOS Print Center!")
    print("=" * 65 + "\n")

    os.makedirs(TEST_DIR, exist_ok=True)

    # 1. Pre-generate 3 test photos
    print("📸 Generating 3 synthetic camera shots...")
    simulate_shots.simulate_camera_session(TEST_DIR, count=3, delay=0.1)

    print("\n🚀 Launching Photo Booth Station...")
    print("💡 TIPS FOR TESTING:")
    print("  • Notice the 3 photos are displayed side-by-side on screen.")
    print("  • Notice the buttons are crisp, high-contrast, and easy to read.")
    print("  • Click any card to select/deselect it, or adjust copies with [− / +].")
    print("  • Click '🖨️ Print Selected Photos' (or uncheck Test Mode to queue to Mac spool).")
    print("  • Click '📋 Mac Print Queue' in the top bar to inspect macOS Print Center!")
    print("  • Click '✅ Next Group / Clear Feed' to clear the active batch for the next guest.")
    print("  • Click '📸 Simulate 3 Shots' in the top bar to trigger a new incoming batch anytime!")
    print("=" * 65 + "\n")

    # Launch GUI with dry_run=False so jobs can enter the macOS print queue if user desires,
    # or start with dry_run checked for safety!
    ui_booth.launch_gui(watch_folder=TEST_DIR, dry_run=False)

    print("\n📋 Current macOS Print Queue status:")
    print(printer_service.get_print_queue_status())

    print("\n🧹 Cleaning up test photos...")
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    print("✅ Interactive test completed.\n")


if __name__ == "__main__":
    main()
