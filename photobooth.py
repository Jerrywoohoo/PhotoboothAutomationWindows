#!/usr/bin/env python3
"""
photobooth.py (Windows Edition)
Main launcher for Canon SELPHY CP1500 Photo Booth Automation on Windows.
Supports both dedicated Kiosk GUI and Native Dialog modes.
"""

import argparse
import os
import sys
import json
import time

import printer_service
from watcher import FolderWatcher
import ui_windows
import ui_booth

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "watch_folder": os.path.expanduser("~/Pictures"),
        "dry_run": True,
        "default_copies": 1,
        "mode": "gui"
    }


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def run_dialog_mode(watch_folder, dry_run=False, printer_name="Canon SELPHY CP1500"):
    print("\n" + "=" * 60)
    print("📸 PHOTO BOOTH AUTOMATION (Windows Native Dialog Mode)")
    print(f"📁 Watching Folder: {watch_folder}")
    print(f"🖨️ Printer:        {printer_name}")
    print(f"🧪 Test Mode:      {'ENABLED (Dry Run)' if dry_run else 'DISABLED (Real Printing)'}")
    print("=" * 60)
    print("Waiting for photos from Sony Imaging Edge... (Press Ctrl+C to stop)\n")

    def on_photo(photo_path):
        fname = os.path.basename(photo_path)
        print(f"\n[NEW PHOTO DETECTED] {fname}")
        should_print, copies, rotation = ui_windows.prompt_photo_print_native(photo_path, printer_name)
        if should_print:
            print(f"-> Printing {copies} copy/copies to {printer_name}...")
            success, msg = printer_service.print_photo(
                photo_path, copies=copies, printer_name=printer_name, dry_run=dry_run, rotation=rotation
            )
            if success:
                print(f"-> ✅ {msg}")
            else:
                print(f"-> ❌ {msg}")
        else:
            print("-> ⏭️ Skipped printing.")

    watcher = FolderWatcher(watch_folder, on_photo)
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Photo Booth Automation...")
        watcher.stop()


def main():
    cfg = load_config()

    parser = argparse.ArgumentParser(description="Canon SELPHY CP1500 Photo Booth Print Automation (Windows)")
    parser.add_argument("-f", "--folder", default=cfg.get("watch_folder"), help="Directory to watch for incoming photos")
    parser.add_argument("--mode", choices=["gui", "dialog"], default=cfg.get("mode", "gui"), help="UI mode: 'gui' (Kiosk window) or 'dialog' (Lightweight popup dialog)")
    parser.add_argument("--dry-run", action="store_true", default=cfg.get("dry_run", False), help="Simulate print jobs without using paper/ink")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Enable actual physical printing")
    parser.add_argument("--printer", default=printer_service.PRINTER_NAME, help="Windows printer name")
    parser.add_argument("--status", action="store_true", help="Check printer status and exit")

    args = parser.parse_args()

    # Printer status check
    if args.status:
        status, msg = printer_service.check_printer_status(args.printer)
        print(f"Printer '{args.printer}' status: {status} ({msg})")
        return

    # Update config
    cfg["watch_folder"] = args.folder if args.folder.startswith("~") else os.path.abspath(args.folder)
    cfg["mode"] = args.mode
    cfg["dry_run"] = args.dry_run
    save_config(cfg)

    if args.mode == "dialog":
        run_dialog_mode(args.folder, dry_run=args.dry_run, printer_name=args.printer)
    else:
        # Launch Tkinter GUI
        ui_booth.launch_gui(watch_folder=args.folder, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

