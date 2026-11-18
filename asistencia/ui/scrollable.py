from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import COLOR_BG


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._canvas = tk.Canvas(self, highlightthickness=0, bg=COLOR_BG)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.body = ttk.Frame(self._canvas)
        self._window = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_body_resize(self, _event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event: tk.Event) -> None:
        if not self.winfo_ismapped():
            return
        target = self.winfo_containing(event.x_root, event.y_root)
        while target is not None:
            if target is self:
                self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return
            target = target.master
