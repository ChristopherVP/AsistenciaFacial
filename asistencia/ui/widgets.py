from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Sequence

from PIL import Image, ImageTk

from ..config import (
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_ZEBRA,
    FONT_FAMILY,
    VIEW_HEIGHT,
    VIEW_WIDTH,
)


class CameraView(tk.Frame):
    def __init__(self, parent: tk.Misc, placeholder: str) -> None:
        super().__init__(parent, width=VIEW_WIDTH, height=VIEW_HEIGHT, bg="#111111")
        self.pack_propagate(False)
        self._placeholder = placeholder
        self._photo: ImageTk.PhotoImage | None = None
        self._label = tk.Label(
            self,
            text=placeholder,
            bg="#111111",
            fg="#AAB7B8",
            font=(FONT_FAMILY, 13),
        )
        self._label.pack(fill="both", expand=True)

    def show(self, image: Image.Image) -> None:
        photo = ImageTk.PhotoImage(image)
        self._label.configure(image=photo, text="")
        self._photo = photo

    def clear(self) -> None:
        self._label.configure(image="", text=self._placeholder)
        self._photo = None


class Card(tk.Frame):
    def __init__(self, parent: tk.Misc, padding: int = 16) -> None:
        super().__init__(
            parent,
            bg=COLOR_CARD,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_BORDER,
        )
        self.body = ttk.Frame(self, style="Card.TFrame", padding=padding)
        self.body.pack(fill="both", expand=True)


def make_chip(parent: tk.Misc, text: str, color: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        bg=color,
        fg="white",
        font=(FONT_FAMILY, 9, "bold"),
        padx=10,
        pady=3,
    )


def set_chip(chip: tk.Label, text: str, color: str) -> None:
    chip.configure(text=text, bg=color)


class StatCard(tk.Frame):
    def __init__(self, parent: tk.Misc, caption: str, color: str) -> None:
        super().__init__(
            parent,
            bg=COLOR_CARD,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_BORDER,
        )
        self._value = tk.Label(
            self, text="–", bg=COLOR_CARD, fg=color, font=(FONT_FAMILY, 22, "bold")
        )
        self._value.pack(pady=(8, 0))
        self._caption = tk.Label(
            self, text=caption, bg=COLOR_CARD, fg=COLOR_MUTED, font=(FONT_FAMILY, 9)
        )
        self._caption.pack(pady=(0, 8))

    def set(self, value: str, caption: str | None = None) -> None:
        self._value.configure(text=value)
        if caption is not None:
            self._caption.configure(text=caption)


class Stepper(tk.Canvas):
    def __init__(self, parent: tk.Misc, steps: Sequence[str], width: int = 900) -> None:
        super().__init__(parent, width=width, height=70, bg=COLOR_CARD, highlightthickness=0)
        self._steps = tuple(steps)
        self._active = 0
        self.bind("<Configure>", lambda _event: self._draw())

    def set_active(self, index: int) -> None:
        self._active = index
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_width() if self.winfo_width() > 1 else int(self.cget("width"))
        slot = width / len(self._steps)
        for index, label in enumerate(self._steps):
            center = slot * (index + 0.5)
            if index < len(self._steps) - 1:
                done = index < self._active
                self.create_line(
                    center + 22,
                    24,
                    slot * (index + 1.5) - 22,
                    24,
                    fill=COLOR_SUCCESS if done else COLOR_BORDER,
                    width=3,
                )
            if index < self._active:
                fill, text = COLOR_SUCCESS, "✔"
            elif index == self._active:
                fill, text = COLOR_PRIMARY, str(index + 1)
            else:
                fill, text = "#C9D1DA", str(index + 1)
            self.create_oval(center - 17, 7, center + 17, 41, fill=fill, outline="")
            self.create_text(center, 24, text=text, fill="white", font=(FONT_FAMILY, 11, "bold"))
            self.create_text(
                center,
                56,
                text=label,
                fill=COLOR_TEXT if index <= self._active else COLOR_MUTED,
                font=(FONT_FAMILY, 9, "bold" if index == self._active else "normal"),
            )


class Table(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        columns: Sequence[tuple[str, str, int, str, bool]],
        height: int,
    ) -> None:
        super().__init__(parent, style="Card.TFrame")
        self.tree = ttk.Treeview(
            self,
            columns=[column[0] for column in columns],
            show="headings",
            height=height,
            selectmode="browse",
        )
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        for key, title, width, anchor, stretch in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor, stretch=stretch)
        self.tree.tag_configure("odd", background=COLOR_ZEBRA)
        self.tree.tag_configure("even", background=COLOR_CARD)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def tag(self, name: str, **options: str) -> None:
        self.tree.tag_configure(name, **options)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def add(self, values: Sequence[object], iid: str | None = None, tags: Sequence[str] = ()) -> None:
        zebra = "odd" if len(self.tree.get_children()) % 2 else "even"
        self.tree.insert("", "end", iid=iid, values=tuple(values), tags=(zebra, *tags))

    def selected(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def select(self, iid: str) -> None:
        self.tree.selection_set(iid)
