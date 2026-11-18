from __future__ import annotations

import ctypes
import sys
from pathlib import Path
import time as clock
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .config import (
    APP_ID,
    APP_TITLE,
    COLOR_PRIMARY,
    FONT_FAMILY,
    ICON_FILE,
)

WHITE = (255, 255, 255, 255)
PAPER = (234, 242, 248, 255)
NAVY = (31, 78, 121, 255)
LENS_OUTER = (46, 134, 193, 255)
LENS_INNER = (21, 50, 80, 255)
GREEN = (46, 139, 87, 255)
RED = (176, 58, 46, 255)


def make_logo(size: int = 256) -> Image.Image:
    scale = 4
    canvas = size * scale
    unit = canvas / 100
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, ...]:
        return (x0 * unit, y0 * unit, x1 * unit, y1 * unit)

    draw.rounded_rectangle(box(2, 2, 98, 98), radius=22 * unit, fill=NAVY)
    draw.rounded_rectangle(box(30, 24, 52, 38), radius=4 * unit, fill=PAPER)
    draw.rounded_rectangle(box(14, 32, 86, 76), radius=9 * unit, fill=PAPER)
    draw.ellipse(box(32, 37, 68, 73), fill=NAVY)
    draw.ellipse(box(37, 42, 63, 68), fill=LENS_OUTER)
    draw.ellipse(box(43, 48, 57, 62), fill=LENS_INNER)
    draw.ellipse(box(45, 49, 50, 54), fill=(255, 255, 255, 230))
    draw.ellipse(box(72, 38, 80, 46), fill=RED)
    draw.ellipse(box(62, 60, 94, 92), fill=GREEN, outline=WHITE, width=int(2.5 * unit))
    draw.line(
        [(70 * unit, 76 * unit), (76 * unit, 82 * unit), (87 * unit, 69 * unit)],
        fill=WHITE,
        width=int(4 * unit),
        joint="curve",
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def prepare_windows_identity() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError) as error:
        print(f"No se pudo registrar la identidad de la aplicación: {error}", file=sys.stderr)


def ensure_icon_file() -> Path | None:
    try:
        ICON_FILE.parent.mkdir(parents=True, exist_ok=True)
        make_logo(256).save(
            ICON_FILE,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    except OSError as error:
        print(f"No se pudo crear el icono: {error}", file=sys.stderr)
        return None
    return ICON_FILE


def install_icon(root: tk.Tk) -> ImageTk.PhotoImage:
    photo = ImageTk.PhotoImage(make_logo(64))
    root.iconphoto(True, photo)
    icon_path = ensure_icon_file()
    if icon_path is not None and sys.platform.startswith("win"):
        try:
            root.iconbitmap(default=str(icon_path))
        except tk.TclError as error:
            print(f"No se pudo aplicar el icono de ventana: {error}", file=sys.stderr)
    return photo


class Splash:
    WIDTH = 480
    HEIGHT = 300

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window = tk.Toplevel(root)
        self._window.overrideredirect(True)
        x = (root.winfo_screenwidth() - self.WIDTH) // 2
        y = (root.winfo_screenheight() - self.HEIGHT) // 3
        self._window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self._window.configure(bg=COLOR_PRIMARY)
        self._window.attributes("-topmost", True)
        self._logo = ImageTk.PhotoImage(make_logo(110))
        tk.Label(self._window, image=self._logo, bg=COLOR_PRIMARY).pack(pady=(26, 6))
        tk.Label(
            self._window,
            text=APP_TITLE,
            bg=COLOR_PRIMARY,
            fg="white",
            font=(FONT_FAMILY, 20, "bold"),
        ).pack()
        self._message_var = tk.StringVar(value="Iniciando…")
        tk.Label(
            self._window,
            textvariable=self._message_var,
            bg=COLOR_PRIMARY,
            fg="#D6EAF8",
            font=(FONT_FAMILY, 10),
        ).pack(pady=(10, 8))
        self._bar = ttk.Progressbar(
            self._window, style="Splash.Horizontal.TProgressbar", length=360, maximum=100
        )
        self._bar.pack()
        self._window.update()

    def report(self, message: str, fraction: float) -> None:
        self._message_var.set(message)
        self._bar["value"] = max(0.0, min(1.0, fraction)) * 100
        self._window.update()

    def hold(self, seconds: float) -> None:
        deadline = clock.monotonic() + seconds
        while clock.monotonic() < deadline:
            self._window.update()
            clock.sleep(0.02)

    def close(self) -> None:
        self._window.destroy()
