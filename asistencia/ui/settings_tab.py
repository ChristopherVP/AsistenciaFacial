from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from ..camera import Camera, detect_cameras
from ..config import (
    APP_TITLE,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    FONT_FAMILY,
    NOTICE_MS,
    PRECISION_LEVELS,
    precision_for,
)
from ..errors import AuthError, CameraError
from ..models import CameraInfo
from .camera_preview import CameraPreviewDialog
from .state import AppState
from .widgets import Card


class SettingsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._cameras: tuple[CameraInfo, ...] = ()
        self._selected: CameraInfo | None = None
        self._cards: list[tuple[CameraInfo, tk.Frame, tk.Label]] = []
        self._camera_status_var = tk.StringVar(value="Buscando cámaras…")
        self._save_status_var = tk.StringVar()
        self._save_job: str | None = None
        user = state.current_user
        self._remember_var = tk.BooleanVar(value=bool(user and user.remembered))
        self._account_status_var = tk.StringVar()
        self._precision_var = tk.StringVar(value=precision_for(state.settings.threshold).name)
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
            text="Elija la cámara que usará el programa. Pulse «Probar cámara» para ver en vivo "
            "cuál está grabando antes de elegirla.",
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
        for level in PRECISION_LEVELS:
            row = ttk.Frame(precision_card.body, style="Card.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Radiobutton(
                row, text=level.name, value=level.name, variable=self._precision_var,
                style="Card.TRadiobutton",
            ).pack(side="left")
            ttk.Label(row, text=f"—  {level.description}", style="Hint.TLabel").pack(
                side="left", padx=(8, 0)
            )
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="💾  Guardar ajustes", style="Primary.TButton", command=self._save).pack(
            side="left"
        )
        ttk.Label(actions, textvariable=self._save_status_var, style="Page.Success.TLabel").pack(
            side="left", padx=12
        )
        self._build_account_card()

    def _build_account_card(self) -> None:
        card = Card(self, padding=18)
        card.pack(fill="x", pady=(18, 0))
        ttk.Label(card.body, text="👤  Mi cuenta", style="CardTitle.TLabel").pack(anchor="w")
        user = self._state.current_user
        if user is not None:
            ttk.Label(
                card.body,
                text=f"{user.full_name}   ·   @{user.username}   ·   Cédula {user.cedula}",
                style="Card.TLabel",
            ).pack(anchor="w", pady=(6, 8))
        ttk.Checkbutton(
            card.body,
            text="Entrar con un clic (recordar mi usuario en este equipo)",
            variable=self._remember_var,
            command=self._toggle_remember,
            style="Card.TCheckbutton",
        ).pack(anchor="w")
        ttk.Label(
            card.body,
            text="Si lo desactiva, tendrá que escribir su contraseña cada vez que abra el programa.",
            style="Hint.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(card.body, textvariable=self._account_status_var, style="Success.TLabel").pack(
            anchor="w", pady=(6, 0)
        )

    def sync_remember(self) -> None:
        """Refleja en el check el estado actual (p. ej. tras guardar desde el aviso superior)."""
        user = self._state.current_user
        self._remember_var.set(bool(user and user.remembered))

    def _toggle_remember(self) -> None:
        wanted = self._remember_var.get()
        try:
            self._state.set_remember_current_user(wanted)
        except AuthError as error:
            self._remember_var.set(not wanted)
            self._account_status_var.set(f"⚠ {error}")
            return
        self._account_status_var.set(
            "✔ Usuario guardado: la próxima vez entrará con un clic."
            if wanted
            else "✔ Ya no se guarda el usuario: se pedirá la contraseña al entrar."
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
        usable = [info for info in cameras if info.available]
        saved = next(
            (
                info
                for info in usable
                if (settings.camera_name and info.name == settings.camera_name)
                or (not settings.camera_name and info.index == settings.camera_index)
            ),
            None,
        )
        others = [info for info in usable if not info.is_integrated]
        fallback = others[0] if len(others) == 1 else (usable[-1] if usable else None)
        self._selected = saved or fallback
        self._render_cards()
        note = ""
        if all(info.name.startswith("Cámara ") for info in cameras):
            note = (
                " No se pudieron leer los nombres del Administrador de dispositivos; "
                "instale pygrabber para verlos: python -m pip install pygrabber"
            )
        usable_count = len(usable)
        self._camera_status_var.set(
            f"Cámaras del sistema (como en el Administrador de dispositivos): "
            f"{', '.join(info.name for info in cameras)}. "
            f"{usable_count} disponible(s) para usar. "
            f"La elegida dice «EN USO»; pulse «Guardar ajustes» para confirmar.{note}"
        )

    def _render_cards(self) -> None:
        for child in self._cards_frame.winfo_children():
            child.destroy()
        self._cards = []
        for column, info in enumerate(self._cameras):
            card = tk.Frame(
                self._cards_frame, bg="white", highlightthickness=3, highlightbackground=COLOR_BORDER
            )
            card.grid(row=0, column=column, padx=(0, 12), sticky="n")
            name = tk.Label(
                card, text=info.name, bg="white", fg="#1B2631", font=(FONT_FAMILY, 11, "bold"),
                wraplength=220, width=24, justify="center",
            )
            name.pack(padx=8, pady=(10, 2))
            kind = "Cámara integrada de la laptop" if info.is_integrated else f"Dispositivo {info.index}"
            tk.Label(card, text=kind, bg="white", fg=COLOR_MUTED, font=(FONT_FAMILY, 9)).pack()
            status_text, status_color = (
                ("● Disponible", COLOR_SUCCESS)
                if info.available
                else ("● No disponible (en uso por otra app)", COLOR_DANGER)
            )
            tk.Label(
                card, text=status_text, bg="white", fg=status_color, font=(FONT_FAMILY, 9, "bold"),
                wraplength=220,
            ).pack(pady=(4, 6))
            test = ttk.Button(
                card,
                text="▶  Probar cámara",
                style="Ghost.TButton",
                command=lambda item=info: self._preview(item),
                state="normal" if info.available else "disabled",
            )
            test.pack(padx=10)
            badge = tk.Label(card, text="", font=(FONT_FAMILY, 9, "bold"), padx=10, pady=3)
            badge.pack(pady=(8, 10))
            self._cards.append((info, card, badge))
            if info.available:
                for widget in (card, name, badge):
                    widget.configure(cursor="hand2")
                    widget.bind("<Button-1>", lambda _event, item=info: self._select(item))
        self._restyle_cards()

    def _preview(self, info: CameraInfo) -> None:
        if self._state.session_active:
            self._camera_status_var.set("Finalice la lista en curso antes de probar una cámara.")
            return
        try:
            camera = Camera(info.index)
        except CameraError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        CameraPreviewDialog(self, info, camera, self._select)

    def _select(self, info: CameraInfo) -> None:
        self._selected = info
        self._restyle_cards()

    def _restyle_cards(self) -> None:
        for info, card, badge in self._cards:
            chosen = self._selected is not None and info.index == self._selected.index
            card.configure(highlightbackground=COLOR_PRIMARY if chosen else COLOR_BORDER)
            if chosen:
                badge.configure(text="✔  EN USO", bg=COLOR_SUCCESS, fg="white")
            elif info.available:
                badge.configure(text="Usar esta cámara", bg="#EEF2F6", fg="#1B2631")
            else:
                badge.configure(text="No disponible", bg="#EEF2F6", fg=COLOR_MUTED)

    def _show_saved(self, message: str) -> None:
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_status_var.set(message)
        self._save_job = self.after(NOTICE_MS, lambda: self._save_status_var.set(""))

    def _save(self) -> None:
        if self._selected is None:
            self._show_saved("⚠ Elija una cámara. Si no hay ninguna, pulse Buscar cámaras.")
            return
        level = next(item for item in PRECISION_LEVELS if item.name == self._precision_var.get())
        settings = replace(
            self._state.settings,
            camera_index=self._selected.index,
            camera_name=self._selected.name,
            threshold=level.threshold,
        )
        try:
            self._state.update_settings(settings)
        except OSError as error:
            self._show_saved(f"⚠ No se pudieron guardar los ajustes: {error}")
            return
        self._show_saved("✔ Ajustes guardados")
