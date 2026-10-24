"""
ui_booth.py
Modern, friendly, and tactile Photo Booth Station for Canon SELPHY CP1500.
Built with Tkinter and Pillow following Apple Human Interface Guidelines (HIG) & Refactoring UI:
- True bold typography ('Helvetica Neue' bold) that pops with high contrast.
- Auto-fitted tactile rounded pill buttons with vertical sheen and bevel highlights (never hollow, never overfilled).
- High-clarity preview pipeline (Lanczos reducing_gap=2.0 + UnsharpMask optical sharpening).
- Multi-Card Grid Zoom (Cmd + Scroll or +/- buttons) that automatically snaps between 3, 2, and 1 photos per row.
- Google Drive-style Full-Display Lightbox Preview (click '🔍 Preview' or double-click any photo) with up to 400% pan/zoom.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
import os
import sys
import threading
import time
from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageEnhance

import printer_service
from watcher import FolderWatcher
import simulate_shots

# --- Apple HIG & Refactoring UI Dark Studio Palette ---
PALETTE = {
    "window_bg": "#111114",
    "surface_bg": "#1c1c21",
    "surface_elevated": "#27272e",
    "surface_border": "#32323b",
    "card_bg": "#1c1c22",
    "card_selected_bg": "#1e222d",
    "canvas_bg": "#121216",
    "lightbox_bg": "#0b0b0e",
    "lightbox_bar": "#16161b",
    "border_subtle": "#34343e",
    "border_active": "#0a84ff",
    "text_primary": "#ffffff",
    "text_secondary": "#b4b4be",
    "text_muted": "#71717a",
    # Primary Royal Blue
    "accent_blue": "#0a84ff",
    "accent_blue_hover": "#2592ff",
    "accent_blue_active": "#0066cc",
    # Vibrant Emerald Green
    "accent_green": "#10b981",
    "accent_green_hover": "#22c55e",
    "accent_green_active": "#059669",
    # Vibrant Indigo / Purple
    "accent_purple": "#6366f1",
    "accent_purple_hover": "#7577f5",
    "accent_purple_active": "#4f46e5",
    # Elevated Slate / Charcoal
    "accent_charcoal": "#383842",
    "accent_charcoal_hover": "#464652",
    "accent_charcoal_active": "#292930",
    # Warm Amber (for Test Mode / Warnings)
    "accent_amber": "#d97706",
    "accent_amber_hover": "#f59e0b",
    "accent_amber_active": "#b45309",
    "accent_amber_text": "#fbbf24",
    # Coral Red
    "accent_red": "#ef4444",
    "accent_red_hover": "#f87171",
    "accent_red_active": "#dc2626",
}

# "Segoe UI" on Windows provides crisp, modern native typography.
# "Helvetica Neue" on macOS provides native high-DPI typography.
SYSTEM_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica Neue"
MOD_KEY_HINT = "Ctrl" if sys.platform == "win32" else "Cmd"

# Grid Zoom Presets: (zoom_percent, max_columns_per_row, canvas_height_px)
GRID_ZOOM_PRESETS = [
    (85, 3, 250),    # Compact 3 per row (fits 6 photos on screen at once)
    (100, 3, 315),   # Default 3 per row (tall, crisp previews)
    (130, 2, 420),   # Large — snaps to 2 photos per row
    (160, 2, 500),   # Extra-Large — 2 photos per row
    (200, 1, 640),   # Studio Full — snaps to 1 photo per row
]
DEFAULT_ZOOM_IDX = 1


def font_bold(size):
    return (SYSTEM_FONT, size, "bold")


def font_regular(size):
    return (SYSTEM_FONT, size)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def adjust_rgb(rgb, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def render_crisp_preview(pil_img, disp_w, disp_h, dimmed=False):
    """
    High-clarity optical downscaling pipeline:
    1. Two-stage Lanczos resampling with reducing_gap=2.0 to preserve fine detail.
    2. Subtle optical UnsharpMask so facial features, eyes, and text look razor-sharp on screen.
    3. Smooth Pillow brightness dimming when a card is unselected (no pixelated stipple grid).
    """
    disp_w = max(1, int(disp_w))
    disp_h = max(1, int(disp_h))
    resized = pil_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS, reducing_gap=2.0)
    # Apply subtle optical sharpening when downscaling
    if disp_w < pil_img.width:
        resized = resized.filter(ImageFilter.UnsharpMask(radius=0.85, percent=62, threshold=2))
    if dimmed:
        resized = ImageEnhance.Brightness(resized).enhance(0.45)
    return resized


class RoundedButton(tk.Label):
    """
    Tactile, auto-fitted rounded pill button:
    - Measures its own bold text width so the label fills ~75-85% of the box (never hollow, never cramped).
    - Renders a 2x-supersampled vertical gradient pill with a crisp top light-reflection rim.
    - Reliable MacBook trackpad click handling with visual press bounce and debounce protection.
    """
    def __init__(self, parent, text, command=None, width=None, height=44, radius=14,
                 pad_x=18, min_width=38,
                 bg_hex=PALETTE["accent_blue"], hover_hex=PALETTE["accent_blue_hover"],
                 active_hex=PALETTE["accent_blue_active"], fg_hex="#ffffff",
                 font_size=16, container_bg=PALETTE["surface_bg"], auto_fit=True, **kwargs):
        self.container_bg = container_bg
        self.command = command
        self.height = height
        self.radius = min(radius, height // 2)
        self.pad_x = pad_x
        self.min_width = min_width
        self.bg_hex = bg_hex
        self.hover_hex = hover_hex
        self.active_hex = active_hex
        self.fg_hex = fg_hex
        self.font_size = font_size
        self._text = text
        self._enabled = True
        self._pressed = False
        self._last_click_time = 0.0
        self.auto_fit = auto_fit

        self._tk_font = tkfont.Font(family=SYSTEM_FONT, size=self.font_size, weight="bold")
        measured_w = self._measure_text_width(self._text)
        if width is None or self.auto_fit:
            target_w = measured_w + self.pad_x * 2
            self.width = max(self.min_width, target_w)
        else:
            self.width = max(self.min_width, width)

        self._rebuild_surfaces()

        super().__init__(
            parent,
            image=self.normal_photo,
            text=self._text,
            compound="center",
            bg=self.container_bg,
            fg=self.fg_hex,
            font=self._tk_font,
            bd=0,
            padx=0,
            pady=0,
            cursor="pointinghand",
            relief=tk.FLAT,
            **kwargs
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _rebuild_surfaces(self):
        self.normal_photo = self._make_pill_bg(self.bg_hex, mode="normal")
        self.hover_photo = self._make_pill_bg(self.hover_hex, mode="hover")
        self.active_photo = self._make_pill_bg(self.active_hex, mode="active")
        self.disabled_photo = self._make_pill_bg("#2c2c34", mode="disabled")

    def _make_pill_bg(self, fill_color, mode="normal"):
        scale = 2
        W, H, R = max(4, self.width * scale), max(4, self.height * scale), self.radius * scale
        base_rgb = hex_to_rgb(fill_color)

        if mode == "active":
            top_rgb = adjust_rgb(base_rgb, 0.88)
            bot_rgb = adjust_rgb(base_rgb, 0.98)
            border_rgb = adjust_rgb(base_rgb, 1.05)
        elif mode == "hover":
            top_rgb = adjust_rgb(base_rgb, 1.15)
            bot_rgb = adjust_rgb(base_rgb, 0.94)
            border_rgb = adjust_rgb(base_rgb, 1.38)
        elif mode == "disabled":
            top_rgb = base_rgb
            bot_rgb = base_rgb
            border_rgb = adjust_rgb(base_rgb, 1.10)
        else:
            top_rgb = adjust_rgb(base_rgb, 1.10)
            bot_rgb = adjust_rgb(base_rgb, 0.90)
            border_rgb = adjust_rgb(base_rgb, 1.28)

        grad = Image.new("RGB", (1, H))
        for y in range(H):
            t = y / max(1, H - 1)
            c = tuple(int(top_rgb[i] * (1.0 - t) + bot_rgb[i] * t) for i in range(3))
            grad.putpixel((0, y), c)
        grad = grad.resize((W, H), Image.Resampling.NEAREST)

        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=255)

        img = Image.new("RGB", (W, H), hex_to_rgb(self.container_bg))
        img.paste(grad, (0, 0), mask)

        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([1, 1, W - 2, H - 2], radius=R, outline=border_rgb, width=2)
        return ImageTk.PhotoImage(img.resize((self.width, self.height), Image.Resampling.LANCZOS))

    def set_colors(self, bg_hex, hover_hex, active_hex, fg_hex="#ffffff"):
        self.bg_hex = bg_hex
        self.hover_hex = hover_hex
        self.active_hex = active_hex
        self.fg_hex = fg_hex
        self._rebuild_surfaces()
        if self._enabled:
            self.configure(image=self.normal_photo, fg=self.fg_hex)

    def _measure_text_width(self, text_str):
        base_w = self._tk_font.measure(text_str)
        extra_emoji_px = sum(8 for ch in text_str if ord(ch) > 0x2000 and ord(ch) != 0xFE0F)
        return base_w + extra_emoji_px

    def set_text(self, new_text, resize_if_needed=False):
        self._text = new_text
        if resize_if_needed:
            measured_w = self._measure_text_width(self._text)
            new_w = max(self.min_width, measured_w + self.pad_x * 2)
            if abs(new_w - self.width) > 1:
                self.width = new_w
                self._rebuild_surfaces()
        self.configure(text=new_text, image=self.normal_photo if self._enabled else self.disabled_photo)

    def _on_enter(self, event):
        if self._enabled and not self._pressed:
            self.configure(image=self.hover_photo)

    def _on_leave(self, event):
        if self._enabled:
            self._pressed = False
            self.configure(image=self.normal_photo)

    def _on_press(self, event):
        if self._enabled:
            self._pressed = True
            self.configure(image=self.active_photo)

    def _on_release(self, event):
        if not self._enabled or not self._pressed:
            return
        self._pressed = False

        tol = 12
        inside = (-tol <= event.x <= self.width + tol) and (-tol <= event.y <= self.height + tol)
        try:
            self.configure(image=self.hover_photo if inside else self.normal_photo)
        except tk.TclError:
            return

        if inside and self.command:
            now = time.time()
            if now - self._last_click_time < 0.12:
                return
            self._last_click_time = now
            self.after(15, self.command)

    def set_enabled(self, enabled):
        self._enabled = enabled
        if enabled:
            self.configure(image=self.normal_photo, fg=self.fg_hex, cursor="pointinghand")
        else:
            self.configure(image=self.disabled_photo, fg="#6e6e77", cursor="arrow")


class PhotoCard(tk.Frame):
    """
    Card representing one photo in the active session batch.
    - High-resolution sharpened thumbnail that dynamically scales with Grid Zoom.
    - '🔍 Preview' button (and double-click on image) opens Google Drive-style full-window Lightbox.
    """
    def __init__(self, parent, photo_path, shot_index, on_toggle_select, on_print_single, on_open_preview,
                 canvas_height=315, get_frame=None, frame_index=0, get_frame_templates=None,
                 on_frame_change=None, **kwargs):
        super().__init__(
            parent, bg=PALETTE["card_selected_bg"], highlightthickness=3,
            highlightbackground=PALETTE["accent_blue"], bd=0, **kwargs
        )
        self.photo_path = photo_path
        self.shot_index = shot_index
        self.on_toggle_select = on_toggle_select
        self.on_print_single = on_print_single
        self.on_open_preview = on_open_preview
        self.canvas_height = canvas_height
        self.get_frame = get_frame or (lambda: None)
        self.frame_index = frame_index
        self.get_frame_templates = get_frame_templates or (lambda: [])
        self.on_frame_change = on_frame_change
        self.use_frame = True

        self.selected = True
        self.copies = 1
        self.rotation = 0
        self.pil_img = None
        self.preview_master = None  # 1800px working master for fast, ultra-crisp card zooming
        self.tk_thumb = None
        self._thumb_cache = {}
        self._single_click_job = None

        self._build_card()
        self._load_and_render_image()
        self.update_selection_visual()

    def _build_card(self):
        # 1. Header Row (Shot Number Badge + Filename on Left, Selection Badge on Right)
        self.header = tk.Frame(self, bg=PALETTE["card_selected_bg"], cursor="pointinghand")
        self.header.pack(fill=tk.X, padx=12, pady=(10, 4))

        self.lbl_badge = tk.Label(
            self.header, text=f"📸 Shot #{self.shot_index}", font=font_bold(13),
            bg=PALETTE["accent_blue"], fg="#ffffff", padx=8, pady=3, cursor="pointinghand"
        )
        self.lbl_badge.pack(side=tk.LEFT)

        fname = os.path.basename(self.photo_path)
        if len(fname) > 13:
            fname = fname[:6] + "…" + fname[-5:]
        self.lbl_name = tk.Label(
            self.header, text=f" {fname}", font=font_bold(12),
            bg=PALETTE["card_selected_bg"], fg=PALETTE["text_secondary"], cursor="pointinghand"
        )
        self.lbl_name.pack(side=tk.LEFT, padx=4)

        self.lbl_select_badge = tk.Label(
            self.header, text="✓ SELECTED", font=font_bold(12),
            bg=PALETTE["accent_green"], fg="#ffffff", padx=8, pady=3, cursor="pointinghand"
        )
        self.lbl_select_badge.pack(side=tk.RIGHT)

        for widget in (self, self.header, self.lbl_badge, self.lbl_name, self.lbl_select_badge):
            widget.bind("<Button-1>", lambda e: self.toggle_selection())

        # 2. High-Clarity Image Preview Canvas
        self.canvas = tk.Canvas(
            self, bg=PALETTE["canvas_bg"], highlightthickness=1,
            highlightbackground=PALETTE["surface_border"], height=self.canvas_height, cursor="pointinghand"
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        self.canvas.bind("<Button-1>", self._on_canvas_single_click)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda e: self._render_thumbnail())

        # 3. Photo Tools Row (Preview Lightbox + Rotate)
        self.tools_frame = tk.Frame(self, bg=PALETTE["card_selected_bg"])
        self.tools_frame.pack(fill=tk.X, padx=12, pady=(6, 2))

        self.btn_preview = RoundedButton(
            self.tools_frame, text="🔍 Preview", command=lambda: self.on_open_preview(self),
            height=32, radius=10, pad_x=10, font_size=12,
            bg_hex=PALETTE["accent_purple"], hover_hex=PALETTE["accent_purple_hover"],
            active_hex=PALETTE["accent_purple_active"], container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_preview.pack(side=tk.LEFT)

        self.btn_rot = RoundedButton(
            self.tools_frame, text="🔄 Rotate", command=self.rotate_photo,
            height=32, radius=10, pad_x=10, font_size=12,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_rot.pack(side=tk.RIGHT)

        # 3b. Individual Photo Frame Stepper Row ([ ◀ ] [ 🖼️ Full Template Name ] [ ▶ ])
        self.frame_row = tk.Frame(self, bg=PALETTE["card_selected_bg"])
        self.frame_row.pack(fill=tk.X, padx=12, pady=(2, 4))

        self.frame_stepper = tk.Frame(self.frame_row, bg=PALETTE["card_selected_bg"])
        self.frame_stepper.pack(anchor=tk.CENTER)

        self.btn_frame_prev = RoundedButton(
            self.frame_stepper, text="◀", command=self.prev_template,
            height=32, radius=10, pad_x=8, min_width=30, font_size=12,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_frame_prev.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_frame_toggle = RoundedButton(
            self.frame_stepper, text="🖼️ Frame", command=self.on_frame_click,
            height=32, radius=10, pad_x=14, font_size=12,
            bg_hex=PALETTE["accent_purple"], hover_hex=PALETTE["accent_purple_hover"],
            active_hex=PALETTE["accent_purple_active"], container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_frame_toggle.pack(side=tk.LEFT, padx=2)

        self.btn_frame_next = RoundedButton(
            self.frame_stepper, text="▶", command=self.next_template,
            height=32, radius=10, pad_x=8, min_width=30, font_size=12,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_frame_next.pack(side=tk.LEFT, padx=(4, 0))
        self._update_frame_visual()

        # 4. Print & Quantity Controls Row (Copies Stepper on Left + Direct Print on Right)
        self.controls = tk.Frame(self, bg=PALETTE["card_selected_bg"])
        self.controls.pack(fill=tk.X, padx=12, pady=(4, 10))

        self.stepper_frame = tk.Frame(
            self.controls, bg=PALETTE["surface_elevated"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        self.stepper_frame.pack(side=tk.LEFT)

        self.btn_minus = RoundedButton(
            self.stepper_frame, text="−", command=self.decrement_copies,
            height=34, radius=9, pad_x=6, min_width=32,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=18,
            container_bg=PALETTE["surface_elevated"]
        )
        self.btn_minus.pack(side=tk.LEFT, padx=2, pady=2)

        self.lbl_copies_num = tk.Label(
            self.stepper_frame, text="1 Copy", font=font_bold(13), width=7,
            bg=PALETTE["surface_elevated"], fg="#ffffff", padx=2
        )
        self.lbl_copies_num.pack(side=tk.LEFT)

        self.btn_plus = RoundedButton(
            self.stepper_frame, text="+", command=self.increment_copies,
            height=34, radius=9, pad_x=6, min_width=32,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=18,
            container_bg=PALETTE["surface_elevated"]
        )
        self.btn_plus.pack(side=tk.LEFT, padx=2, pady=2)

        self.btn_print_this = RoundedButton(
            self.controls, text="🖨️ Print 1x", command=lambda: self.on_print_single(self),
            height=36, radius=10, pad_x=12,
            bg_hex=PALETTE["accent_blue"], hover_hex=PALETTE["accent_blue_hover"],
            active_hex=PALETTE["accent_blue_active"], font_size=13,
            container_bg=PALETTE["card_selected_bg"]
        )
        self.btn_print_this.pack(side=tk.RIGHT)

    def _on_canvas_single_click(self, event):
        if self._single_click_job is not None:
            self.after_cancel(self._single_click_job)
        self._single_click_job = self.after(190, self._commit_single_click)

    def _commit_single_click(self):
        self._single_click_job = None
        self.toggle_selection()

    def _on_canvas_double_click(self, event):
        if self._single_click_job is not None:
            self.after_cancel(self._single_click_job)
            self._single_click_job = None
        self.on_open_preview(self)

    def set_canvas_height(self, new_height):
        if self.canvas_height != new_height:
            self.canvas_height = new_height
            self.canvas.configure(height=new_height)

    def _load_and_render_image(self):
        try:
            self.pil_img = Image.open(self.photo_path)
            try:
                import PIL.ImageOps
                self.pil_img = PIL.ImageOps.exif_transpose(self.pil_img)
            except Exception:
                pass
            # Create a 1800px high-definition working master for super-fast, sharp grid zooming
            w, h = self.pil_img.size
            if max(w, h) > 1800:
                scale = 1800.0 / max(w, h)
                self.preview_master = self.pil_img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS, reducing_gap=2.0
                )
            else:
                self.preview_master = self.pil_img
            self._render_thumbnail()
        except Exception as e:
            self.canvas.create_text(
                140, 110, text=f"Error loading image:\n{e}",
                fill=PALETTE["accent_red"], font=font_bold(13)
            )

    def _render_thumbnail(self):
        source_img = self.preview_master or self.pil_img
        if not source_img:
            return
        c_w = self.canvas.winfo_width()
        c_h = self.canvas.winfo_height()
        if c_w < 40 or c_h < 40:
            c_w, c_h = 380, self.canvas_height

        img = source_img
        if self.rotation % 360 != 0:
            img = img.rotate(-self.rotation, expand=True)

        # Show exactly what will print: overlay the frame when one is chosen and enabled for this photo
        try:
            frame = self.get_frame(self) if self.use_frame else None
        except TypeError:
            frame = self.get_frame() if self.use_frame else None
        if frame is not None:
            composed_key = (self.rotation % 360, id(frame))
            cur_comp = getattr(self, "_composed", None)
            if cur_comp is None or cur_comp[0] != composed_key:
                self._composed = (composed_key, printer_service.compose_with_frame(img, frame))
            img = self._composed[1]

        w, h = img.size
        scale = min((c_w - 6) / w, (c_h - 6) / h)
        disp_w = max(1, int(w * scale))
        disp_h = max(1, int(h * scale))

        cache_key = (disp_w, disp_h, self.rotation % 360, self.selected, id(frame) if frame is not None else None)
        if cache_key in self._thumb_cache:
            self.tk_thumb = self._thumb_cache[cache_key]
        else:
            crisp_img = render_crisp_preview(img, disp_w, disp_h, dimmed=not self.selected)
            self.tk_thumb = ImageTk.PhotoImage(crisp_img)
            if len(self._thumb_cache) > 12:
                self._thumb_cache.clear()
            self._thumb_cache[cache_key] = self.tk_thumb

        self.canvas.delete("all")
        cx, cy = c_w // 2, c_h // 2
        self.canvas.create_image(cx, cy, image=self.tk_thumb, anchor=tk.CENTER)

    def rotate_photo(self):
        self.rotation = (self.rotation + 90) % 360
        self._render_thumbnail()

    def _update_frame_visual(self):
        templates = self.get_frame_templates()
        total = len(templates)
        if not self.use_frame or total == 0:
            self.btn_frame_toggle.set_colors(
                PALETTE["accent_charcoal"], PALETTE["accent_charcoal_hover"], PALETTE["accent_charcoal_active"],
                fg_hex=PALETTE["text_secondary"]
            )
            self.btn_frame_toggle.set_text("🖼️ Frame: OFF", resize_if_needed=True)
        else:
            if not (0 <= self.frame_index < total):
                self.frame_index = 0
            path = templates[self.frame_index]
            raw_name = os.path.splitext(os.path.basename(path))[0]
            clean_name = raw_name
            if len(clean_name) > 3 and clean_name[:2].isdigit() and clean_name[2] in ("_", "-", " "):
                clean_name = clean_name[3:]
            clean_name = clean_name.replace("_", " ")

            text = f"🖼️ {clean_name}"
            self.btn_frame_toggle.set_colors(
                PALETTE["accent_purple"], PALETTE["accent_purple_hover"], PALETTE["accent_purple_active"]
            )
            self.btn_frame_toggle.set_text(text, resize_if_needed=True)

        can_cycle = total > 1
        if hasattr(self, "btn_frame_prev"):
            self.btn_frame_prev.set_enabled(can_cycle)
        if hasattr(self, "btn_frame_next"):
            self.btn_frame_next.set_enabled(can_cycle)

    def on_frame_click(self):
        """Opens dropdown menu to choose template directly or toggle off."""
        templates = self.get_frame_templates()
        if not templates:
            self.toggle_frame()
            return

        menu = tk.Menu(
            self, tearoff=0,
            bg=PALETTE["surface_elevated"], fg="#ffffff",
            activebackground=PALETTE["accent_purple"], activeforeground="#ffffff",
            font=font_bold(12)
        )
        menu.add_command(label=f"── Frame for Shot #{self.shot_index} ──", state=tk.DISABLED)
        for idx, path in enumerate(templates):
            name = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
            marker = "✓  " if (self.use_frame and idx == self.frame_index) else "    "
            menu.add_command(
                label=f"{marker}{idx + 1}. {name}",
                command=lambda i=idx: self.set_template(i)
            )
        menu.add_separator()
        if self.use_frame:
            menu.add_command(label="🚫 Turn Frame OFF", command=self.toggle_frame)
        else:
            menu.add_command(label="🖼️ Turn Frame ON", command=self.toggle_frame)
        if len(templates) > 1:
            menu.add_command(label="◀ Previous Template", command=self.prev_template)
            menu.add_command(label="▶ Next Template", command=self.next_template)

        x = self.btn_frame_toggle.winfo_rootx()
        y = self.btn_frame_toggle.winfo_rooty() + self.btn_frame_toggle.winfo_height() + 2
        menu.post(x, y)

    def next_template(self):
        """Cycles circularly to the next template for this photo."""
        templates = self.get_frame_templates()
        if not templates:
            return
        if not self.use_frame:
            self.use_frame = True
            self.frame_index = 0
        else:
            self.frame_index = (self.frame_index + 1) % len(templates)
        self._composed = None
        self._thumb_cache.clear()
        self._update_frame_visual()
        self._render_thumbnail()
        if self.on_frame_change:
            self.on_frame_change(self)

    def prev_template(self):
        """Cycles circularly to the previous template for this photo."""
        templates = self.get_frame_templates()
        if not templates:
            return
        if not self.use_frame:
            self.use_frame = True
            self.frame_index = len(templates) - 1
        else:
            self.frame_index = (self.frame_index - 1) % len(templates)
        self._composed = None
        self._thumb_cache.clear()
        self._update_frame_visual()
        self._render_thumbnail()
        if self.on_frame_change:
            self.on_frame_change(self)

    def set_template(self, i):
        """Selects a specific template for this photo."""
        templates = self.get_frame_templates()
        if 0 <= i < len(templates):
            self.use_frame = True
            self.frame_index = i
            self._composed = None
            self._thumb_cache.clear()
            self._update_frame_visual()
            self._render_thumbnail()
            if self.on_frame_change:
                self.on_frame_change(self)

    def toggle_frame(self):
        """Toggles frame ON / OFF for this photo."""
        self.use_frame = not self.use_frame
        self._composed = None
        self._thumb_cache.clear()
        self._update_frame_visual()
        self._render_thumbnail()
        if self.on_frame_change:
            self.on_frame_change(self)

    def _sync_copy_labels(self):
        unit = "Copy" if self.copies == 1 else "Copies"
        self.lbl_copies_num.config(text=f"{self.copies} {unit}")
        self.btn_print_this.set_text(f"🖨️ Print {self.copies}x", resize_if_needed=True)

    def increment_copies(self):
        if self.copies < 10:
            self.copies += 1
            if not self.selected:
                self.selected = True
                self.update_selection_visual()
            self._sync_copy_labels()
            self.on_toggle_select()

    def decrement_copies(self):
        if self.copies > 1:
            self.copies -= 1
            self._sync_copy_labels()
            self.on_toggle_select()

    def toggle_selection(self):
        self.selected = not self.selected
        self.update_selection_visual()
        self._render_thumbnail()
        self.on_toggle_select()

    def update_selection_visual(self):
        card_bg = PALETTE["card_selected_bg"] if self.selected else PALETTE["card_bg"]
        self.configure(bg=card_bg)
        self.header.configure(bg=card_bg)
        self.lbl_name.configure(bg=card_bg)
        self.tools_frame.configure(bg=card_bg)
        self.frame_row.configure(bg=card_bg)
        self.frame_stepper.configure(bg=card_bg)
        self.controls.configure(bg=card_bg)
        for btn in (self.btn_preview, self.btn_frame_prev, self.btn_frame_toggle, self.btn_frame_next, self.btn_rot, self.btn_print_this):
            btn.container_bg = card_bg
            btn._rebuild_surfaces()

        if self.selected:
            self.configure(highlightbackground=PALETTE["accent_blue"], highlightcolor=PALETTE["accent_blue"])
            self.lbl_badge.configure(bg=PALETTE["accent_blue"], fg="#ffffff")
            self.lbl_select_badge.configure(text="✓ SELECTED", bg=PALETTE["accent_green"], fg="#ffffff")
            self.btn_print_this.set_enabled(True)
        else:
            self.configure(highlightbackground=PALETTE["border_subtle"], highlightcolor=PALETTE["border_subtle"])
            self.lbl_badge.configure(bg=PALETTE["accent_charcoal"], fg=PALETTE["text_secondary"])
            self.lbl_select_badge.configure(text="✕ SKIPPED", bg=PALETTE["accent_charcoal"], fg=PALETTE["text_secondary"])
            self.btn_print_this.set_enabled(False)
        self.btn_preview.configure(image=self.btn_preview.normal_photo)
        self.btn_frame_prev.set_enabled(self.btn_frame_prev._enabled)
        self.btn_frame_toggle.configure(image=self.btn_frame_toggle.normal_photo)
        self.btn_frame_next.set_enabled(self.btn_frame_next._enabled)
        self.btn_rot.configure(image=self.btn_rot.normal_photo)


class PhotoBoothApp:
    def __init__(self, root, watch_folder=None, dry_run=False):
        self.root = root
        self.root.title("📸 Photo Booth Station — Canon SELPHY CP1500")
        self.root.geometry("1340x920")
        self.root.minsize(1100, 760)
        self.root.configure(bg=PALETTE["window_bg"])

        self.watch_folder = os.path.abspath(os.path.expanduser(watch_folder)) if watch_folder else os.path.expanduser("~/Pictures")
        self.dry_run = tk.BooleanVar(value=dry_run)

        self.active_cards = []
        self.processed_files = set()

        # Grid Zoom State
        self.zoom_idx = DEFAULT_ZOOM_IDX
        self._last_zoom_scroll_time = 0.0

        # Google Drive-style Lightbox State
        self.lightbox_card = None
        self.lightbox_zoom = 1.0  # 1.0 = Fit to screen, up to 4.0 (400%)
        self.lightbox_pan_x = 0.0
        self.lightbox_pan_y = 0.0
        self._drag_start = None
        self.lightbox_tk_img = None

        # Multi-template photo frame system
        self.frame_templates = []
        self.frame_index = -1
        self.frame_path = None
        self.frame_img = None
        self.frames_folder = None
        self._frame_cache = {}

        self._build_top_bar()
        self._build_bottom_bar()
        self._build_gallery_area()
        self._build_lightbox_overlay()
        self._bind_shortcuts()
        self._init_frame_templates()

        # Initialize Folder Watcher
        self.watcher = FolderWatcher(self.watch_folder, self.on_new_photo_detected)
        self.watcher.start()

        # Load recent existing photos into the active batch (up to 6) so they appear on launch
        existing = self.watcher.get_recent_photos(limit=6)
        if existing:
            existing.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
            for p in existing:
                self._add_photo_to_active_batch(p)

        self.update_printer_status()

    @staticmethod
    def _format_short_path(path_str):
        parts = [p for p in path_str.split(os.sep) if p]
        if len(parts) <= 2:
            return path_str
        return "…/" + "/".join(parts[-2:])

    def _build_top_bar(self):
        top_outer = tk.Frame(
            self.root, bg=PALETTE["surface_bg"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        top_outer.pack(fill=tk.X, side=tk.TOP, padx=16, pady=(12, 6))

        top_bar = tk.Frame(top_outer, bg=PALETTE["surface_bg"])
        top_bar.pack(fill=tk.X, padx=12, pady=10)

        # Left: Title + Folder Selector
        lbl_title = tk.Label(
            top_bar, text="📸 Photo Booth", font=font_bold(19),
            fg=PALETTE["text_primary"], bg=PALETTE["surface_bg"]
        )
        lbl_title.pack(side=tk.LEFT, padx=(4, 12))

        btn_folder = RoundedButton(
            top_bar, text="📁 Folder", command=self.select_folder,
            height=40, radius=11, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_bg"]
        )
        btn_folder.pack(side=tk.LEFT, padx=4)

        self.lbl_folder = tk.Label(
            top_bar, text=self._format_short_path(self.watch_folder), font=font_bold(12),
            fg=PALETTE["text_secondary"], bg=PALETTE["surface_bg"]
        )
        self.lbl_folder.pack(side=tk.LEFT, padx=(4, 12))

        # Multi-Template Frame Stepper: [ ◀ ] [ 🖼️ Template (1/3) ] [ ▶ ]
        self.frame_box = tk.Frame(
            top_bar, bg=PALETTE["surface_elevated"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        self.frame_box.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_frame_prev = RoundedButton(
            self.frame_box, text="◀", command=self.prev_frame_template,
            height=36, radius=9, pad_x=8, min_width=30, font_size=13,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_elevated"]
        )

        self.btn_frame_active = RoundedButton(
            self.frame_box, text="🖼️ Frame: None", command=self._on_frame_button_clicked,
            height=36, radius=9, pad_x=12, font_size=13,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_elevated"]
        )
        self.btn_frame_active.pack(side=tk.LEFT, padx=2, pady=2)
        self.btn_frame = self.btn_frame_active

        self.btn_frame_next = RoundedButton(
            self.frame_box, text="▶", command=self.next_frame_template,
            height=36, radius=9, pad_x=8, min_width=30, font_size=13,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_elevated"]
        )

        # Center-Left: Grid Zoom Stepper ([ − ] 🔍 100% (3/row) [ + ])
        zoom_frame = tk.Frame(
            top_bar, bg=PALETTE["surface_elevated"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        zoom_frame.pack(side=tk.LEFT, padx=6)

        self.btn_zoom_out = RoundedButton(
            zoom_frame, text="−", command=self.zoom_out,
            height=36, radius=9, pad_x=11, min_width=36,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=19,
            container_bg=PALETTE["surface_elevated"]
        )
        self.btn_zoom_out.pack(side=tk.LEFT, padx=2, pady=2)

        self.lbl_zoom = tk.Label(
            zoom_frame, text="🔍 100% (3/row)", font=font_bold(13), width=14,
            bg=PALETTE["surface_elevated"], fg="#ffffff", cursor="pointinghand"
        )
        self.lbl_zoom.pack(side=tk.LEFT, padx=4)
        self.lbl_zoom.bind("<Button-1>", lambda e: self.zoom_reset())

        self.btn_zoom_in = RoundedButton(
            zoom_frame, text="+", command=self.zoom_in,
            height=36, radius=9, pad_x=11, min_width=36,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=19,
            container_bg=PALETTE["surface_elevated"]
        )
        self.btn_zoom_in.pack(side=tk.LEFT, padx=2, pady=2)

        # Right: Printer Status + Queue + Simulate + Tactile Mode Toggle
        self.lbl_printer = tk.Label(
            top_bar, text="● SELPHY: CHECKING", font=font_bold(13),
            fg=PALETTE["accent_green"], bg=PALETTE["surface_elevated"],
            padx=10, pady=8
        )
        self.lbl_printer.pack(side=tk.RIGHT, padx=(6, 2))

        btn_queue = RoundedButton(
            top_bar, text="📋 Print Queue", command=self.open_queue_window,
            height=40, radius=11, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_bg"]
        )
        btn_queue.pack(side=tk.RIGHT, padx=4)

        self.btn_sim = RoundedButton(
            top_bar, text="📸 +3 Shots", command=self.simulate_batch,
            height=40, radius=11, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_purple"], hover_hex=PALETTE["accent_purple_hover"],
            active_hex=PALETTE["accent_purple_active"], container_bg=PALETTE["surface_bg"]
        )
        if self.dry_run.get():
            self.btn_sim.pack(side=tk.RIGHT, padx=4)

        self.btn_mode_toggle = RoundedButton(
            top_bar, text="🧪 Test Mode: ON", command=self.toggle_dry_run,
            height=40, radius=11, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_amber"], hover_hex=PALETTE["accent_amber_hover"],
            active_hex=PALETTE["accent_amber_active"], container_bg=PALETTE["surface_bg"]
        )
        self.btn_mode_toggle.pack(side=tk.RIGHT, padx=4)
        self._sync_mode_toggle_visual()

    def toggle_dry_run(self):
        self.dry_run.set(not self.dry_run.get())
        self._sync_mode_toggle_visual()
        mode_desc = (
            "🧪 Test Mode (Dry Run) enabled — prints will be simulated safely."
            if self.dry_run.get()
            else "🖨️ Live Print Mode enabled — jobs will be sent to Canon SELPHY CP1500."
        )
        self.lbl_status.config(text=mode_desc)

    def _sync_mode_toggle_visual(self):
        if self.dry_run.get():
            self.btn_mode_toggle.set_colors(
                PALETTE["accent_amber"], PALETTE["accent_amber_hover"], PALETTE["accent_amber_active"]
            )
            self.btn_mode_toggle.set_text("🧪 Test Mode: ON", resize_if_needed=True)
            if hasattr(self, "btn_sim") and not self.btn_sim.winfo_ismapped():
                self.btn_sim.pack(side=tk.RIGHT, padx=4, before=self.btn_mode_toggle)
            if hasattr(self, "btn_standby_sim"):
                self.btn_standby_sim.pack()
        else:
            self.btn_mode_toggle.set_colors(
                PALETTE["accent_green"], PALETTE["accent_green_hover"], PALETTE["accent_green_active"]
            )
            self.btn_mode_toggle.set_text("🖨️ Live Print: ON", resize_if_needed=True)
            if hasattr(self, "btn_sim"):
                self.btn_sim.pack_forget()
            if hasattr(self, "btn_standby_sim"):
                self.btn_standby_sim.pack_forget()

    # --- Grid Zoom Logic (Snaps between 3, 2, and 1 columns per row) ---
    def zoom_in(self):
        if self.lightbox_card is not None:
            self.lightbox_zoom_in()
            return
        if self.zoom_idx < len(GRID_ZOOM_PRESETS) - 1:
            self.zoom_idx += 1
            self._apply_grid_zoom()

    def zoom_out(self):
        if self.lightbox_card is not None:
            self.lightbox_zoom_out()
            return
        if self.zoom_idx > 0:
            self.zoom_idx -= 1
            self._apply_grid_zoom()

    def zoom_reset(self):
        if self.lightbox_card is not None:
            self.lightbox_zoom_reset()
            return
        self.zoom_idx = DEFAULT_ZOOM_IDX
        self._apply_grid_zoom()

    def _apply_grid_zoom(self):
        pct, cols, c_height = GRID_ZOOM_PRESETS[self.zoom_idx]
        self.lbl_zoom.config(text=f"🔍 {pct}% ({cols}/row)")
        for card in self.active_cards:
            card.set_canvas_height(c_height)
        self._rearrange_cards_grid(scroll_to_bottom=False)
        self.lbl_status.config(
            text=f"🔍 Display Zoom set to {pct}% — showing up to {cols} photo(s) per row ({MOD_KEY_HINT} + Scroll or +/- to adjust)."
        )

    def _build_gallery_area(self):
        """Container for the current session's multi-photo grid with smart pixel scrolling."""
        self.gallery_outer = tk.Frame(self.root, bg=PALETTE["window_bg"])
        self.gallery_outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Standby frame shown when feed is empty
        self.standby_frame = tk.Frame(
            self.gallery_outer, bg=PALETTE["surface_bg"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        self.standby_frame.pack(fill=tk.BOTH, expand=True, pady=6)

        standby_inner = tk.Frame(self.standby_frame, bg=PALETTE["surface_bg"])
        standby_inner.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        lbl_standby_icon = tk.Label(
            standby_inner, text="📸", font=font_bold(54), bg=PALETTE["surface_bg"],
            fg=PALETTE["text_primary"]
        )
        lbl_standby_icon.pack(pady=(0, 12))

        lbl_standby = tk.Label(
            standby_inner,
            text="Ready for Next Guests!",
            font=font_bold(26), fg=PALETTE["text_primary"], bg=PALETTE["surface_bg"],
            justify=tk.CENTER
        )
        lbl_standby.pack(pady=(0, 8))

        lbl_standby_sub = tk.Label(
            standby_inner,
            text="Take photos on your Sony camera — they will pop up here side-by-side automatically.",
            font=font_bold(16), fg=PALETTE["text_secondary"], bg=PALETTE["surface_bg"],
            justify=tk.CENTER
        )
        lbl_standby_sub.pack(pady=(0, 26))

        self.btn_standby_sim = RoundedButton(
            standby_inner, text="📸 Simulate 3 Camera Shots Now", command=self.simulate_batch,
            height=56, radius=16, pad_x=26, font_size=19,
            bg_hex=PALETTE["accent_purple"], hover_hex=PALETTE["accent_purple_hover"],
            active_hex=PALETTE["accent_purple_active"], container_bg=PALETTE["surface_bg"]
        )
        if self.dry_run.get():
            self.btn_standby_sim.pack()

        # Scrollable gallery container
        self.gallery_canvas = tk.Canvas(
            self.gallery_outer, bg=PALETTE["window_bg"],
            highlightthickness=0, yscrollincrement=1
        )
        self.scrollbar = tk.Scrollbar(self.gallery_outer, orient="vertical", command=self.gallery_canvas.yview)
        self.cards_grid = tk.Frame(self.gallery_canvas, bg=PALETTE["window_bg"])

        self.cards_grid.bind("<Configure>", self._on_cards_grid_configure)
        self.canvas_win_id = self.gallery_canvas.create_window((0, 0), window=self.cards_grid, anchor="nw")
        self.gallery_canvas.bind("<Configure>", self._on_canvas_configure)
        self.gallery_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.gallery_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # --- Google Drive-Style Full-Window Lightbox Preview ---
    def _build_lightbox_overlay(self):
        self.lightbox_frame = tk.Frame(self.root, bg=PALETTE["lightbox_bg"])

        # Top Bar in Lightbox
        lb_top = tk.Frame(
            self.lightbox_frame, bg=PALETTE["lightbox_bar"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        lb_top.pack(fill=tk.X, side=tk.TOP)

        lb_top_inner = tk.Frame(lb_top, bg=PALETTE["lightbox_bar"])
        lb_top_inner.pack(fill=tk.X, padx=18, pady=10)

        self.lbl_lb_title = tk.Label(
            lb_top_inner, text="📸 Shot #1", font=font_bold(18),
            fg="#ffffff", bg=PALETTE["lightbox_bar"]
        )
        self.lbl_lb_title.pack(side=tk.LEFT, padx=(4, 14))

        self.btn_lb_select = RoundedButton(
            lb_top_inner, text="✓ SELECTED FOR PRINT", command=self._lightbox_toggle_select,
            height=40, radius=11, pad_x=16, font_size=14,
            bg_hex=PALETTE["accent_green"], hover_hex=PALETTE["accent_green_hover"],
            active_hex=PALETTE["accent_green_active"], container_bg=PALETTE["lightbox_bar"]
        )
        self.btn_lb_select.pack(side=tk.LEFT, padx=6)

        self.btn_lb_frame = RoundedButton(
            lb_top_inner, text="🖼️ Frame: ON", command=self._lightbox_toggle_frame,
            height=40, radius=11, pad_x=16, font_size=14,
            bg_hex=PALETTE["accent_purple"], hover_hex=PALETTE["accent_purple_hover"],
            active_hex=PALETTE["accent_purple_active"], container_bg=PALETTE["lightbox_bar"]
        )
        self.btn_lb_frame.pack(side=tk.LEFT, padx=6)

        self.btn_lb_next_frame = RoundedButton(
            lb_top_inner, text="Next Template ▶", command=self._lightbox_next_frame,
            height=40, radius=11, pad_x=14, font_size=13,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["lightbox_bar"]
        )

        # Close Lightbox Button (Right)
        self.btn_lb_close = RoundedButton(
            lb_top_inner, text="✕ Close Preview [Esc]", command=self.close_lightbox,
            height=40, radius=11, pad_x=16, font_size=15,
            bg_hex=PALETTE["accent_red"], hover_hex=PALETTE["accent_red_hover"],
            active_hex=PALETTE["accent_red_active"], container_bg=PALETTE["lightbox_bar"]
        )
        self.btn_lb_close.pack(side=tk.RIGHT, padx=4)

        # Lightbox Zoom Stepper (Center-Right)
        lb_zoom_box = tk.Frame(
            lb_top_inner, bg=PALETTE["surface_elevated"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        lb_zoom_box.pack(side=tk.RIGHT, padx=16)

        btn_lb_zout = RoundedButton(
            lb_zoom_box, text="−", command=self.lightbox_zoom_out,
            height=36, radius=9, pad_x=11, min_width=36,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=19,
            container_bg=PALETTE["surface_elevated"]
        )
        btn_lb_zout.pack(side=tk.LEFT, padx=2, pady=2)

        self.lbl_lb_zoom = tk.Label(
            lb_zoom_box, text="🔍 Fit (100%)", font=font_bold(14), width=12,
            bg=PALETTE["surface_elevated"], fg="#ffffff", cursor="pointinghand"
        )
        self.lbl_lb_zoom.pack(side=tk.LEFT, padx=4)
        self.lbl_lb_zoom.bind("<Button-1>", lambda e: self.lightbox_zoom_reset())

        btn_lb_zin = RoundedButton(
            lb_zoom_box, text="+", command=self.lightbox_zoom_in,
            height=36, radius=9, pad_x=11, min_width=36,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=19,
            container_bg=PALETTE["surface_elevated"]
        )
        btn_lb_zin.pack(side=tk.LEFT, padx=2, pady=2)

        # Bottom Control Bar in Lightbox
        lb_bot = tk.Frame(
            self.lightbox_frame, bg=PALETTE["lightbox_bar"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        lb_bot.pack(fill=tk.X, side=tk.BOTTOM)

        lb_bot_inner = tk.Frame(lb_bot, bg=PALETTE["lightbox_bar"])
        lb_bot_inner.pack(fill=tk.X, padx=18, pady=12)

        lbl_lb_hint = tk.Label(
            lb_bot_inner,
            text="💡 Scroll or click [− / +] to zoom up to 400%  •  Drag photo to pan  •  ◀ / ▶ arrows to switch shots  •  Esc to close",
            font=font_bold(13), fg=PALETTE["text_secondary"], bg=PALETTE["lightbox_bar"]
        )
        lbl_lb_hint.pack(side=tk.LEFT, padx=6)

        # Right side controls in Lightbox bottom bar: Prev / Next + Copies + Rotate + Print
        self.btn_lb_print = RoundedButton(
            lb_bot_inner, text="🖨️ Print This (1x)",
            command=lambda: self._print_single_card(self.lightbox_card) if self.lightbox_card else None,
            height=46, radius=13, pad_x=18, font_size=16,
            bg_hex=PALETTE["accent_blue"], hover_hex=PALETTE["accent_blue_hover"],
            active_hex=PALETTE["accent_blue_active"], container_bg=PALETTE["lightbox_bar"]
        )
        self.btn_lb_print.pack(side=tk.RIGHT, padx=6)

        self.btn_lb_rot = RoundedButton(
            lb_bot_inner, text="🔄 Rotate", command=self._lightbox_rotate,
            height=46, radius=13, pad_x=15, font_size=15,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["lightbox_bar"]
        )
        self.btn_lb_rot.pack(side=tk.RIGHT, padx=6)

        lb_stepper = tk.Frame(
            lb_bot_inner, bg=PALETTE["surface_elevated"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        lb_stepper.pack(side=tk.RIGHT, padx=8)

        btn_lb_cminus = RoundedButton(
            lb_stepper, text="−", command=self._lightbox_dec_copies,
            height=40, radius=10, pad_x=12, min_width=40,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=20,
            container_bg=PALETTE["surface_elevated"]
        )
        btn_lb_cminus.pack(side=tk.LEFT, padx=3, pady=3)

        self.lbl_lb_copies = tk.Label(
            lb_stepper, text="1 Copy", font=font_bold(15), width=8,
            bg=PALETTE["surface_elevated"], fg="#ffffff"
        )
        self.lbl_lb_copies.pack(side=tk.LEFT, padx=2)

        btn_lb_cplus = RoundedButton(
            lb_stepper, text="+", command=self._lightbox_inc_copies,
            height=40, radius=10, pad_x=12, min_width=40,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], font_size=20,
            container_bg=PALETTE["surface_elevated"]
        )
        btn_lb_cplus.pack(side=tk.LEFT, padx=3, pady=3)

        btn_lb_next = RoundedButton(
            lb_bot_inner, text="Next ▶", command=self.lightbox_next_photo,
            height=46, radius=13, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["lightbox_bar"]
        )
        btn_lb_next.pack(side=tk.RIGHT, padx=4)

        btn_lb_prev = RoundedButton(
            lb_bot_inner, text="◀ Prev", command=self.lightbox_prev_photo,
            height=46, radius=13, pad_x=14, font_size=15,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["lightbox_bar"]
        )
        btn_lb_prev.pack(side=tk.RIGHT, padx=4)

        # Center High-Resolution Canvas in Lightbox
        self.lightbox_canvas = tk.Canvas(
            self.lightbox_frame, bg=PALETTE["lightbox_bg"], highlightthickness=0, cursor="fleur"
        )
        self.lightbox_canvas.pack(fill=tk.BOTH, expand=True)
        self.lightbox_canvas.bind("<Configure>", lambda e: self._render_lightbox_image())
        self.lightbox_canvas.bind("<ButtonPress-1>", self._on_lightbox_press)
        self.lightbox_canvas.bind("<B1-Motion>", self._on_lightbox_drag)
        self.lightbox_canvas.bind("<ButtonRelease-1>", self._on_lightbox_release)

    def open_lightbox(self, card):
        self.lightbox_card = card
        self.lightbox_zoom = 1.0
        self.lightbox_pan_x = 0.0
        self.lightbox_pan_y = 0.0
        self.lightbox_frame.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        self.lightbox_frame.tkraise()
        self._sync_lightbox_ui()
        self._render_lightbox_image()

    def close_lightbox(self, event=None):
        if self.lightbox_card is not None:
            self.lightbox_card = None
            self.lightbox_frame.place_forget()

    def _sync_lightbox_ui(self):
        card = self.lightbox_card
        if not card:
            return
        total = len(self.active_cards)
        fname = os.path.basename(card.photo_path)
        w, h = card.pil_img.size if card.pil_img else (0, 0)
        self.lbl_lb_title.config(
            text=f"📸 Shot #{card.shot_index} of {total}  —  {fname} ({w}×{h} px)"
        )

        if card.selected:
            self.btn_lb_select.set_colors(
                PALETTE["accent_green"], PALETTE["accent_green_hover"], PALETTE["accent_green_active"]
            )
            self.btn_lb_select.set_text("✓ SELECTED FOR PRINT", resize_if_needed=True)
        else:
            self.btn_lb_select.set_colors(
                PALETTE["accent_charcoal"], PALETTE["accent_charcoal_hover"], PALETTE["accent_charcoal_active"]
            )
            self.btn_lb_select.set_text("✕ SKIPPED (Click to Select)", resize_if_needed=True)

        unit = "Copy" if card.copies == 1 else "Copies"
        self.lbl_lb_copies.config(text=f"{card.copies} {unit}")
        self.btn_lb_print.set_text(f"🖨️ Print This ({card.copies}x)", resize_if_needed=True)

        if self.frame_templates:
            self.btn_lb_frame.pack(side=tk.LEFT, padx=6)
            if card.use_frame:
                self.btn_lb_frame.set_colors(
                    PALETTE["accent_purple"], PALETTE["accent_purple_hover"], PALETTE["accent_purple_active"]
                )
                self.btn_lb_frame.set_text("🖼️ Frame: ON", resize_if_needed=True)
                if len(self.frame_templates) > 1:
                    self.btn_lb_next_frame.pack(side=tk.LEFT, padx=4)
                    t_idx = getattr(card, "frame_index", 0)
                    if not (0 <= t_idx < len(self.frame_templates)):
                        t_idx = 0
                    raw_t = os.path.splitext(os.path.basename(self.frame_templates[t_idx]))[0]
                    clean_t = raw_t[3:] if len(raw_t) > 3 and raw_t[:2].isdigit() and raw_t[2] in ('_', '-') else raw_t
                    clean_t = clean_t.replace('_', ' ')
                    self.btn_lb_next_frame.set_text(f"Template: {clean_t} ▶ ({t_idx + 1}/{len(self.frame_templates)})", resize_if_needed=True)
                else:
                    self.btn_lb_next_frame.pack_forget()
            else:
                self.btn_lb_frame.set_colors(
                    PALETTE["accent_charcoal"], PALETTE["accent_charcoal_hover"], PALETTE["accent_charcoal_active"]
                )
                self.btn_lb_frame.set_text("🖼️ Frame: OFF", resize_if_needed=True)
                self.btn_lb_next_frame.pack_forget()
        else:
            self.btn_lb_frame.pack_forget()
            self.btn_lb_next_frame.pack_forget()

        z_pct = int(round(self.lightbox_zoom * 100))
        self.lbl_lb_zoom.config(text=f"🔍 Fit (100%)" if z_pct == 100 else f"🔍 {z_pct}%")

    def _lightbox_toggle_frame(self):
        if self.lightbox_card:
            self.lightbox_card.toggle_frame()
            self._sync_lightbox_ui()
            self._render_lightbox_image()

    def _lightbox_next_frame(self):
        if self.lightbox_card:
            self.lightbox_card.next_template()
            self._sync_lightbox_ui()
            self._render_lightbox_image()

    def _render_lightbox_image(self):
        card = self.lightbox_card
        if not card or not card.pil_img:
            return
        c_w = self.lightbox_canvas.winfo_width()
        c_h = self.lightbox_canvas.winfo_height()
        if c_w < 100 or c_h < 100:
            c_w, c_h = 1280, 740

        img = card.pil_img
        if card.rotation % 360 != 0:
            img = img.rotate(-card.rotation, expand=True)

        # Show frame overlay in full-screen Lightbox if active for this photo
        if card.use_frame:
            frame_img = self._get_card_frame_image(card)
            if frame_img is not None:
                img = printer_service.compose_with_frame(img, frame_img)

        w, h = img.size
        base_scale = min((c_w - 40) / w, (c_h - 30) / h)
        fit_w = max(1, int(w * base_scale))
        fit_h = max(1, int(h * base_scale))

        if self.lightbox_zoom <= 1.01:
            # Fit entire image cleanly inside the Lightbox viewport
            crisp = render_crisp_preview(img, fit_w, fit_h, dimmed=False)
            self.lightbox_tk_img = ImageTk.PhotoImage(crisp)
            self.lightbox_canvas.delete("all")
            self._lb_img_bbox = (
                (c_w - fit_w) // 2, (c_h - fit_h) // 2,
                (c_w + fit_w) // 2, (c_h + fit_h) // 2
            )
            self.lightbox_canvas.create_image(c_w // 2, c_h // 2, image=self.lightbox_tk_img, anchor=tk.CENTER)
        else:
            # High-resolution zoomed crop directly from full 3000x2000 source image!
            view_w_src = w / self.lightbox_zoom
            view_h_src = h / self.lightbox_zoom
            max_pan_x = max(0.0, (w - view_w_src) / 2.0)
            max_pan_y = max(0.0, (h - view_h_src) / 2.0)
            self.lightbox_pan_x = max(-max_pan_x, min(max_pan_x, self.lightbox_pan_x))
            self.lightbox_pan_y = max(-max_pan_y, min(max_pan_y, self.lightbox_pan_y))

            cx_src = w / 2.0 - self.lightbox_pan_x
            cy_src = h / 2.0 - self.lightbox_pan_y
            x0 = max(0, int(cx_src - view_w_src / 2.0))
            y0 = max(0, int(cy_src - view_h_src / 2.0))
            x1 = min(w, int(cx_src + view_w_src / 2.0))
            y1 = min(h, int(cy_src + view_h_src / 2.0))

            cropped = img.crop((x0, y0, x1, y1))
            disp_w = min(c_w - 20, int(fit_w * self.lightbox_zoom))
            disp_h = min(c_h - 20, int(fit_h * self.lightbox_zoom))
            # Maintain aspect ratio of cropped region
            crop_scale = min(disp_w / max(1, x1 - x0), disp_h / max(1, y1 - y0))
            final_w = max(1, int((x1 - x0) * crop_scale))
            final_h = max(1, int((y1 - y0) * crop_scale))

            crisp = render_crisp_preview(cropped, final_w, final_h, dimmed=False)
            self.lightbox_tk_img = ImageTk.PhotoImage(crisp)
            self.lightbox_canvas.delete("all")
            self._lb_img_bbox = (
                (c_w - final_w) // 2, (c_h - final_h) // 2,
                (c_w + final_w) // 2, (c_h + final_h) // 2
            )
            self.lightbox_canvas.create_image(c_w // 2, c_h // 2, image=self.lightbox_tk_img, anchor=tk.CENTER)

    def _on_lightbox_press(self, event):
        # If user clicks on the dark backdrop outside the image when at 100% zoom, close Lightbox (like Google Drive!)
        bbox = getattr(self, "_lb_img_bbox", None)
        if self.lightbox_zoom <= 1.01 and bbox:
            x0, y0, x1, y1 = bbox
            if not (x0 <= event.x <= x1 and y0 <= event.y <= y1):
                self.close_lightbox()
                return
        self._drag_start = (event.x, event.y, self.lightbox_pan_x, self.lightbox_pan_y)

    def _on_lightbox_drag(self, event):
        if not self._drag_start or self.lightbox_zoom <= 1.01 or not self.lightbox_card:
            return
        sx, sy, spx, spy = self._drag_start
        dx = event.x - sx
        dy = event.y - sy
        # Convert screen pixel drag to source image coordinates
        scale_factor = 2.5 / self.lightbox_zoom
        self.lightbox_pan_x = spx + dx * scale_factor
        self.lightbox_pan_y = spy + dy * scale_factor
        self._render_lightbox_image()

    def _on_lightbox_release(self, event):
        self._drag_start = None

    def lightbox_zoom_in(self):
        if not self.lightbox_card:
            return
        self.lightbox_zoom = min(4.0, round(self.lightbox_zoom + 0.5, 2))
        self._sync_lightbox_ui()
        self._render_lightbox_image()

    def lightbox_zoom_out(self):
        if not self.lightbox_card:
            return
        self.lightbox_zoom = max(1.0, round(self.lightbox_zoom - 0.5, 2))
        if self.lightbox_zoom <= 1.01:
            self.lightbox_pan_x = 0.0
            self.lightbox_pan_y = 0.0
        self._sync_lightbox_ui()
        self._render_lightbox_image()

    def lightbox_zoom_reset(self):
        if not self.lightbox_card:
            return
        self.lightbox_zoom = 1.0
        self.lightbox_pan_x = 0.0
        self.lightbox_pan_y = 0.0
        self._sync_lightbox_ui()
        self._render_lightbox_image()

    def lightbox_prev_photo(self, event=None):
        if not self.lightbox_card or not self.active_cards:
            return
        idx = self.active_cards.index(self.lightbox_card)
        new_idx = (idx - 1) % len(self.active_cards)
        self.open_lightbox(self.active_cards[new_idx])

    def lightbox_next_photo(self, event=None):
        if not self.lightbox_card or not self.active_cards:
            return
        idx = self.active_cards.index(self.lightbox_card)
        new_idx = (idx + 1) % len(self.active_cards)
        self.open_lightbox(self.active_cards[new_idx])

    def _lightbox_toggle_select(self):
        if self.lightbox_card:
            self.lightbox_card.toggle_selection()
            self._sync_lightbox_ui()

    def _lightbox_rotate(self):
        if self.lightbox_card:
            self.lightbox_card.rotate_photo()
            self._render_lightbox_image()

    def _lightbox_inc_copies(self):
        if self.lightbox_card:
            self.lightbox_card.increment_copies()
            self._sync_lightbox_ui()

    def _lightbox_dec_copies(self):
        if self.lightbox_card:
            self.lightbox_card.decrement_copies()
            self._sync_lightbox_ui()

    def _on_cards_grid_configure(self, event=None):
        bbox = self.gallery_canvas.bbox("all")
        if bbox:
            self.gallery_canvas.configure(scrollregion=bbox)
        self._update_scrollbar_visibility()

    def _on_canvas_configure(self, event):
        self.gallery_canvas.itemconfig(self.canvas_win_id, width=event.width)
        self._update_scrollbar_visibility()

    def _is_scroll_needed(self):
        if not self.gallery_canvas.winfo_ismapped():
            return False
        bbox = self.gallery_canvas.bbox("all")
        if not bbox:
            return False
        content_h = bbox[3] - bbox[1]
        canvas_h = self.gallery_canvas.winfo_height()
        return content_h > (canvas_h + 12)

    def _update_scrollbar_visibility(self):
        if not self.gallery_canvas.winfo_ismapped():
            return
        if self._is_scroll_needed():
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()
            self.gallery_canvas.yview_moveto(0.0)

    def _on_mousewheel(self, event):
        if not event.delta:
            return

        # Check if Command (Mod1: 0x08/0x10) or Control (0x04) is held -> Zoom!
        is_cmd_or_ctrl = bool(event.state & (0x0004 | 0x0008 | 0x0010))

        if self.lightbox_card is not None:
            # Inside Google Drive Lightbox: Scroll or Cmd+Scroll zooms in/out smoothly!
            now = time.time()
            if now - self._last_zoom_scroll_time >= 0.08:
                self._last_zoom_scroll_time = now
                if event.delta > 0:
                    self.lightbox_zoom_in()
                else:
                    self.lightbox_zoom_out()
            return

        if is_cmd_or_ctrl:
            now = time.time()
            if now - self._last_zoom_scroll_time >= 0.16:
                self._last_zoom_scroll_time = now
                if event.delta > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
            return

        # Normal vertical scrolling in the gallery
        if not self._is_scroll_needed():
            return
        # On Windows, mouse wheel delta is typically ±120. Normalize for smooth scrolling:
        norm_delta = (event.delta / 120.0) if abs(event.delta) >= 60 else event.delta
        step_px = int(-1 * norm_delta * 3)
        if step_px == 0:
            step_px = -1 if event.delta > 0 else 1
        self.gallery_canvas.yview_scroll(step_px, "units")

    def _build_bottom_bar(self):
        bottom_bar = tk.Frame(
            self.root, bg=PALETTE["surface_bg"],
            highlightthickness=1, highlightbackground=PALETTE["surface_border"]
        )
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(6, 14))

        self.lbl_status = tk.Label(
            bottom_bar,
            text=f"✨ Ready — {MOD_KEY_HINT}+Scroll or [−/+] to Zoom Grid • Click '🔍 Preview' on any photo for Full-Screen View",
            font=font_bold(14), fg=PALETTE["text_secondary"], bg=PALETTE["surface_bg"], anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, side=tk.TOP, padx=18, pady=(10, 2))

        action_row = tk.Frame(bottom_bar, bg=PALETTE["surface_bg"])
        action_row.pack(fill=tk.X, side=tk.BOTTOM, padx=18, pady=(6, 12))

        self.lbl_summary = tk.Label(
            action_row, text="Session: Waiting for photos…", font=font_bold(18),
            fg=PALETTE["text_primary"], bg=PALETTE["surface_bg"]
        )
        self.lbl_summary.pack(side=tk.LEFT, padx=2)

        self.btn_done = RoundedButton(
            action_row, text="✨ Next Group / Clear [C]", command=self.clear_session_batch,
            height=52, radius=15, pad_x=20, font_size=18,
            bg_hex=PALETTE["accent_charcoal"], hover_hex=PALETTE["accent_charcoal_hover"],
            active_hex=PALETTE["accent_charcoal_active"], container_bg=PALETTE["surface_bg"]
        )
        self.btn_done.pack(side=tk.RIGHT, padx=6)

        self.btn_print_all = RoundedButton(
            action_row, text="🖨️ Print All (1 Each)", command=self.print_all_photos,
            height=52, radius=15, pad_x=20, font_size=18,
            bg_hex=PALETTE["accent_green"], hover_hex=PALETTE["accent_green_hover"],
            active_hex=PALETTE["accent_green_active"], container_bg=PALETTE["surface_bg"]
        )
        self.btn_print_all.pack(side=tk.RIGHT, padx=6)

        self.btn_print_selected = RoundedButton(
            action_row, text="🖨️ Print Selected [Enter]", command=self.print_selected_photos,
            height=52, radius=15, pad_x=22, font_size=19,
            bg_hex=PALETTE["accent_blue"], hover_hex=PALETTE["accent_blue_hover"],
            active_hex=PALETTE["accent_blue_active"], container_bg=PALETTE["surface_bg"]
        )
        self.btn_print_selected.pack(side=tk.RIGHT, padx=6)

    def _bind_shortcuts(self):
        self.root.bind("<Return>", lambda e: self.print_selected_photos())
        self.root.bind("c", lambda e: self.clear_session_batch())
        self.root.bind("C", lambda e: self.clear_session_batch())
        self.root.bind("<Escape>", self.close_lightbox)
        self.root.bind("<Left>", self.lightbox_prev_photo)
        self.root.bind("<Right>", self.lightbox_next_photo)
        # Keyboard Zoom shortcuts (Cmd/Ctrl + Plus/Minus/0)
        for seq in ("<Command-equal>", "<Command-plus>", "<Control-equal>", "<Control-plus>"):
            self.root.bind(seq, lambda e: self.zoom_in())
        for seq in ("<Command-minus>", "<Control-minus>"):
            self.root.bind(seq, lambda e: self.zoom_out())
        for seq in ("<Command-0>", "<Control-0>"):
            self.root.bind(seq, lambda e: self.zoom_reset())
        # Quick circular frame template cycle with 'f'
        self.root.bind("f", lambda e: self.next_frame_template())
        self.root.bind("F", lambda e: self.next_frame_template())

    def update_printer_status(self):
        def check():
            status, msg = printer_service.check_printer_status()
            color = PALETTE["accent_green"] if status == "ready" else (PALETTE["accent_amber_text"] if status == "offline" else PALETTE["accent_red"])
            status_text = f"● SELPHY: {status.upper()}"
            try:
                self.root.after(0, lambda: self.lbl_printer.config(text=status_text, fg=color))
                self.root.after(8000, self.update_printer_status)
            except (tk.TclError, RuntimeError, AttributeError):
                pass

        threading.Thread(target=check, daemon=True).start()

    def _init_frame_templates(self):
        """Initializes multi-template system from saved config or default sample_frames."""
        saved_folder = None
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            if os.path.isfile(cfg_path):
                import json
                with open(cfg_path, "r") as f:
                    saved_folder = json.load(f).get("frames_folder")
        except Exception:
            pass

        if saved_folder:
            resolved = saved_folder if os.path.isabs(saved_folder) else os.path.join(os.path.dirname(os.path.abspath(__file__)), saved_folder)
            if os.path.isdir(resolved):
                if self.load_frames_from_folder(resolved, silent=True):
                    return

        # Try default sample_frames directory in app folder
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_frames")
        if os.path.isdir(default_dir):
            if self.load_frames_from_folder(default_dir, silent=True):
                return

        # Fallback to single sample_frame.png if present
        single_sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_frame.png")
        if os.path.isfile(single_sample):
            self.frame_templates = [single_sample]
            self.frame_index = 0
            self._apply_active_frame()

    def _update_frame_ui(self):
        total = len(self.frame_templates)
        if total == 0:
            self.btn_frame_prev.pack_forget()
            self.btn_frame_next.pack_forget()
            self.btn_frame_active.pack(side=tk.LEFT, padx=3, pady=2)
            self.btn_frame_active.set_colors(
                PALETTE["accent_charcoal"], PALETTE["accent_charcoal_hover"], PALETTE["accent_charcoal_active"]
            )
            self.btn_frame_active.set_text("🖼️ Frame: None", resize_if_needed=True)
            self.frame_path = None
            self.frame_img = None
        else:
            if total > 1:
                self.btn_frame_prev.pack(side=tk.LEFT, padx=(2, 1), pady=2)
                self.btn_frame_active.pack(side=tk.LEFT, padx=1, pady=2)
                self.btn_frame_next.pack(side=tk.LEFT, padx=(1, 2), pady=2)
            else:
                self.btn_frame_prev.pack_forget()
                self.btn_frame_next.pack_forget()
                self.btn_frame_active.pack(side=tk.LEFT, padx=3, pady=2)

            if not (0 <= self.frame_index < total):
                self.frame_index = 0

            self.frame_path = self.frame_templates[self.frame_index]
            self.frame_img = self._get_frame_image_by_index(self.frame_index)

            raw_name = os.path.splitext(os.path.basename(self.frame_path))[0]
            clean_name = raw_name
            if len(clean_name) > 3 and clean_name[:2].isdigit() and clean_name[2] in ("_", "-", " "):
                clean_name = clean_name[3:]
            clean_name = clean_name.replace("_", " ")

            label_text = f"🖼️ {clean_name} ({self.frame_index + 1}/{total})" if total > 1 else f"🖼️ {clean_name}"
            self.btn_frame_active.set_colors(
                PALETTE["accent_purple"], PALETTE["accent_purple_hover"], PALETTE["accent_purple_active"]
            )
            self.btn_frame_active.set_text(label_text, resize_if_needed=True)

    def _get_frame_image_by_index(self, idx):
        if not self.frame_templates or not (0 <= idx < len(self.frame_templates)):
            return None
        path = self.frame_templates[idx]
        if path in self._frame_cache:
            return self._frame_cache[path]
        try:
            with Image.open(path) as f:
                img = f.convert("RGBA")
                self._frame_cache[path] = img
                return img
        except Exception as e:
            print(f"[Warning] Failed to load frame template '{path}': {e}")
            return None

    def _get_card_frame_image(self, card=None):
        if card is None:
            idx = self.frame_index if (0 <= self.frame_index < len(self.frame_templates)) else 0
            return self._get_frame_image_by_index(idx)
        if not getattr(card, "use_frame", True):
            return None
        idx = getattr(card, "frame_index", 0)
        return self._get_frame_image_by_index(idx)

    def _on_card_frame_changed(self, card):
        if self.lightbox_card == card:
            self._sync_lightbox_ui()
            self._render_lightbox_image()

    def apply_active_frame_to_all_cards(self):
        """Explicitly applies the currently active default frame template to all photos in the session."""
        if not self.frame_templates:
            return
        for card in self.active_cards:
            card.frame_index = self.frame_index
            card.use_frame = True
            card._composed = None
            card._thumb_cache.clear()
            card._update_frame_visual()
            card._render_thumbnail()
        if self.lightbox_card is not None:
            self._sync_lightbox_ui()
            self._render_lightbox_image()
        name = os.path.basename(self.frame_templates[self.frame_index]) if 0 <= self.frame_index < len(self.frame_templates) else ""
        self.lbl_status.config(text=f"🖼️ Applied frame '{name}' to all photos in session.")

    def _on_frame_button_clicked(self):
        """Dropdown menu to directly select template, choose folder, or disable frames."""
        if not self.frame_templates:
            self.select_frames_folder()
            return

        menu = tk.Menu(
            self.root, tearoff=0,
            bg=PALETTE["surface_elevated"], fg="#ffffff",
            activebackground=PALETTE["accent_purple"], activeforeground="#ffffff",
            font=font_bold(13)
        )
        menu.add_command(label="── Choose Default Template ──", state=tk.DISABLED)
        for idx, path in enumerate(self.frame_templates):
            name = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
            marker = "✓  " if idx == self.frame_index else "    "
            menu.add_command(
                label=f"{marker}{idx + 1}. {name}",
                command=lambda i=idx: self.set_frame_index(i)
            )
        menu.add_separator()
        if self.active_cards:
            menu.add_command(label="🔄 Apply Default Frame to All Current Photos", command=self.apply_active_frame_to_all_cards)
        menu.add_command(label="📁 Choose Different Frames Folder...", command=self.select_frames_folder)
        menu.add_command(label="📄 Select Specific Frame PNG(s)...", command=self.select_frame_files)
        menu.add_command(label="🚫 Disable Frames (No Overlay)", command=self.clear_frame_templates)

        x = self.btn_frame_active.winfo_rootx()
        y = self.btn_frame_active.winfo_rooty() + self.btn_frame_active.winfo_height() + 4
        menu.post(x, y)

    def next_frame_template(self):
        """Circular forward switch for default template: 1 -> 2 -> 3 -> 1."""
        if not self.frame_templates:
            self.select_frames_folder()
            return
        self.frame_index = (self.frame_index + 1) % len(self.frame_templates)
        self._update_frame_ui()
        if self.frame_path:
            name = os.path.basename(self.frame_path)
            self.lbl_status.config(
                text=f"🖼️ Default Frame: {name} ({self.frame_index + 1}/{len(self.frame_templates)}) — Click [◀/▶] or [f] to cycle."
            )

    def prev_frame_template(self):
        """Circular backward switch for default template: 1 -> 3 -> 2 -> 1."""
        if not self.frame_templates:
            self.select_frames_folder()
            return
        self.frame_index = (self.frame_index - 1) % len(self.frame_templates)
        self._update_frame_ui()
        if self.frame_path:
            name = os.path.basename(self.frame_path)
            self.lbl_status.config(
                text=f"🖼️ Default Frame: {name} ({self.frame_index + 1}/{len(self.frame_templates)}) — Click [◀/▶] or [f] to cycle."
            )

    def set_frame_index(self, i):
        """Direct index selection from dropdown menu."""
        if 0 <= i < len(self.frame_templates):
            self.frame_index = i
            self._update_frame_ui()
            if self.frame_path:
                name = os.path.basename(self.frame_path)
                self.lbl_status.config(
                    text=f"🖼️ Default Frame: {name} ({self.frame_index + 1}/{len(self.frame_templates)})."
                )

    def select_frames_folder(self):
        initial = self.frames_folder or os.path.dirname(os.path.abspath(__file__))
        folder = filedialog.askdirectory(initialdir=initial, title="Select Frames Folder (containing .PNG templates)")
        if not folder:
            return
        self.load_frames_from_folder(folder)

    def select_frame_files(self):
        initial = self.frames_folder or os.path.dirname(os.path.abspath(__file__))
        files = filedialog.askopenfilenames(
            initialdir=initial,
            title="Select Frame PNG(s)",
            filetypes=[("PNG image", "*.png")]
        )
        if not files:
            return
        valid_files = [f for f in sorted(files) if not os.path.basename(f).startswith(".")]
        if valid_files:
            self._frame_cache.clear()
            self.frame_templates = valid_files
            self.frame_index = 0
            self.frames_folder = os.path.dirname(valid_files[0])
            self._update_frame_ui()
            self._save_frames_config()
            for card in self.active_cards:
                card.frame_index = 0
                card._composed = None
                card._thumb_cache.clear()
                card._update_frame_visual()
                card._render_thumbnail()
            if self.lightbox_card is not None:
                self._sync_lightbox_ui()
                self._render_lightbox_image()

    def load_frames_from_folder(self, folder, silent=False):
        if not os.path.isdir(folder):
            return False
        png_files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if not f.startswith(".") and f.lower().endswith(".png")
        ])
        if not png_files:
            if not silent:
                messagebox.showwarning(
                    "No PNG Frames Found",
                    f"No .png files were found in:\n{folder}\n\nPlease add transparent 100x148mm PNG frames to this folder."
                )
            return False
        self._frame_cache.clear()
        self.frame_templates = png_files
        self.frame_index = 0
        self.frames_folder = folder
        self._update_frame_ui()
        self._save_frames_config()
        self.lbl_status.config(text=f"🖼️ Loaded {len(png_files)} frame template(s) from {os.path.basename(folder)}.")
        for card in self.active_cards:
            card.frame_index = 0
            card._composed = None
            card._thumb_cache.clear()
            card._update_frame_visual()
            card._render_thumbnail()
        if self.lightbox_card is not None:
            self._sync_lightbox_ui()
            self._render_lightbox_image()
        return True

    def clear_frame_templates(self):
        self._frame_cache.clear()
        self.frame_templates = []
        self.frame_index = -1
        self.frame_path = None
        self.frame_img = None
        self.frames_folder = None
        self._update_frame_ui()
        self._save_frames_config()
        self.lbl_status.config(text="🖼️ Frames disabled. Photos will print without overlay.")
        for card in self.active_cards:
            card._composed = None
            card._thumb_cache.clear()
            card._update_frame_visual()
            card._render_thumbnail()
        if self.lightbox_card is not None:
            self._sync_lightbox_ui()
            self._render_lightbox_image()

    def _apply_active_frame(self):
        self._update_frame_ui()
        if self.frame_path:
            name = os.path.basename(self.frame_path)
            self.lbl_status.config(
                text=f"🖼️ Default Frame: {name} ({self.frame_index + 1}/{len(self.frame_templates)}) — Click [◀/▶] or [f] to cycle."
            )
        for card in self.active_cards:
            card._composed = None
            card._thumb_cache.clear()
            card._render_thumbnail()
        if self.lightbox_card is not None:
            self._sync_lightbox_ui()
            self._render_lightbox_image()

    def _save_frames_config(self):
        try:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            cfg_path = os.path.join(app_dir, "config.json")
            if os.path.isfile(cfg_path):
                import json
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
                save_val = self.frames_folder
                if save_val:
                    try:
                        if os.path.commonpath([app_dir, save_val]) == app_dir:
                            save_val = os.path.relpath(save_val, app_dir)
                    except ValueError:
                        pass
                cfg["frames_folder"] = save_val
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def select_frame(self):
        """Legacy entry point / alias."""
        self._on_frame_button_clicked()

    def _frame_for(self, card):
        if not getattr(card, "use_frame", True) or not self.frame_templates:
            return None
        idx = getattr(card, "frame_index", 0)
        if 0 <= idx < len(self.frame_templates):
            return self.frame_templates[idx]
        return self.frame_templates[0]

    def select_folder(self):
        folder = filedialog.askdirectory(initialdir=self.watch_folder, title="Select Sony Imaging Edge Save Folder")
        if folder:
            self.watch_folder = folder
            self.lbl_folder.config(text=self._format_short_path(folder))
            self.watcher.update_folder(folder)

    def on_new_photo_detected(self, photo_path):
        if photo_path in self.processed_files:
            return
        try:
            self.root.after(0, lambda: self._add_photo_to_active_batch(photo_path))
        except (tk.TclError, RuntimeError, AttributeError):
            pass

    def _add_photo_to_active_batch(self, photo_path):
        if any(c.photo_path == photo_path for c in self.active_cards):
            return

        self.standby_frame.pack_forget()
        if not self.gallery_canvas.winfo_ismapped():
            self.gallery_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        _, _, c_height = GRID_ZOOM_PRESETS[self.zoom_idx]
        shot_num = len(self.active_cards) + 1
        card = PhotoCard(
            self.cards_grid, photo_path, shot_index=shot_num,
            on_toggle_select=self._update_summary,
            on_print_single=self._print_single_card,
            on_open_preview=self.open_lightbox,
            canvas_height=c_height,
            get_frame=self._get_card_frame_image,
            frame_index=self.frame_index if (0 <= self.frame_index < len(self.frame_templates)) else 0,
            get_frame_templates=lambda: self.frame_templates,
            on_frame_change=self._on_card_frame_changed
        )
        self.active_cards.append(card)
        self._rearrange_cards_grid(scroll_to_bottom=True)
        self._update_summary()

    def _rearrange_cards_grid(self, scroll_to_bottom=False):
        """Lays out cards according to the active zoom column count (snaps between 3, 2, or 1 per row)."""
        count = len(self.active_cards)
        _, max_cols, _ = GRID_ZOOM_PRESETS[self.zoom_idx]
        cols = min(max_cols, max(1, count))

        for c_idx in range(4):
            self.cards_grid.grid_columnconfigure(c_idx, weight=0, uniform="")

        for i, card in enumerate(self.active_cards):
            card.grid_forget()
            r = i // cols
            c = i % cols
            card.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            self.cards_grid.grid_columnconfigure(c, weight=1, uniform="card_col")
            self.cards_grid.grid_rowconfigure(r, weight=0)

        def refresh_scroll():
            self._on_cards_grid_configure()
            if scroll_to_bottom and count > cols:
                self.gallery_canvas.yview_moveto(1.0)

        self.root.after(50, refresh_scroll)

    def _update_summary(self):
        total_photos = len(self.active_cards)
        selected_cards = [c for c in self.active_cards if c.selected]
        selected_count = len(selected_cards)
        total_copies = sum(c.copies for c in selected_cards)

        if self.lightbox_card is not None:
            self._sync_lightbox_ui()

        if total_photos == 0:
            self.lbl_summary.config(text="Session: Waiting for photos…")
            self.btn_print_selected.set_text("🖨️ Print Selected [Enter]", resize_if_needed=True)
            return

        p_word = "Photo" if total_photos == 1 else "Photos"
        c_word = "Print" if total_copies == 1 else "Prints"
        self.lbl_summary.config(
            text=f"📸 {total_photos} {p_word}  •  {selected_count} Selected ({total_copies} Total {c_word})"
        )
        if total_copies > 0:
            self.btn_print_selected.set_text(
                f"🖨️ Print Selected ({total_copies} {c_word}) [Enter]", resize_if_needed=True
            )
            self.btn_print_selected.set_enabled(True)
        else:
            self.btn_print_selected.set_text("🖨️ No Photos Selected", resize_if_needed=True)
            self.btn_print_selected.set_enabled(False)

    def clear_session_batch(self):
        self.close_lightbox()
        for card in self.active_cards:
            self.processed_files.add(card.photo_path)
            card.destroy()

        self.active_cards.clear()
        self.gallery_canvas.yview_moveto(0.0)
        self.scrollbar.pack_forget()
        self.gallery_canvas.pack_forget()
        self.standby_frame.pack(fill=tk.BOTH, expand=True, pady=6)

        self.lbl_status.config(
            text="✨ Session completed and feed cleared. Ready for next guests!"
        )
        self._update_summary()

    def _print_single_card(self, card):
        if not card:
            return
        fname = os.path.basename(card.photo_path)
        dry = self.dry_run.get()
        copies = card.copies
        rot = card.rotation
        frame = self._frame_for(card)

        self.lbl_status.config(text=f"⏳ Spooling {copies}x {fname} to Canon SELPHY CP1500...")
        self.root.update_idletasks()

        def worker():
            success, msg = printer_service.print_photo(
                card.photo_path, copies=copies, dry_run=dry, rotation=rot, frame_path=frame
            )
            self.root.after(0, lambda: self._on_print_finished(success, msg, fname, copies, dry))

        threading.Thread(target=worker, daemon=True).start()

    def print_selected_photos(self):
        selected_cards = [c for c in self.active_cards if c.selected]
        if not selected_cards:
            messagebox.showinfo("No Photos Selected", "Click on at least one photo card to select it for printing!")
            return

        dry = self.dry_run.get()
        total_prints = sum(c.copies for c in selected_cards)
        self.lbl_status.config(
            text=f"⏳ Spooling {len(selected_cards)} selected photo(s) ({total_prints} total prints) to Canon SELPHY..."
        )
        self.root.update_idletasks()

        def worker():
            results = []
            for card in selected_cards:
                fname = os.path.basename(card.photo_path)
                success, msg = printer_service.print_photo(
                    card.photo_path, copies=card.copies, dry_run=dry, rotation=card.rotation,
                    frame_path=self._frame_for(card)
                )
                results.append((success, fname, card.copies, msg))

            self.root.after(0, lambda: self._on_batch_print_finished(results, dry))

        threading.Thread(target=worker, daemon=True).start()

    def print_all_photos(self):
        if not self.active_cards:
            messagebox.showinfo("No Photos Yet", "There are no photos in the current session yet.")
            return
        for card in self.active_cards:
            card.selected = True
            card.copies = 1
            card._sync_copy_labels()
            card.update_selection_visual()
            card._render_thumbnail()
        self._update_summary()
        self.print_selected_photos()

    def _on_print_finished(self, success, msg, fname, copies, dry):
        tag = "[TEST DRY-RUN] " if dry else "✅ "
        if success:
            self.lbl_status.config(text=f"{tag}{msg}")
        else:
            self.lbl_status.config(text=f"❌ Print Failed: {msg}")
            messagebox.showerror("Print Failed", f"Could not print {fname}:\n\n{msg}")

    def _on_batch_print_finished(self, results, dry):
        tag = "[TEST DRY-RUN] " if dry else "✅ "
        succeeded = [(fname, c, m) for s, fname, c, m in results if s]
        failed = [(fname, m) for s, fname, c, m in results if not s]

        if succeeded and not failed:
            total_prints = sum(c for fname, c, m in succeeded)
            summary_parts = [f"{fname} ({c}x)" for fname, c, m in succeeded]
            self.lbl_status.config(
                text=f"{tag}Queued {len(succeeded)} photo(s) ({total_prints} total prints): {', '.join(summary_parts)}"
            )
        elif failed:
            self.lbl_status.config(text=f"⚠️ Batch finished with {len(failed)} error(s).")
            err_msg = "\n".join([f"{fn}: {err}" for fn, err in failed])
            messagebox.showwarning("Print Issues", f"Some photos failed to print:\n\n{err_msg}")

    def open_queue_window(self):
        printer_service.open_windows_print_queue()
        queue_text = printer_service.get_print_queue_status()
        first_line = queue_text.splitlines()[0] if queue_text else "Queue is empty."
        self.lbl_status.config(text=f"📋 Windows Print Queue: {first_line}")

    def simulate_batch(self):
        self.lbl_status.config(text="📸 Simulating 3 camera shots arriving from Sony Imaging Edge...")
        def worker():
            simulate_shots.simulate_camera_session(self.watch_folder, count=3, delay=0.4)
        threading.Thread(target=worker, daemon=True).start()


def launch_gui(watch_folder=None, dry_run=False):
    root = tk.Tk()
    app = PhotoBoothApp(root, watch_folder=watch_folder, dry_run=dry_run)
    root.mainloop()


if __name__ == "__main__":
    launch_gui(dry_run=True)
