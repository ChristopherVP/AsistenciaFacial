from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from ..config import FONT_FAMILY, VIEW_HEIGHT, VIEW_WIDTH


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
