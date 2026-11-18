from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

import numpy as np

from ..camera import Camera, render_frame
from ..config import DAY_LABELS, FRAME_DELAY_MS, ID_PATTERN, REQUIRED_SAMPLES
from ..errors import ValidationError
from ..face_engine import FaceEngine
from ..models import FaceResult, Slot, Student
from .widgets import CameraView


class RegistrationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        engine: FaceEngine,
        camera: Camera,
        course_name: str,
        on_saved: Callable[[Student], None],
    ) -> None:
        super().__init__(parent)
        self.title(f"Registrar estudiante · {course_name}")
        self.resizable(False, False)
        self._engine = engine
        self._camera = camera
        self._on_saved = on_saved
        self._samples: tuple[tuple[float, ...], ...] = ()
        self._frame: np.ndarray | None = None
        self._faces = np.empty((0, 15), np.float32)
        self._loop_id: str | None = None
        self._id_var = tk.StringVar()
        self._name_var = tk.StringVar()
        self._count_var = tk.StringVar(value=f"Fotos: 0 de {REQUIRED_SAMPLES}")
        self._hint_var = tk.StringVar(
            value=f"Mira de frente a la cámara con buena luz. Se toman "
            f"{REQUIRED_SAMPLES} fotos; cambia un poco el ángulo en cada una."
        )
        self._build()
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._loop()

    def _build(self) -> None:
        self._view = CameraView(self, "Iniciando cámara…")
        self._view.grid(row=0, column=0, padx=16, pady=16)
        side = ttk.Frame(self, style="Card.TFrame", padding=16)
        side.grid(row=0, column=1, sticky="ns", padx=(0, 16), pady=16)
        ttk.Label(side, text="Datos del estudiante", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        ttk.Label(side, text="Cédula o ID (3 a 20 caracteres)", style="Card.TLabel").pack(
            anchor="w"
        )
        ttk.Entry(side, textvariable=self._id_var, width=30).pack(anchor="w", pady=(2, 10))
        ttk.Label(side, text="Nombre completo", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(side, textvariable=self._name_var, width=30).pack(anchor="w", pady=(2, 14))
        ttk.Label(side, textvariable=self._count_var, style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Button(
            side,
            text="📷  Tomar foto",
            style="Primary.TButton",
            command=self._capture_sample,
        ).pack(fill="x", pady=(6, 6))
        ttk.Button(
            side,
            text="💾  Guardar estudiante",
            style="Success.TButton",
            command=self._save,
        ).pack(fill="x", pady=6)
        ttk.Button(side, text="Cancelar", command=self._close).pack(fill="x", pady=6)
        self._hint_label = ttk.Label(
            side,
            textvariable=self._hint_var,
            style="Hint.TLabel",
            wraplength=260,
            justify="left",
        )
        self._hint_label.pack(anchor="w", pady=(12, 0))

    def _set_hint(self, message: str, error: bool = False) -> None:
        self._hint_var.set(message)
        self._hint_label.configure(style="Error.TLabel" if error else "Hint.TLabel")

    def _loop(self) -> None:
        frame = self._camera.read()
        if frame is not None:
            self._frame = frame
            self._faces = self._engine.detect(frame)
            results = tuple(
                FaceResult(tuple(int(v) for v in face[:4]), "Rostro", True)
                for face in self._faces
            )
            self._view.show(render_frame(frame, results))
        self._loop_id = self.after(FRAME_DELAY_MS, self._loop)

    def _capture_sample(self) -> None:
        if len(self._samples) >= REQUIRED_SAMPLES:
            self._set_hint("Ya tienes las fotos necesarias. Pulsa Guardar estudiante.")
            return
        if self._frame is None or len(self._faces) != 1:
            self._set_hint("Debe verse exactamente un rostro en la cámara.", True)
            return
        feature = self._engine.embed(self._frame, self._faces[0])
        vector = tuple(float(value) for value in feature.flatten())
        self._samples = (*self._samples, vector)
        self._count_var.set(f"Fotos: {len(self._samples)} de {REQUIRED_SAMPLES}")
        if len(self._samples) == REQUIRED_SAMPLES:
            self._set_hint("Listo. Pulsa Guardar estudiante.")
        else:
            self._set_hint("Foto tomada. Cambia un poco el ángulo y toma la siguiente.")

    def _save(self) -> None:
        student_id = self._id_var.get().strip()
        name = " ".join(self._name_var.get().split())
        if not ID_PATTERN.match(student_id):
            self._set_hint("El ID debe tener de 3 a 20 letras, números o guiones.", True)
            return
        if not name:
            self._set_hint("Escribe el nombre del estudiante.", True)
            return
        if len(self._samples) < REQUIRED_SAMPLES:
            self._set_hint(f"Faltan fotos: toma {REQUIRED_SAMPLES}.", True)
            return
        try:
            self._on_saved(Student(student_id, name, self._samples))
        except ValidationError as error:
            self._set_hint(str(error), True)
            return
        self._close()

    def _close(self) -> None:
        if self._loop_id is not None:
            self.after_cancel(self._loop_id)
            self._loop_id = None
        self._camera.release()
        self.grab_release()
        self.destroy()


class SlotDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, on_saved: Callable[[Slot], None]) -> None:
        super().__init__(parent)
        self.title("Agregar horario")
        self.resizable(False, False)
        self._on_saved = on_saved
        self._day_vars = [tk.BooleanVar(value=index < 5) for index in range(7)]
        self._start_hour = tk.StringVar(value="07")
        self._start_minute = tk.StringVar(value="00")
        self._end_hour = tk.StringVar(value="07")
        self._end_minute = tk.StringVar(value="10")
        self._hint_var = tk.StringVar(
            value="La lista solo se toma dentro de este intervalo."
        )
        self._build()
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def _time_row(
        self, parent: ttk.Frame, label: str, hour: tk.StringVar, minute: tk.StringVar
    ) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(anchor="w", pady=4)
        ttk.Label(row, text=label, style="Card.TLabel", width=18).pack(side="left")
        ttk.Spinbox(
            row, from_=0, to=23, width=4, format="%02.0f", textvariable=hour, wrap=True
        ).pack(side="left")
        ttk.Label(row, text=":", style="Card.TLabel").pack(side="left", padx=2)
        ttk.Spinbox(
            row, from_=0, to=59, width=4, format="%02.0f", textvariable=minute, wrap=True
        ).pack(side="left")

    def _build(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)
        ttk.Label(card, text="Días de la semana", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        days_row = ttk.Frame(card, style="Card.TFrame")
        days_row.pack(anchor="w", pady=(0, 10))
        for index, variable in enumerate(self._day_vars):
            ttk.Checkbutton(
                days_row, text=DAY_LABELS[index], variable=variable, style="Card.TCheckbutton"
            ).pack(side="left", padx=3)
        self._time_row(card, "Hora de inicio:", self._start_hour, self._start_minute)
        self._time_row(card, "Hora de fin:", self._end_hour, self._end_minute)
        self._hint_label = ttk.Label(
            card, textvariable=self._hint_var, style="Hint.TLabel", wraplength=340
        )
        self._hint_label.pack(anchor="w", pady=(10, 10))
        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Guardar horario", style="Primary.TButton", command=self._save).pack(
            side="left"
        )
        ttk.Button(buttons, text="Cancelar", command=self._close).pack(side="left", padx=8)

    def _set_error(self, message: str) -> None:
        self._hint_var.set(message)
        self._hint_label.configure(style="Error.TLabel")

    def _save(self) -> None:
        try:
            start = f"{int(self._start_hour.get()):02d}:{int(self._start_minute.get()):02d}"
            end = f"{int(self._end_hour.get()):02d}:{int(self._end_minute.get()):02d}"
        except ValueError:
            self._set_error("Las horas y minutos deben ser números.")
            return
        days = tuple(index for index, var in enumerate(self._day_vars) if var.get())
        try:
            self._on_saved(Slot(days, start, end))
        except ValidationError as error:
            self._set_error(str(error))
            return
        self._close()

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
