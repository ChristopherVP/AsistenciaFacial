from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import ttk

from PIL import ImageTk

from ..camera import detect_cameras
from ..config import (
    COLOR_BORDER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    FONT_FAMILY,
    NOTICE_MS,
    PRECISION_LEVELS,
)
from ..models import CameraInfo
from .state import AppState
from .widgets import Card


class SettingsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._cameras: tuple[CameraInfo, ...] = ()
        self._selected: CameraInfo | None = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._cards: list[tuple[CameraInfo, tk.Frame, tk.Label]] = []
        self._camera_status_var = tk.StringVar(value="Buscando cámaras…")
        self._save_status_var = tk.StringVar()
        self._save_job: str | None = None
        nearest = min(PRECISION_LEVELS, key=lambda level: abs(level[1] - state.settings.threshold))
        self._precision_var = tk.StringVar(value=nearest[0])
        self._build()

    def _build(self) -> None:
        camera_card = Card(self, padding=18)
        camera_card.pack(fill="x")
        top = ttk.Frame(camera_card.body, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="📷  Cámara del sistema", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(top, text="🔄  Buscar cámaras", style="Ghost.TButton", command=self.refresh_cameras).pack(
            side="right"
        )
        ttk.Label(
            camera_card.body,
            text="Elija la cámara que usará el programa. Compare la imagen de cada tarjeta "
            "para reconocer cuál es su webcam.",
            style="Hint.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 10))
        self._cards_frame = ttk.Frame(camera_card.body, style="Card.TFrame")
        self._cards_frame.pack(fill="x")
        ttk.Label(
            camera_card.body,
            textvariable=self._camera_status_var,
            style="Hint.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))
        precision_card = Card(self, padding=18)
        precision_card.pack(fill="x", pady=(12, 0))
        ttk.Label(precision_card.body, text="🎯  Precisión del reconocimiento", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            precision_card.body,
            text="Define qué tan seguro debe estar el sistema antes de marcar presente a un estudiante.",
            style="Hint.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 8))
        for name, _threshold, description in PRECISION_LEVELS:
            row = ttk.Frame(precision_card.body, style="Card.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Radiobutton(
                row, text=name, value=name, variable=self._precision_var, style="Card.TRadiobutton"
            ).pack(side="left")
            ttk.Label(row, text=f"—  {description}", style="Hint.TLabel").pack(side="left", padx=(8, 0))
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="💾  Guardar ajustes", style="Primary.TButton", command=self._save).pack(
            side="left"
        )
        ttk.Label(actions, textvariable=self._save_status_var, style="Page.Success.TLabel").pack(
            side="left", padx=12
        )

    def refresh_cameras(self) -> None:
        if self._state.session_active:
            self._camera_status_var.set("Finalice la lista en curso antes de buscar cámaras.")
            return
        self._camera_status_var.set("Buscando cámaras…")
        self.update_idletasks()
        cameras = detect_cameras()
        self._cameras = cameras
        settings = self._state.settings
        if not cameras:
            self._selected = None
            self._render_cards()
            self._camera_status_var.set(
                "No se detectó ninguna cámara. Conecte la webcam y revise en Windows: Configuración → "
                "Privacidad y seguridad → Cámara, con «Acceso a cámara» y «Permitir que las aplicaciones "
                "de escritorio accedan a la cámara» activados. Luego pulse Buscar cámaras."
            )
            return
        saved = next(
            (
                info
                for info in cameras
                if (settings.camera_name and info.name == settings.camera_name)
                or (not settings.camera_name and info.index == settings.camera_index)
            ),
            None,
        )
        others = [info for info in cameras if not info.is_integrated]
        self._selected = saved or (others[0] if len(others) == 1 else cameras[-1])
        self._render_cards()
        note = ""
        if all(info.name.startswith("Cámara ") for info in cameras):
            note = (
                " Para ver los nombres reales de las cámaras instale: python -m pip install pygrabber"
            )
        self._camera_status_var.set(
            f"Se detectaron {len(cameras)} cámara(s). La seleccionada está marcada «EN USO»; "
            f"pulse «Guardar ajustes» para confirmar.{note}"
        )

    def _render_cards(self) -> None:
        for child in self._cards_frame.winfo_children():
            child.destroy()
        self._photos = []
        self._cards = []
        for column, info in enumerate(self._cameras):
            card = tk.Frame(
                self._cards_frame, bg="white", highlightthickness=3, highlightbackground=COLOR_BORDER, cursor="hand2"
            )
            card.grid(row=0, column=column, padx=(0, 12), sticky="n")
            if info.snapshot is not None:
                photo = ImageTk.PhotoImage(info.snapshot)
                self._photos.append(photo)
                picture = tk.Label(card, image=photo, bg="white")
            else:
                picture = tk.Label(card, text="Sin imagen", bg="#111111", fg="white", width=28, height=9)
            picture.pack(padx=6, pady=(6, 4))
            name = tk.Label(
                card, text=info.name, bg="white", fg="#1B2631", font=(FONT_FAMILY, 10, "bold"), wraplength=210
            )
            name.pack()
            if info.is_integrated:
                tk.Label(
                    card, text="Cámara integrada de la laptop", bg="white", fg=COLOR_MUTED, font=(FONT_FAMILY, 9)
                ).pack()
            badge = tk.Label(card, text="", font=(FONT_FAMILY, 9, "bold"), padx=10, pady=3)
            badge.pack(pady=(6, 8))
            self._cards.append((info, card, badge))
            for widget in (card, picture, name, badge):
                widget.bind("<Button-1>", lambda _event, item=info: self._select(item))
        self._restyle_cards()

    def _select(self, info: CameraInfo) -> None:
        self._selected = info
        self._restyle_cards()

    def _restyle_cards(self) -> None:
        for info, card, badge in self._cards:
            chosen = self._selected is not None and info.index == self._selected.index
            card.configure(highlightbackground=COLOR_PRIMARY if chosen else COLOR_BORDER)
            if chosen:
                badge.configure(text="✔  EN USO", bg=COLOR_SUCCESS, fg="white")
            else:
                badge.configure(text="Usar esta cámara", bg="#EEF2F6", fg="#1B2631")

    def _show_saved(self, message: str) -> None:
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_status_var.set(message)
        self._save_job = self.after(NOTICE_MS, lambda: self._save_status_var.set(""))

    def _save(self) -> None:
        if self._selected is None:
            self._show_saved("⚠ Elija una cámara. Si no hay ninguna, pulse Buscar cámaras.")
            return
        threshold = next(level[1] for level in PRECISION_LEVELS if level[0] == self._precision_var.get())
        settings = replace(
            self._state.settings,
            camera_index=self._selected.index,
            camera_name=self._selected.name,
            threshold=threshold,
        )
        try:
            self._state.update_settings(settings)
        except OSError as error:
            self._show_saved(f"⚠ No se pudieron guardar los ajustes: {error}")
            return
        self._show_saved("✔ Ajustes guardados")
