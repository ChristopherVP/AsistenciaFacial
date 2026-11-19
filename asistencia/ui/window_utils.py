from __future__ import annotations

import tkinter as tk


def maximize(window: tk.Misc) -> None:
    """Abre la ventana maximizada; el usuario decide si la minimiza o la reduce."""
    try:
        window.state("zoomed")
        return
    except tk.TclError:
        pass
    try:
        window.attributes("-zoomed", True)
    except tk.TclError:
        width, height = window.winfo_screenwidth(), window.winfo_screenheight()
        window.geometry(f"{width}x{height}+0+0")
