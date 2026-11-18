from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ..camera import Camera, render_frame
from ..config import APP_TITLE, FRAME_DELAY_MS, MAX_READ_FAILURES
from ..models import CameraInfo
from .dialogs import BLUE, build_header
from .widgets import Card, CameraView


class CameraPreviewDialog(tk.Toplevel):
    """Video en vivo de UNA cámara, con su nombre encima, para saber cuál está grabando."""

    def __init__(
        self,
        parent: tk.Misc,
        info: CameraInfo,
        camera: Camera,
        on_use: Callable[[CameraInfo], None],
    ) -> None:
        super().__init__(parent)
        self.title("Probar cámara")
        self.configure(bg="#EEF2F6")
        self.resizable(False, False)
        self._info = info
        self._camera = camera
        self._on_use = on_use
        self._closed = False
        self._failures = 0
        self._loop_id: str | None = None
        build_header(self, "Probar cámara", info.name).pack(fill="x")
        card = Card(self, padding=14)
        card.pack(padx=16, pady=16)
        self._view = CameraView(card.body, "Iniciando cámara…")
        self._view.pack()
        ttk.Label(
            card.body,
            text=f"Si ve su imagen aquí, esta es la cámara que está grabando:\n{info.name}",
            style="Hint.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(10, 8))
        buttons = ttk.Frame(card.body, style="Card.TFrame")
        buttons.pack(fill="x")
        ttk.Button(
            buttons, text="✔  Usar esta cámara", style="Primary.TButton", command=self._use
        ).pack(side="left")
        ttk.Button(buttons, text="Cerrar", style="Ghost.TButton", command=self._close).pack(
            side="left", padx=8
        )
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._loop()

    def _loop(self) -> None:
        if self._closed:
            return
        frame = self._camera.read()
        if frame is None:
            self._failures += 1
            if self._failures >= MAX_READ_FAILURES:
                self._close()
                messagebox.showerror(
                    APP_TITLE, f"La cámara «{self._info.name}» dejó de enviar imagen."
                )
                return
        else:
            self._failures = 0
            self._view.show(render_frame(frame, (), (self._info.name, BLUE)))
        self._loop_id = self.after(FRAME_DELAY_MS, self._loop)

    def _use(self) -> None:
        self._on_use(self._info)
        self._close()

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop_id is not None:
            self.after_cancel(self._loop_id)
            self._loop_id = None
        self._camera.release()
        self.grab_release()
        self.destroy()
