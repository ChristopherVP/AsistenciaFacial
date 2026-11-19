from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..config import (
    COLOR_ACCENT,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT,
    FONT_FAMILY,
)
from ..errors import AppError

WIDTH = 420
TOP_GAP = 80  # justo debajo del encabezado azul
SLIDE_FRAMES = 14
SLIDE_DELAY_MS = 16
AUTO_HIDE_MS = 15_000
RESULT_MS = 1_800
BORDER = "#C9D3DE"
HOVER_SOFT = "#E8F1FA"
HOVER_STRONG = "#1F6FA5"


class SavePrompt(tk.Frame):
    """Aviso que se desliza desde arriba (estilo Google) para guardar el usuario.

    No es modal: no detiene nada. Se cierra solo, con «Ahora no» o con la ✕.
    `on_save` guarda el usuario y puede lanzar AppError si falla.
    """

    def __init__(self, root: tk.Misc, on_save: Callable[[], None]) -> None:
        super().__init__(root, bg=BORDER)  # el marco de 1 px lo da este fondo
        self._on_save = on_save
        self._slide_job: str | None = None
        self._hide_job: str | None = None
        self._y = 0
        self._height = 0
        self._build()
        self.update_idletasks()
        self._height = self.winfo_reqheight()
        self._place_at(-self._height)
        self.lift()
        self._slide(TOP_GAP, None)
        self._hide_job = self.after(AUTO_HIDE_MS, self.dismiss)

    def _build(self) -> None:
        card = tk.Frame(self, bg="white")
        card.pack(padx=1, pady=1)
        tk.Frame(card, bg=COLOR_ACCENT, height=4, width=WIDTH).pack(fill="x")
        content = tk.Frame(card, bg="white")
        content.pack(fill="x", padx=16, pady=(12, 12))
        icon = tk.Canvas(content, width=44, height=44, bg="white", highlightthickness=0)
        icon.create_oval(2, 2, 42, 42, fill="#EAF2FB", outline="")
        icon.create_text(22, 22, text="🔑", font=(FONT_FAMILY, 15), fill=COLOR_PRIMARY)
        icon.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 12))
        self._title = tk.Label(
            content, text="¿Guardar usuario?", bg="white", fg=COLOR_TEXT,
            font=(FONT_FAMILY, 12, "bold"), anchor="w",
        )
        self._title.grid(row=0, column=1, sticky="w")
        self._detail = tk.Label(
            content, text="Entra con un solo clic la próxima vez.\nPuedes cambiarlo en Ajustes.",
            bg="white", fg=COLOR_MUTED, font=(FONT_FAMILY, 10), anchor="w", justify="left",
        )
        self._detail.grid(row=1, column=1, sticky="w", pady=(2, 0))
        close = tk.Label(content, text="✕", bg="white", fg=COLOR_MUTED, cursor="hand2", font=(FONT_FAMILY, 11))
        close.grid(row=0, column=2, sticky="ne", padx=(10, 0))
        close.bind("<Button-1>", lambda _event: self.dismiss())
        content.columnconfigure(1, weight=1)
        self._buttons = tk.Frame(card, bg="white")
        self._buttons.pack(fill="x", padx=14, pady=(0, 12))
        # Se empaquetan de derecha a izquierda: «Guardar» queda al extremo, «Ahora no» a su lado.
        self._button("Guardar", COLOR_ACCENT, "white", HOVER_STRONG, self._save)
        self._button("Ahora no", "white", COLOR_ACCENT, HOVER_SOFT, self.dismiss)

    def _button(self, text: str, bg: str, fg: str, hover: str, command: Callable[[], None]) -> None:
        button = tk.Label(
            self._buttons, text=text, bg=bg, fg=fg, cursor="hand2", padx=18, pady=7,
            font=(FONT_FAMILY, 10, "bold"),
        )
        button.pack(side="right", padx=(8, 0))
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=bg))

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
        self._detail.grid_forget()
        self._title.configure(text=text, fg=color)
        self._hide_job = self.after(RESULT_MS, self.dismiss)

    def dismiss(self) -> None:
        self._cancel(self._hide_job)
        self._hide_job = None
        self._cancel(self._slide_job)
        self._slide(-self._height - 4, self.destroy)

    def destroy(self) -> None:
        self._cancel(self._hide_job)
        self._cancel(self._slide_job)
        super().destroy()
