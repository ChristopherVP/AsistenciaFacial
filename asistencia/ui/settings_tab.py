from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from ..camera import Camera, detect_cameras, render_frame
from ..config import APP_TITLE, MAX_THRESHOLD, MIN_THRESHOLD
from ..errors import CameraError
from ..models import CameraInfo
from .state import AppState
from .widgets import CameraView


class SettingsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._cameras: tuple[CameraInfo, ...] = ()
        self._camera_var = tk.StringVar()
        self._camera_status_var = tk.StringVar(value="Buscando cámaras…")
        self._threshold_var = tk.StringVar(value=f"{state.settings.threshold:.2f}")
        self._manual_var = tk.StringVar(value=str(state.settings.manual_minutes))
        self._build()

    def _build(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=20)
        card.pack(fill="both", expand=True)
        ttk.Label(card, text="Cámara", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(anchor="w", pady=4)
        self._camera_combo = ttk.Combobox(
            row, textvariable=self._camera_var, values=(), width=40, state="readonly"
        )
        self._camera_combo.pack(side="left")
        ttk.Button(row, text="Buscar cámaras", command=self.refresh_cameras).pack(side="left", padx=8)
        ttk.Button(row, text="Probar cámara", command=self._test_camera).pack(side="left")
        ttk.Label(
            card,
            textvariable=self._camera_status_var,
            style="Hint.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(2, 14))
        ttk.Label(card, text="Reconocimiento y listas manuales", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        threshold_row = ttk.Frame(card, style="Card.TFrame")
        threshold_row.pack(anchor="w", pady=4)
        ttk.Label(
            threshold_row,
            text=f"Exigencia de reconocimiento ({MIN_THRESHOLD:.2f} a {MAX_THRESHOLD:.2f}, más alto = más estricto):",
            style="Card.TLabel",
        ).pack(side="left")
        ttk.Spinbox(
            threshold_row,
            from_=MIN_THRESHOLD,
            to=MAX_THRESHOLD,
            increment=0.05,
            format="%.2f",
            width=6,
            textvariable=self._threshold_var,
        ).pack(side="left", padx=8)
        manual_row = ttk.Frame(card, style="Card.TFrame")
        manual_row.pack(anchor="w", pady=4)
        ttk.Label(
            manual_row,
            text="Duración de una lista manual (minutos):",
            style="Card.TLabel",
        ).pack(side="left")
        ttk.Spinbox(manual_row, from_=1, to=120, width=6, textvariable=self._manual_var).pack(
            side="left", padx=8
        )
        ttk.Button(
            card, text="💾  Guardar ajustes", style="Primary.TButton", command=self._save
        ).pack(anchor="w", pady=(16, 0))

    def _selected_camera(self) -> CameraInfo | None:
        label = self._camera_var.get()
        return next((info for info in self._cameras if info.label == label), None)

    @staticmethod
    def _describe(cameras: tuple[CameraInfo, ...], chosen: CameraInfo) -> str:
        kinds = {info.kind for info in cameras}
        if len(cameras) == 1 and chosen.kind == "integrated":
            return (
                "Solo se detectó la cámara de la laptop. Conecta la webcam externa y "
                "pulsa Buscar cámaras para que aparezca."
            )
        if len(cameras) == 1 and chosen.kind == "external":
            return f"Se detectó la webcam externa: {chosen.name}. Pulsa Guardar ajustes."
        if len(cameras) == 1:
            return (
                f"Se detectó una cámara: {chosen.name}. Pulsa Probar cámara para confirmar "
                "cuál es y luego Guardar ajustes."
            )
        if kinds >= {"integrated", "external"}:
            return (
                "Se detectaron la cámara de la laptop y la webcam externa. "
                "Se seleccionó la webcam; pulsa Guardar ajustes."
            )
        return (
            f"Se detectaron {len(cameras)} cámaras. Elige una y usa Probar cámara "
            "para confirmar cuál es."
        )

    def refresh_cameras(self) -> None:
        if self._state.session_active:
            messagebox.showinfo(APP_TITLE, "Finaliza la lista en curso antes de buscar cámaras.")
            return
        self._camera_status_var.set("Buscando cámaras…")
        self.update_idletasks()
        cameras = detect_cameras()
        self._cameras = cameras
        self._camera_combo.configure(values=tuple(info.label for info in cameras))
        if not cameras:
            self._camera_var.set("")
            self._camera_status_var.set(
                "No se detectó ninguna cámara. Conecta la webcam y revisa en Windows: "
                "Configuración → Privacidad y seguridad → Cámara, con «Acceso a cámara» y "
                "«Permitir que las aplicaciones de escritorio accedan a la cámara» activados. "
                "Luego pulsa Buscar cámaras."
            )
            return
        settings = self._state.settings
        saved = next(
            (
                info
                for info in cameras
                if (settings.camera_name and info.name == settings.camera_name)
                or (not settings.camera_name and info.index == settings.camera_index)
            ),
            None,
        )
        external = next((info for info in cameras if info.kind == "external"), None)
        chosen = saved or external or cameras[-1]
        self._camera_var.set(chosen.label)
        self._camera_status_var.set(self._describe(cameras, chosen))

    def _test_camera(self) -> None:
        selected = self._selected_camera()
        if selected is None:
            messagebox.showinfo(APP_TITLE, "No hay cámara seleccionada. Pulsa Buscar cámaras primero.")
            return
        index = selected.index
        if self._state.session_active:
            messagebox.showinfo(APP_TITLE, "Finaliza la lista en curso antes de probar la cámara.")
            return
        try:
            camera = Camera(index)
        except CameraError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        frame = None
        for _ in range(10):
            frame = camera.read()
        camera.release()
        if frame is None:
            messagebox.showerror(APP_TITLE, "La cámara abrió pero no entregó imagen.")
            return
        window = tk.Toplevel(self)
        window.title(f"Vista previa · {selected.label}")
        view = CameraView(window, "")
        view.pack(padx=12, pady=12)
        view.show(render_frame(frame, ()))
        ttk.Label(
            window,
            text="Si ves la cámara correcta, pulsa Guardar ajustes.",
            style="Hint.TLabel",
        ).pack(pady=(0, 6))
        ttk.Button(window, text="Cerrar", command=window.destroy).pack(pady=(0, 12))

    def _save(self) -> None:
        selected = self._selected_camera()
        if selected is None:
            messagebox.showerror(
                APP_TITLE, "Elige una cámara de la lista. Si está vacía, pulsa Buscar cámaras."
            )
            return
        try:
            threshold = float(self._threshold_var.get())
            manual = int(self._manual_var.get())
        except ValueError:
            messagebox.showerror(APP_TITLE, "La exigencia y los minutos deben ser números.")
            return
        if not MIN_THRESHOLD <= threshold <= MAX_THRESHOLD:
            messagebox.showerror(
                APP_TITLE, f"La exigencia debe estar entre {MIN_THRESHOLD:.2f} y {MAX_THRESHOLD:.2f}."
            )
            return
        if not 1 <= manual <= 120:
            messagebox.showerror(APP_TITLE, "La duración manual debe estar entre 1 y 120 minutos.")
            return
        settings = replace(
            self._state.settings,
            camera_index=selected.index,
            camera_name=selected.name,
            threshold=threshold,
            manual_minutes=manual,
        )
        try:
            self._state.update_settings(settings)
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"No se pudieron guardar los ajustes:\n{error}")
            return
        messagebox.showinfo(APP_TITLE, "Ajustes guardados.")
