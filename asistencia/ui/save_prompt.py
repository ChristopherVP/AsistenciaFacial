from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_MUTED,
    COLOR_SUCCESS,
    COLOR_TEXT,
    FONT_FAMILY,
)
from ..errors import AppError

WIDTH = 400
HEIGHT = 92
TOP_GAP = 78  # justo debajo del encabezado azul
SLIDE_FRAMES = 14
SLIDE_DELAY_MS = 16
AUTO_HIDE_MS = 15_000
RESULT_MS = 1_800


class SavePrompt(tk.Frame):
    """Aviso que se desliza desde arriba (estilo Google) para guardar el usuario.

    No es modal: no detiene nada. Se cierra solo, con «Ahora no» o con la ✕.
    `on_save` guarda el usuario y puede lanzar AppError si falla.
    """

    def __init__(self, root: tk.Misc, on_save: Callable[[], None]) -> None:
        super().__init__(
            root, bg="white", width=WIDTH, height=HEIGHT,
            highlightthickness=1, highlightbackground=COLOR_BORDER,
        )
        self.pack_propagate(False)
        self._on_save = on_save
        self._slide_job: str | None = None
        self._hide_job: str | None = None
        self._y = -HEIGHT
        self._title = tk.Label(
            self, text="🔑  ¿Guardar usuario?", bg="white", fg=COLOR_TEXT,
            font=(FONT_FAMILY, 11, "bold"), anchor="w",
        )
        self._title.pack(fill="x", padx=14, pady=(10, 0))
        self._detail = tk.Label(
            self, text="Entra con un solo clic la próxima vez. Puedes cambiarlo en Ajustes.",
            bg="white", fg=COLOR_MUTED, font=(FONT_FAMILY, 9), anchor="w",
            justify="left", wraplength=WIDTH - 60,
        )
        self._detail.pack(fill="x", padx=14)
        self._buttons = tk.Frame(self, bg="white")
        self._buttons.pack(side="bottom", anchor="e", padx=10, pady=(0, 8))
        self._button(self._buttons, "Ahora no", COLOR_ACCENT, "white", self.dismiss)
        self._button(self._buttons, "Guardar", "white", COLOR_ACCENT, self._save)
        close = tk.Label(self, text="✕", bg="white", fg=COLOR_MUTED, cursor="hand2", font=(FONT_FAMILY, 10))
        close.place(relx=1.0, x=-8, y=6, anchor="ne")
        close.bind("<Button-1>", lambda _event: self.dismiss())
        self._place_at(-HEIGHT)
        self.lift()
        self._slide(TOP_GAP, None)
        self._hide_job = self.after(AUTO_HIDE_MS, self.dismiss)

    @staticmethod
    def _button(parent: tk.Misc, text: str, bg: str, fg: str, command: Callable[[], None]) -> None:
        tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg, relief="flat", cursor="hand2",
            activebackground="#EAF2FB" if bg == "white" else "#1F6FA5", activeforeground=fg if bg == "white" else "white",
            font=(FONT_FAMILY, 10, "bold"), padx=14, pady=4, borderwidth=0,
        ).pack(side="right", padx=(6, 0))

    def _place_at(self, y: int) -> None:
        self._y = y
        self.place(relx=1.0, x=-20, y=y, anchor="ne")

    def _slide(self, target: int, done: Callable[[], None] | None) -> None:
        start = self._y

        def step(frame: int) -> None:
            self._slide_job = None
            progress = frame / SLIDE_FRAMES
            eased = 1 - (1 - progress) ** 3
            self._place_at(round(start + (target - start) * eased))
            if frame < SLIDE_FRAMES:
                self._slide_job = self.after(SLIDE_DELAY_MS, lambda: step(frame + 1))
            elif done is not None:
                done()

        step(0)

    def _cancel(self, job: str | None) -> None:
        if job is not None:
            self.after_cancel(job)

    def _save(self) -> None:
        self._cancel(self._hide_job)
        try:
            self._on_save()
        except AppError as error:
            self._show_result(f"⚠  No se pudo guardar: {error}", COLOR_MUTED)
            return
        self._show_result("✔  Usuario guardado", COLOR_SUCCESS)

    def _show_result(self, text: str, color: str) -> None:
        self._buttons.pack_forget()
        self._detail.pack_forget()
        self._title.configure(text=text, fg=color)
        self._hide_job = self.after(RESULT_MS, self.dismiss)

    def dismiss(self) -> None:
        self._cancel(self._hide_job)
        self._hide_job = None
        self._cancel(self._slide_job)
        self._slide(-HEIGHT - 4, self.destroy)

    def destroy(self) -> None:
        self._cancel(self._hide_job)
        self._cancel(self._slide_job)
        super().destroy()
