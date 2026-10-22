# 📸 Photo Booth Print Automation for Canon SELPHY CP1500 (Windows Edition)

Automated, lossless, borderless photo printing workflow for Sony Imaging Edge + Canon SELPHY CP1500 on Microsoft Windows (Windows 10 & 11).

---

## 🎯 The Problem This Solves

When printing manually on Windows:
1. **Aspect Ratio Mismatch:** Sony Alpha cameras shoot at **3:2 (1.50)**. Canon SELPHY paper is Japanese Postcard (Hagaki / KP-108IN) at **100 x 148 mm (1.48)**.
2. **Margin & Scaling Issues:** Windows Photo Viewer and Print Photos wizard often add white borders or require manual fit-to-frame tweaking.
3. **Photo Frame Automation:** Manually overlaying transparent event frames (.PNG) in Canva or Photoshop for every print job is tedious and slow.

### How This Script Solves It Automatically:
- **Native Windows Printing:** Uses high-fidelity GDI+ / .NET `PrintDocument` borderless printing with zero margins and automatic 100x148 mm center-crop bleed.
- **Instant Photo Frame Overlays:** Load any transparent event frame (.PNG); the app automatically overlays it onto the camera photos, displays live previews on the kiosk and in the full-screen lightbox, and prints with the frame.
- **Zero Lossy Re-encoding:** Spools photos losslessly at native 300 DPI without intermediate JPEG compression. Original camera files remain untouched.
- **Side-by-Side Batch Display:** When guests take 3 photos in a session, all 3 are displayed side-by-side on screen for quick comparison, selection, rotation, and printing.
- **One-Click Session Reset:** A single **"Next Group / Clear Feed"** button archives the session and clears the screen ready for the next guest.

---

## 🚀 How to Run on Windows

Navigate to the project folder:
```cmd
cd PhotoBoothAutomationWindows
```

### Option A: One-Click Launcher
Double-click **`run.bat`** (or execute in Command Prompt/PowerShell).

### Option B: Interactive Test Mode (Simulates 3 Camera Shots)
```cmd
python interactive_test.py
```
- Creates 3 synthetic camera photos with colors, numbers, and timestamps.
- Launches the UI with all 3 photos displayed side-by-side.
- Lets you click to select, choose copies, preview with frames, and test print spooling.
- Click **"📋 Print Queue"** in the top bar to inspect the Windows native Print Queue dialog (`Canon SELPHY CP1500`).

### Option C: Live Photo Booth Station
```cmd
python photobooth.py
:: Or specify a custom folder:
python photobooth.py --folder "C:\Users\<YourUsername>\Pictures"
```
- Watches your Sony Imaging Edge save folder (defaults to your Windows `Pictures` folder).
- When camera photos arrive, they immediately appear on the kiosk.
- Click **"🖨️ Print Selected Photos"** (or press `Enter`) to print.
- Click **"✅ Next Group / Clear Feed"** (or press `c`) to reset the screen for the next guest.

---

## ⌨️ Shortcuts & Controls

- **Click Photo Card:** Toggle selection for printing (`✓ SELECTED` vs `✕ SKIPPED`).
- **`🔍 Preview` Button (or Double-Click Photo):** Open the **Google Drive-style Full-Display Lightbox** with up to **400% zoom**, click-and-drag panning, `◀ Prev` / `Next ▶` arrows, live frame toggle, and `Esc` to close.
- **Grid Zoom (`Ctrl + Scroll` or Top Bar `[−] 🔍 100% [+]`, or `Ctrl +` / `Ctrl -`):** Dynamically scales photo cards and automatically snaps between **3 per row**, **2 per row**, and **1 per row** (`Ctrl 0` or click the zoom label to reset to `100%`).
- **`🖼️ Frame: None / Active`:** Load a transparent PNG photo booth frame (100x148 mm ratio). Individual photos can toggle the frame on/off with their `🖼️ Frame: ON` button.
- **`[−] Copies [+]`:** Set number of copies per photo (live copy counts appear directly on the print buttons).
- **`🔄 Rotate`:** Rotates the photo 90° clockwise with lossless processing.
- **`Enter`:** Print all selected photos.
- **`c`:** Finish session & clear feed for next group.
- **`📸 +3 Shots`:** Generates 3 simulated HD camera photos in the watched folder anytime to test tethering.
- **`📋 Print Queue`:** Opens Windows native Print Queue dialog for Canon SELPHY CP1500.
- **`🧪 Test Mode: ON` / `🖨️ Live Print: ON`:** Toggle in the top bar between safe simulation and live printing.

---

## 📁 File Structure

- `photobooth.py`: Main CLI & Windows launcher.
- `ui_booth.py`: Multi-photo batch kiosk UI with native `Segoe UI` typography and tactile buttons.
- `ui_windows.py`: Lightweight Windows native popup dialog fallback.
- `printer_service.py`: Windows printing subsystem (PowerShell GDI+, pywin32, and native queue management).
- `watcher.py`: Background thread monitoring Sony Imaging Edge save folder.
- `simulate_shots.py`: Generates 3:2 synthetic camera photos for testing.
- `interactive_test.py`: End-to-end interactive test script.
- `sample_frame.png`: Ready-to-use sample transparent photo frame (1.48 Postcard ratio).
- `run.bat` / `run.ps1`: Windows one-click launchers.
- `config.json`: Stores your chosen watch folder and settings.

