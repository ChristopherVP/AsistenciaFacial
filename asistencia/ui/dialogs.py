from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..camera import Camera, render_frame
from ..config import (
    CLOSE_SECONDS,
    DAY_LABELS,
    FRAME_DELAY_MS,
    LOOK_SECONDS,
    MIN_SAMPLES,
    VIEW_WIDTH,
)
from ..enrollment import EnrollmentStatus, FaceEnrollment, Phase, seconds_left
from ..errors import ValidationError
from ..face_engine import FaceEngine
from ..liveness import EyeStateDetector
from ..models import FaceResult, Slot, Student
from ..validators import (
    allows_cedula_input,
    allows_name_input,
    normalize_full_name,
    validate_cedula,
)
from ..voice import Speaker
from .widgets import CameraView

BLUE = (46, 134, 193)
AMBER = (185, 119, 14)
GREEN = (46, 139, 87)
RED = (176, 58, 46)


class RegistrationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        engine: FaceEngine,
        eyes: EyeStateDetector,
        camera: Camera,
        course_name: str,
        is_taken: Callable[[str], bool],
        on_saved: Callable[[Student], None],
    ) -> None:
        super().__init__(parent)
        self.title(f"Registrar estudiante · {course_name}")
        self.resizable(False, False)
        self._engine = engine
        self._eyes = eyes
        self._camera = camera
        self._is_taken = is_taken
        self._on_saved = on_saved
        self._speaker = Speaker()
        self._voice_warned = False
        self._closed = False
        self._enrollment: FaceEnrollment | None = None
        self._pending_samples: tuple[tuple[float, ...], ...] = ()
        self._pending_identity: tuple[str, str] | None = None
        self._banner: tuple[str, tuple[int, int, int]] | None = None
        self._loop_id: str | None = None
        self._cedula_var = tk.StringVar()
        self._name_var = tk.StringVar()
        self._consent_var = tk.BooleanVar(value=False)
        self._cedula_hint_var = tk.StringVar()
        self._hint_var = tk.StringVar(
            value="Complete los datos y pulse Iniciar. La cámara le pedirá mirar "
            "fijamente 3 segundos y luego cerrar los ojos 3 segundos."
        )
        self._build()
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._loop()

    def _build(self) -> None:
        left = ttk.Frame(self, style="Card.TFrame", padding=10)
        left.grid(row=0, column=0, padx=16, pady=16)
        self._view = CameraView(left, "Iniciando cámara…")
        self._view.pack()
        self._progress = ttk.Progressbar(left, length=VIEW_WIDTH, maximum=100)
        self._progress.pack(pady=(10, 0))
        side = ttk.Frame(self, style="Card.TFrame", padding=16)
        side.grid(row=0, column=1, sticky="ns", padx=(0, 16), pady=16)
        ttk.Label(side, text="Datos del estudiante", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        ttk.Label(side, text="Cédula (10 dígitos)", style="Card.TLabel").pack(anchor="w")
        self._cedula_entry = ttk.Entry(
            side,
            textvariable=self._cedula_var,
            width=32,
            validate="key",
            validatecommand=(self.register(allows_cedula_input), "%P"),
        )
        self._cedula_entry.pack(anchor="w", pady=(2, 0))
        self._cedula_entry.bind("<KeyRelease>", lambda _: self._update_cedula_hint())
        self._cedula_hint = ttk.Label(side, textvariable=self._cedula_hint_var, style="Hint.TLabel")
        self._cedula_hint.pack(anchor="w", pady=(0, 8))
        ttk.Label(side, text="Apellidos y nombres", style="Card.TLabel").pack(anchor="w")
        self._name_entry = ttk.Entry(
            side,
            textvariable=self._name_var,
            width=32,
            validate="key",
            validatecommand=(self.register(allows_name_input), "%P"),
        )
        self._name_entry.pack(anchor="w", pady=(2, 10))
        self._consent_check = ttk.Checkbutton(
            side,
            text="El estudiante autoriza usar su rostro\npara registrar su asistencia.",
            variable=self._consent_var,
            style="Card.TCheckbutton",
        )
        self._consent_check.pack(anchor="w", pady=(0, 12))
        self._start_button = ttk.Button(
            side,
            text="🔒  Iniciar verificación facial",
            style="Primary.TButton",
            command=self._start,
        )
        self._start_button.pack(fill="x", pady=(0, 6))
        self._skip_button = ttk.Button(
            side,
            text="Registrar sin verificar ojos cerrados",
            command=self._accept_without_blink,
        )
        ttk.Button(side, text="Cancelar", command=self._close).pack(fill="x", pady=6)
        self._hint_label = ttk.Label(
            side,
            textvariable=self._hint_var,
            style="Hint.TLabel",
            wraplength=290,
            justify="left",
        )
        self._hint_label.pack(anchor="w", pady=(10, 0))

    def _set_hint(self, message: str, error: bool = False) -> None:
        self._hint_var.set(message)
        self._hint_label.configure(style="Error.TLabel" if error else "Hint.TLabel")

    def _update_cedula_hint(self) -> None:
        text = self._cedula_var.get()
        if len(text) < 10:
            self._cedula_hint_var.set("")
            self._cedula_hint.configure(style="Hint.TLabel")
            return
        try:
            validate_cedula(text)
        except ValidationError as error:
            self._cedula_hint_var.set(str(error))
            self._cedula_hint.configure(style="Error.TLabel")
            return
        self._cedula_hint_var.set("✔ Cédula válida")
        self._cedula_hint.configure(style="Hint.TLabel")

    def _set_fields_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._cedula_entry.configure(state=state)
        self._name_entry.configure(state=state)
        self._consent_check.configure(state=state)
        self._start_button.configure(state=state)

    def _say(self, text: str) -> None:
        if self._speaker.speak(text) or self._voice_warned:
            return
        self._voice_warned = True
        self._set_hint("Sin voz en este equipo: siga las indicaciones en pantalla.")

    def _start(self) -> None:
        try:
            cedula = validate_cedula(self._cedula_var.get())
            name = normalize_full_name(self._name_var.get())
        except ValidationError as error:
            self._set_hint(str(error), True)
            return
        if self._is_taken(cedula):
            self._set_hint("Esa cédula ya está registrada en este curso.", True)
            return
        if not self._consent_var.get():
            self._set_hint("Marca la autorización del estudiante para continuar.", True)
            return
        self._pending_identity = (cedula, name)
        self._pending_samples = ()
        self._skip_button.pack_forget()
        self._set_fields_enabled(False)
        self._enrollment = FaceEnrollment(self._engine, self._eyes)
        self._apply_status(self._enrollment.begin())
        self._set_hint("Verificación en curso. Siga las indicaciones de la cámara.")

    def _loop(self) -> None:
        if self._closed:
            return
        frame = self._camera.read()
        if frame is not None:
            faces = self._engine.detect(frame)
            if self._enrollment is not None:
                self._apply_status(self._enrollment.update(frame, faces))
            results = tuple(
                FaceResult(tuple(int(v) for v in face[:4]), "", True) for face in faces
            )
            self._view.show(render_frame(frame, results, self._banner))
        self._loop_id = self.after(FRAME_DELAY_MS, self._loop)

    def _apply_status(self, status: EnrollmentStatus) -> None:
        if status.speak:
            self._say(status.speak)
        self._progress["value"] = status.progress * 100
        if status.phase is Phase.LOOK:
            suffix = (
                f"   {seconds_left(LOOK_SECONDS, status.progress)}"
                if status.progress > 0
                else ""
            )
            self._banner = (status.prompt.upper() + suffix, BLUE)
        elif status.phase is Phase.CLOSE:
            suffix = (
                f"   {seconds_left(CLOSE_SECONDS, status.progress)}"
                if status.progress > 0
                else ""
            )
            self._banner = (status.prompt.upper() + suffix, AMBER)
        elif status.phase is Phase.DONE:
            self._finish_success()
        else:
            self._finish_failure(status)

    def _finish_success(self) -> None:
        enrollment = self._enrollment
        self._enrollment = None
        if enrollment is None:
            return
        self._complete(enrollment.samples)

    def _complete(self, samples: tuple[tuple[float, ...], ...]) -> None:
        if self._pending_identity is None:
            return
        cedula, name = self._pending_identity
        try:
            self._on_saved(Student(cedula, name, samples))
        except ValidationError as error:
            self._banner = (str(error), RED)
            self._set_hint(str(error), True)
            self._set_fields_enabled(True)
            return
        self._banner = ("✔  REGISTRO CONFIRMADO", GREEN)
        self._progress["value"] = 100
        self._set_hint(f"{name} quedó registrado.")
        self._skip_button.pack_forget()
        self.after(1800, self._close)

    def _finish_failure(self, status: EnrollmentStatus) -> None:
        enrollment = self._enrollment
        self._enrollment = None
        self._banner = ("NO SE PUDO VERIFICAR", RED)
        self._progress["value"] = 0
        self._set_hint(status.prompt, True)
        self._start_button.configure(text="🔁  Reintentar verificación")
        self._set_fields_enabled(True)
        if enrollment is not None and len(enrollment.samples) >= MIN_SAMPLES:
            self._pending_samples = enrollment.samples
            self._skip_button.pack(fill="x", pady=(0, 6), after=self._start_button)

    def _accept_without_blink(self) -> None:
        if len(self._pending_samples) < MIN_SAMPLES:
            return
        self._complete(self._pending_samples)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop_id is not None:
            self.after_cancel(self._loop_id)
            self._loop_id = None
        self._speaker.stop()
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
