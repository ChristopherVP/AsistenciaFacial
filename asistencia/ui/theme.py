from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import (
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_SELECT,
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
        "Title.TLabel",
        background=COLOR_CARD,
        foreground=COLOR_TEXT,
        font=(FONT_FAMILY, 18, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=COLOR_CARD,
        foreground=COLOR_TEXT,
        font=(FONT_FAMILY, 14, "bold"),
    )
    style.configure(
        "Timer.TLabel",
        background=COLOR_CARD,
        foreground=COLOR_PRIMARY,
        font=(FONT_FAMILY, 26, "bold"),
    )
    style.configure("Hint.TLabel", background=COLOR_CARD, foreground=COLOR_MUTED)
    style.configure("Error.TLabel", background=COLOR_CARD, foreground=COLOR_DANGER)
    style.configure("Success.TLabel", background=COLOR_CARD, foreground=COLOR_SUCCESS)
    style.configure("Page.Success.TLabel", background=COLOR_BG, foreground=COLOR_SUCCESS, font=(FONT_FAMILY, 10, "bold"))
    style.configure("Card.TCheckbutton", background=COLOR_CARD, foreground=COLOR_TEXT)
    style.configure("Card.TRadiobutton", background=COLOR_CARD, foreground=COLOR_TEXT)
    style.configure("Info.TCheckbutton", background="#EAF2FB", foreground=COLOR_TEXT)
    style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(22, 10),
        font=(FONT_FAMILY, 10, "bold"),
        background="#D3DAE2",
        foreground=COLOR_MUTED,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_CARD)],
        foreground=[("selected", COLOR_PRIMARY)],
    )
    style.configure("TButton", padding=(14, 9), font=(FONT_FAMILY, 10), borderwidth=1)
    style.configure("Ghost.TButton", background=COLOR_CARD, foreground=COLOR_TEXT, bordercolor=COLOR_BORDER)
    style.map("Ghost.TButton", background=[("active", "#EEF2F6")])
    for name, color, hover in (
        ("Primary", COLOR_PRIMARY, COLOR_PRIMARY_DARK),
        ("Success", COLOR_SUCCESS, "#236B43"),
        ("Danger", COLOR_DANGER, "#8C2E24"),
    ):
        style.configure(
            f"{name}.TButton",
            background=color,
            foreground="white",
            bordercolor=color,
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            f"{name}.TButton",
            background=[("active", hover), ("disabled", "#B2BABB")],
            foreground=[("disabled", "#ECF0F1")],
        )
    style.configure(
        "Day.Toolbutton",
        background="#EEF2F6",
        foreground=COLOR_TEXT,
        padding=(12, 9),
        font=(FONT_FAMILY, 10, "bold"),
        borderwidth=1,
        bordercolor=COLOR_BORDER,
    )
    style.map(
        "Day.Toolbutton",
        background=[("selected", COLOR_PRIMARY), ("active", "#DCE6F0")],
        foreground=[("selected", "white")],
    )
    style.configure("Treeview", rowheight=30, font=(FONT_FAMILY, 10), borderwidth=0, background=COLOR_CARD)
    style.map(
        "Treeview",
        background=[("selected", COLOR_SELECT)],
        foreground=[("selected", COLOR_TEXT)],
    )
    style.configure(
        "Treeview.Heading",
        font=(FONT_FAMILY, 10, "bold"),
        background=COLOR_PRIMARY,
        foreground="white",
        relief="flat",
        padding=(8, 7),
    )
    style.map("Treeview.Heading", background=[("active", COLOR_PRIMARY_DARK)])
    style.configure("TEntry", padding=7)
    style.configure("TCombobox", padding=7)
    style.configure("TSpinbox", padding=6)
    style.configure(
        "Scan.Horizontal.TProgressbar",
        troughcolor="#DDE3EA",
        background="#00B8D9",
        bordercolor="#DDE3EA",
        lightcolor="#00B8D9",
        darkcolor="#00B8D9",
        thickness=12,
    )
    style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor=COLOR_PRIMARY_DARK,
        background="#5DADE2",
        bordercolor=COLOR_PRIMARY_DARK,
        lightcolor="#5DADE2",
        darkcolor="#5DADE2",
    )
