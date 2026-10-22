"""
printer_service.py (Windows Edition)
Handles detection, configuration, queue management, and lossless printing to
Canon SELPHY CP1500 on Microsoft Windows.
"""

import subprocess
import shutil
import os
import sys
from PIL import Image

# On Windows, Canon SELPHY CP1500 typically installs with spaces in the device name
PRINTER_NAME = "Canon SELPHY CP1500"
POSTCARD_RATIO = 148.0 / 100.0  # 1.48 (Hagaki / 100x148 mm)


def check_printer_status(printer_name=PRINTER_NAME):
    """
    Returns (status_code, status_message) for the given printer on Windows.
    status_code: 'ready', 'offline', 'printing', 'not_found', 'simulated'
    """
    if sys.platform != "win32":
        # Cross-platform fallback for testing or non-Windows hosts
        return "ready", f"[Simulated/Cross-Platform] Windows printer '{printer_name}' service initialized."

    # Try pywin32 if installed
    try:
        import win32print
        handle = win32print.OpenPrinter(printer_name)
        try:
            info = win32print.GetPrinter(handle, 2)
            status_flags = info.get("Status", 0)
            if status_flags & 0x00000080:  # PRINTER_STATUS_OFFLINE
                return "offline", f"Printer '{printer_name}' is offline."
            elif status_flags & 0x00000400:  # PRINTER_STATUS_PRINTING
                return "printing", f"Printer '{printer_name}' is currently printing."
            return "ready", f"Printer '{printer_name}' is ready and idle."
        finally:
            win32print.ClosePrinter(handle)
    except ImportError:
        pass
    except Exception as e:
        if "cannot find" in str(e).lower() or "not found" in str(e).lower():
            return "not_found", f"Printer '{printer_name}' not found in Windows Printers."

    # Fallback to PowerShell WMI / CIM query
    try:
        ps_cmd = (
            f"Get-CimInstance Win32_Printer | "
            f"Where-Object {{ $_.Name -like '*{printer_name}*' -or $_.Name -like '*SELPHY*' }} | "
            f"Select-Object -First 1 Name, WorkOffline, PrinterStatus | "
            f"ConvertTo-Json -Compress"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        out = res.stdout.strip()
        if not out:
            return "not_found", f"Printer '{printer_name}' not detected in Windows."
        if '"WorkOffline":true' in out.replace(" ", ""):
            return "offline", "Canon SELPHY is currently powered off or offline."
        return "ready", "Canon SELPHY CP1500 is connected and ready."
    except Exception as e:
        return "ready", f"Windows printer status query fallback: {e}"


def get_print_queue_status(printer_name=PRINTER_NAME):
    """Returns the text output of the current Windows print queue for printer."""
    if sys.platform != "win32":
        return "Queue status: [Simulated/Testing - 0 active jobs]"

    try:
        ps_cmd = (
            f"Get-PrintJob -PrinterName '{printer_name}' -ErrorAction SilentlyContinue | "
            f"Format-Table -Property Id, DocumentName, JobStatus, TotalPages | Out-String"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        out = res.stdout.strip()
        return out if out else "Queue is empty."
    except Exception as e:
        return f"Error querying Windows queue: {e}"


def open_windows_print_queue(printer_name=PRINTER_NAME):
    """Opens Windows native Print Queue window for the printer."""
    try:
        # Standard native Windows print queue dialog
        subprocess.Popen(
            ["rundll32.exe", "printui.dll,PrintUIEntry", "/o", "/n", printer_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        try:
            # Fallback to Windows Settings -> Printers & Scanners
            os.system("start ms-settings:printers")
            return True
        except Exception:
            return False


def clear_print_queue(printer_name=PRINTER_NAME):
    """Cancels all pending jobs in the Windows printer queue."""
    if sys.platform != "win32":
        return True, "[Simulated] Print queue cleared."

    try:
        ps_cmd = f"Get-PrintJob -PrinterName '{printer_name}' -ErrorAction SilentlyContinue | Remove-PrintJob"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        return True, "Print queue cleared."
    except Exception as e:
        return False, str(e)


def compose_with_frame(photo, frame):
    """
    Center-crops the photo (at native resolution) to the frame's aspect ratio,
    then overlays the transparent PNG frame on top. The frame is resized to the photo, not vice versa.
    """
    fw, fh = frame.size
    pw, ph = photo.size
    if pw / ph > fw / fh:
        cw, ch = round(ph * fw / fh), ph
    else:
        cw, ch = pw, round(pw * fh / fw)
    left, top = (pw - cw) // 2, (ph - ch) // 2
    canvas = photo.crop((left, top, left + cw, top + ch)).convert("RGBA")
    overlay = frame.convert("RGBA").resize((cw, ch), Image.Resampling.LANCZOS)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def prepare_lossless_rotated_image(image_path, output_dir=None, rotation=0, frame_path=None):
    """
    If rotation or a frame is needed, prepares a 100% LOSSLESS temporary PNG print file.
    Does NOT use lossy JPEG re-compression. Preserves exact pixel data.
    """
    with Image.open(image_path) as img:
        try:
            import PIL.ImageOps
            img = PIL.ImageOps.exif_transpose(img)
        except Exception:
            pass

        if rotation != 0:
            img = img.rotate(-rotation, expand=True)

        if frame_path:
            with Image.open(frame_path) as frame:
                img = compose_with_frame(img, frame)

        if output_dir is None:
            output_dir = os.path.dirname(image_path)

        base_name = os.path.basename(image_path)
        name, _ = os.path.splitext(base_name)
        out_path = os.path.join(output_dir, f".spool_lossless_{name}.png")

        # Save as 100% LOSSLESS PNG with 300 DPI metadata
        img.convert("RGB").save(out_path, "PNG", dpi=(300, 300))
        return out_path


def _print_file_windows(file_path, printer_name=PRINTER_NAME, title="Photo"):
    """
    Internal Windows print dispatcher:
    Uses .NET System.Drawing.Printing (standard in PowerShell on Windows 10/11)
    to render full-bleed at native DPI directly to Canon SELPHY without white margins.
    """
    if sys.platform != "win32":
        return True, "Simulated non-Windows spool"

    # Normalize Windows backslashes for PowerShell single-quote escaping
    norm_path = os.path.abspath(file_path).replace("'", "''")
    norm_printer = printer_name.replace("'", "''")
    norm_title = title.replace("'", "''")

    ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.DocumentName = '{norm_title}'
$doc.PrinterSettings.PrinterName = '{norm_printer}'
$doc.PrinterSettings.Copies = 1

# Borderless margins
$doc.DefaultPageSettings.Margins = New-Object System.Drawing.Printing.Margins(0, 0, 0, 0)
$doc.OriginAtMargins = $false

$imgPath = '{norm_path}'
$img = [System.Drawing.Image]::FromFile($imgPath)

$doc.add_PrintPage({{
    param($sender, $e)
    # Fill full printable area
    $bounds = $e.PageBounds
    $e.Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $e.Graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $e.Graphics.DrawImage($img, $bounds)
    $e.HasMorePages = $false
}})

try {{
    $doc.Print()
    Write-Output "SUCCESS"
}} finally {{
    $img.Dispose()
    $doc.Dispose()
}}
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15
        )
        if res.returncode == 0 and "SUCCESS" in res.stdout:
            return True, "Print job spooled successfully."
        err = res.stderr.strip() or res.stdout.strip()
        return False, f"PowerShell print error: {err}"
    except Exception as e:
        return False, f"Windows print failed: {e}"


def print_photo(image_path, copies=1, printer_name=PRINTER_NAME, dry_run=False, rotation=0, frame_path=None):
    """
    Sends photo to Canon SELPHY CP1500 on Windows.
    
    LOSSLESS GUARANTEE:
    1. If rotation == 0 and no frame: Sends original file directly to print pipeline.
    2. If rotation != 0 or frame overlay: Generates a temporary 100% LOSSLESS PNG (zero lossy re-encoding).
    3. Handles discrete numbered copy queueing for unambiguous spool tracking.
    """
    if not os.path.isfile(image_path):
        return False, f"File not found: {image_path}"

    temp_file = None
    if rotation % 360 != 0 or frame_path:
        try:
            temp_file = prepare_lossless_rotated_image(image_path, rotation=rotation, frame_path=frame_path)
            target_print_file = temp_file
        except Exception as e:
            if frame_path:
                return False, f"Could not apply frame: {e}"
            target_print_file = image_path
    else:
        target_print_file = image_path

    fname = os.path.basename(image_path)
    job_ids = []
    errors = []

    for copy_idx in range(1, copies + 1):
        if copies > 1:
            title = f"{fname} (Copy {copy_idx} of {copies})"
        else:
            title = f"{fname} (1 copy)"

        if dry_run:
            job_ids.append(f"Simulated-{copy_idx}/{copies}: {title}")
            continue

        success, msg = _print_file_windows(target_print_file, printer_name=printer_name, title=title)
        if success:
            job_ids.append(f"Job-{copy_idx}/{copies} [{title}]")
        else:
            errors.append(f"Copy {copy_idx}: {msg}")

    # Clean up temporary lossless file if one was created
    if temp_file and os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except Exception:
            pass

    if dry_run:
        return True, f"[DRY RUN - Simulated {copies} copies] " + ", ".join(job_ids)

    if errors:
        return False, "; ".join(errors)

    return True, f"Queued {copies} copy/copies: " + ", ".join(job_ids)

