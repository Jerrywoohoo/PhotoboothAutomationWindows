"""
ui_windows.py
Windows native lightweight dialog interface.
Zero external dependencies required; uses Tkinter dialog / Windows shell preview.
"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

def prompt_photo_print_native(image_path, printer_name="Canon SELPHY CP1500"):
    """
    1. Opens Windows photo preview in background.
    2. Displays a dialog asking whether to print (1 copy, 2 copies) or skip.
    3. Returns (should_print, copies, rotation)
    """
    filename = os.path.basename(image_path)
    
    # 1. Open photo in default Windows viewer
    try:
        os.startfile(image_path)
    except Exception:
        try:
            subprocess.Popen(["rundll32.exe", "shimgvw.dll,ImageView_Fullscreen", os.path.abspath(image_path)])
        except Exception:
            pass

    # 2. Tkinter prompt dialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    res = messagebox.askyesnocancel(
        "Photo Booth: New Photo Captured",
        f"New photo detected: {filename}\nPrinter: {printer_name}\n\n"
        f"• Click 'Yes' to Print 1 Copy\n"
        f"• Click 'No' to Print 2 Copies\n"
        f"• Click 'Cancel' to Skip printing",
        parent=root
    )
    root.destroy()

    if res is True:
        return True, 1, 0
    elif res is False:
        return True, 2, 0
    else:
        return False, 0, 0

