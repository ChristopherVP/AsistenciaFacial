from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import (
    COLOR_BG,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_SUCCESS,
    COLOR_TEXT,
    FONT_FAMILY,
)


def apply_theme(root: tk.Misc) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(FONT_FAMILY, 10), background=COLOR_BG)
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_CARD)
    style.configure("Card.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT)
    style.configure(
        "CardTitle.TLabel",
        background=COLOR_CARD,
        foreground=COLOR_PRIMARY,
        font=(FONT_FAMILY, 12, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=COLOR_CARD,
        foreground=COLOR_TEXT,
        font=(FONT_FAMILY, 15, "bold"),
    )
    style.configure("Hint.TLabel", background=COLOR_CARD, foreground=COLOR_MUTED)
    style.configure("Error.TLabel", background=COLOR_CARD, foreground=COLOR_DANGER)
    style.configure("Card.TCheckbutton", background=COLOR_CARD, foreground=COLOR_TEXT)
    style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(18, 8),
        font=(FONT_FAMILY, 10, "bold"),
        background="#D6DCE2",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_CARD)],
        foreground=[("selected", COLOR_PRIMARY)],
    )
    style.configure("TButton", padding=(12, 8), font=(FONT_FAMILY, 10))
    for name, color, hover in (
        ("Primary", COLOR_PRIMARY, COLOR_PRIMARY_DARK),
        ("Success", COLOR_SUCCESS, "#236B43"),
        ("Danger", COLOR_DANGER, "#8C2E24"),
    ):
        style.configure(
            f"{name}.TButton",
            background=color,
            foreground="white",
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            f"{name}.TButton",
            background=[("active", hover), ("disabled", "#B2BABB")],
            foreground=[("disabled", "#ECF0F1")],
        )
    style.configure("Treeview", rowheight=28, font=(FONT_FAMILY, 10))
    style.configure(
        "Treeview.Heading",
        font=(FONT_FAMILY, 10, "bold"),
        background=COLOR_PRIMARY,
        foreground="white",
    )
    style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor=COLOR_PRIMARY_DARK,
        background="#5DADE2",
        bordercolor=COLOR_PRIMARY_DARK,
        lightcolor="#5DADE2",
        darkcolor="#5DADE2",
    )
