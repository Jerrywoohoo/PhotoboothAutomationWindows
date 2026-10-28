# 📸 Photo Booth Print Automation for Canon SELPHY CP1500 (Windows Edition)

Automated, lossless, borderless photo printing workflow with multi-template `.png` frame overlays for Sony Imaging Edge + Canon SELPHY CP1500 on Microsoft Windows (Windows 10 & 11).

---

## 🚀 How to Use on Windows (Quick Start)

### Option 1: 🌟 One-Click Launcher (Easiest - Zero Setup!)
1. Download or clone this folder.
2. **Double-click `run.bat`** in File Explorer!
   - On the very first launch, it automatically sets up an isolated environment and installs `Pillow`.
   - On future launches, it boots immediately in 1 second.
   *(Note: If Windows SmartScreen prompts "Windows protected your PC", click **More info** → **Run anyway**).*

---

### Option 2: Run via Command Prompt / PowerShell
```cmd
.\run.bat
:: Or run directly with Python:
python photobooth.py
```
- Monitors your Sony Imaging Edge save folder (defaults to your Windows `Pictures` folder).
- Incoming camera photos appear side-by-side automatically.
- Click **"🖨️ Print Selected Photos"** (or press `Enter`) to print.
- Click **"✅ Next Group / Clear Feed"** (or press `c`) to archive the session and clear the screen for the next guest.

#### Option C: Interactive Test Mode (Pre-loads 3 Simulated Shots)
```cmd
python interactive_test.py
```
- Generates 3 clean **3:2 (`3000×2000 px`)** gradient test photos with a centered shot number circle and a thin **`1.48` printable area boundary line** (`2960×2000 px`) so you can verify exact center-cropping.
- Launches the UI in **Test Mode** so you can test frame templates, selection, and copies safely without using paper.

---

## 🎯 The Problem This Solves

When printing manually on Windows or editing in Canva:
1. **Aspect Ratio Mismatch:** Sony Alpha cameras shoot at **3:2 (1.50)**. Canon SELPHY paper is Japanese Postcard (Hagaki / KP-108IN) at **100 x 148 mm (1.48)**.
2. **Margin & Scaling Issues:** Windows Photo Viewer and Print Photos wizard often add white borders or require manual fit-to-frame tweaking.
3. **Manual Canva Frame Overlays:** Manually importing camera shots into Canva, overlaying transparent `.png` frames, exporting PDFs, and printing takes too long during live events.

### How This Script Solves It Automatically:
- **Native Windows Printing:** Uses high-fidelity GDI+ / .NET `PrintDocument` borderless printing with zero margins and automatic 100x148 mm (`1.48`) center-crop bleed.
- **Multi-Template Photo Frame Overlays:** Point the app to any folder of transparent `.png` frames (`1.48` ratio). The app center-crops `3:2` camera shots to `1.48`, composites the chosen frame losslessly at 300 DPI, and previews it live on every card and in the full-screen lightbox.
- **Zero Lossy Re-encoding:** Spools photos losslessly at native 300 DPI without intermediate JPEG compression. Original camera files remain 100% untouched.
- **Side-by-Side Batch Display:** When guests take 3 photos in a session, all 3 are displayed side-by-side on screen for quick comparison, individual frame choice, rotation, and printing.
- **One-Click Session Reset:** A single **"Next Group / Clear Feed"** button archives the session and clears the screen ready for the next guest.

---

## ⌨️ Shortcuts & Controls

- **Click Photo Card:** Toggle selection for printing (`✓ SELECTED` vs `✕ SKIPPED`).
- **`🔍 Preview` Button (or Double-Click Photo):** Open the **Google Drive-style Full-Display Lightbox** with up to **400% zoom**, click-and-drag panning, `◀ Prev` / `Next ▶` arrows, live frame selector, and `Esc` to close.
- **Grid Zoom (`Ctrl + Scroll` or Top Bar `[−] 🔍 100% [+]`, or `Ctrl +` / `Ctrl -`):** Dynamically scales photo cards and automatically snaps between **3 per row**, **2 per row**, and **1 per row** (`Ctrl 0` or click the zoom label to reset to `100%`).
- **Individual Photo Frame Selection (`[ ◀ ] [ 🖼️ Template Name ] [ ▶ ]`):** Each photo card has its own dedicated frame row with left (`◀`) and right (`▶`) circular arrow buttons (`1 -> 2 -> 3 -> 1`) and an adaptive template name button that expands to display the full filename without clipping. Click the template name button for a dropdown menu to pick any template or turn the frame OFF (`🚫 No Frame`) for that specific shot.
- **Top Bar Session Default & Multi-Template Folder (`[ ◀ ] [ 🖼️ Default Template ] [ ▶ ]` or `f` key):** Point the app to any folder containing transparent `.png` frames. Sets the session default template for incoming photos, or applies a template to all current photos via the dropdown menu.
- **`[−] Copies [+]`:** Set number of copies per photo (live copy counts appear directly on the print buttons).
- **`🔄 Rotate`:** Rotates the photo 90° clockwise losslessly.
- **`Enter`:** Print all selected photos.
- **`c`:** Finish session & clear feed for next group.
- **`🧪 Test Mode: ON` / `🖨️ Live Print: ON`:** Toggle in the top bar between safe simulation and live printing.
- **`📸 +3 Shots` (Test Mode only):** Generates 3 simulated 3:2 camera photos in the watched folder during `🧪 Test Mode: ON`. Automatically hidden when switched to `🖨️ Live Print: ON` to prevent accidental clicks during live events.
- **`📋 Print Queue`:** Opens Windows native Print Queue dialog for Canon SELPHY CP1500.

---

## 📁 File Structure

- `photobooth.py`: Main CLI & Windows launcher.
- `ui_booth.py`: Multi-photo batch kiosk UI with native `Segoe UI` typography, custom auto-sizing buttons, and per-photo frame controls.
- `ui_windows.py`: Lightweight Windows native popup dialog fallback.
- `printer_service.py`: Windows printing subsystem (PowerShell GDI+, pywin32, `1.48` center-crop + `.png` frame compositing, and native queue management).
- `watcher.py`: Background thread monitoring Sony Imaging Edge save folder.
- `simulate_shots.py`: Generates clean 3:2 gradient test photos with centered shot numbers and `1.48` printable boundary lines.
- `interactive_test.py`: End-to-end interactive test script.
- `sample_frames/`: Folder containing ready-to-use transparent `.png` frame templates (`1.48` postcard ratio).
- `run.bat` / `run.ps1`: Windows one-click launchers.
- `config.json`: Stores your chosen watch folder and frame folder settings.
