from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
from typing import Callable

from ..camera import Camera, ScanOverlay, render_frame
from ..config import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_INFO_BG,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT,
    DAY_LABELS,
    FONT_FAMILY,
    FRAME_DELAY_MS,
    VIEW_WIDTH,
)
from ..enrollment import EnrollmentStatus, FaceEnrollment, Phase
from ..errors import ValidationError
from ..face_engine import FaceEngine
from ..models import FaceResult, Slot, Student, parse_time
from ..validators import (
    allows_cedula_input,
    allows_name_input,
    normalize_full_name,
    validate_cedula,
)
from ..voice import Speaker
from .widgets import Card, CameraView, Stepper, make_chip, set_chip

BLUE = (46, 134, 193)
GREEN = (46, 139, 87)
RED = (176, 58, 46)
GRAY = "#7F8C8D"


def build_header(window: tk.Misc, title: str, subtitle: str) -> tk.Frame:
    header = tk.Frame(window, bg=COLOR_PRIMARY)
    tk.Label(
        header, text=title, bg=COLOR_PRIMARY, fg="white", font=(FONT_FAMILY, 15, "bold")
    ).pack(side="left", padx=20, pady=14)
    tk.Label(
        header, text=subtitle, bg=COLOR_PRIMARY, fg="#D6EAF8", font=(FONT_FAMILY, 10)
    ).pack(side="right", padx=20)
    return header


class RegistrationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        engine: FaceEngine,
        camera: Camera,
        course_name: str,
        is_taken: Callable[[str], bool],
        on_saved: Callable[[Student], None],
    ) -> None:
        super().__init__(parent)
        self.title("Registrar estudiante")
        self.configure(bg="#EEF2F6")
        self.resizable(False, False)
        self._engine = engine
        self._camera = camera
        self._course_name = course_name
        self._is_taken = is_taken
        self._on_saved = on_saved
        self._speaker = Speaker()
        self._voice_warned = False
        self._closed = False
        self._enrollment: FaceEnrollment | None = None
        self._identity: tuple[str, str] | None = None
        self._banner: tuple[str, tuple[int, int, int]] | None = None
        self._loop_id: str | None = None
        self._cedula_var = tk.StringVar()
        self._name_var = tk.StringVar()
        self._consent_var = tk.BooleanVar(value=False)
        self._cedula_hint_var = tk.StringVar()
        self._percent_var = tk.StringVar(value="Escaneo: 0 %")
        self._hint_var = tk.StringVar(
            value="Complete los datos y pulse «Iniciar escaneo facial». La voz le guiará."
        )
        self._build()
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._loop()

    def _build(self) -> None:
        build_header(self, "Registrar estudiante", f"Curso: {self._course_name}").grid(
            row=0, column=0, columnspan=2, sticky="ew"
        )
        steps = Card(self, padding=8)
        steps.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 0))
        self._stepper = Stepper(
            steps.body, ("Datos del estudiante", "Escaneo facial", "Registro confirmado"), width=900
        )
        self._stepper.pack(fill="x")
        left = Card(self)
        left.grid(row=2, column=0, padx=(16, 8), pady=14, sticky="n")
        top = ttk.Frame(left.body, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Cámara", style="CardTitle.TLabel").pack(side="left")
        self._chip = make_chip(top, "EN ESPERA", GRAY)
        self._chip.pack(side="right")
        self._view = CameraView(left.body, "Iniciando cámara…")
        self._view.pack()
        self._progress = ttk.Progressbar(
            left.body, length=VIEW_WIDTH, maximum=100, style="Scan.Horizontal.TProgressbar"
        )
        self._progress.pack(pady=(10, 2))
        ttk.Label(left.body, textvariable=self._percent_var, style="Hint.TLabel").pack(anchor="w")
        right = Card(self)
        right.grid(row=2, column=1, padx=(8, 16), pady=14, sticky="nsew")
        self._form = ttk.Frame(right.body, style="Card.TFrame")
        self._form.pack(fill="both", expand=True)
        self._summary = ttk.Frame(right.body, style="Card.TFrame")
        self._build_form(self._form)
        self._build_summary(self._summary)

    def _build_form(self, form: ttk.Frame) -> None:
        ttk.Label(form, text="Datos personales", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        ttk.Label(form, text="Cédula (10 dígitos)", style="Card.TLabel").pack(anchor="w")
        self._cedula_entry = ttk.Entry(
            form,
            textvariable=self._cedula_var,
            width=34,
            font=(FONT_FAMILY, 11),
            validate="key",
            validatecommand=(self.register(allows_cedula_input), "%P"),
        )
        self._cedula_entry.pack(anchor="w", pady=(2, 0))
        self._cedula_entry.bind("<KeyRelease>", lambda _: self._update_cedula_hint())
        self._cedula_hint = ttk.Label(form, textvariable=self._cedula_hint_var, style="Hint.TLabel")
        self._cedula_hint.pack(anchor="w", pady=(2, 8))
        ttk.Label(form, text="Apellidos y nombres", style="Card.TLabel").pack(anchor="w")
        self._name_entry = ttk.Entry(
            form,
            textvariable=self._name_var,
            width=34,
            font=(FONT_FAMILY, 11),
            validate="key",
            validatecommand=(self.register(allows_name_input), "%P"),
        )
        self._name_entry.pack(anchor="w", pady=(2, 0))
        ttk.Label(form, text="Ejemplo: PÉREZ GÓMEZ JUAN CARLOS", style="Hint.TLabel").pack(
            anchor="w", pady=(2, 12)
        )
        consent = tk.Frame(form, bg=COLOR_INFO_BG, highlightthickness=1, highlightbackground=COLOR_BORDER)
        consent.pack(fill="x", pady=(0, 14))
        self._consent_check = ttk.Checkbutton(
            consent,
            text="El estudiante autoriza el uso de su rostro\npara registrar su asistencia.",
            variable=self._consent_var,
            style="Info.TCheckbutton",
        )
        self._consent_check.pack(anchor="w", padx=10, pady=10)
        self._start_button = ttk.Button(
            form, text="🔒  Iniciar escaneo facial", style="Primary.TButton", command=self._start
        )
        self._start_button.pack(fill="x", pady=(0, 6))
        ttk.Button(form, text="Cancelar", style="Ghost.TButton", command=self._close).pack(fill="x")
        self._hint_label = ttk.Label(
            form, textvariable=self._hint_var, style="Hint.TLabel", wraplength=300, justify="left"
        )
        self._hint_label.pack(anchor="w", pady=(12, 0))

    def _build_summary(self, summary: ttk.Frame) -> None:
        self._summary_icon = tk.Label(
            summary, text="✔", bg="white", fg=COLOR_SUCCESS, font=(FONT_FAMILY, 54, "bold")
        )
        self._summary_icon.pack(pady=(30, 4))
        ttk.Label(summary, text="Registro confirmado", style="Title.TLabel").pack()
        self._summary_name = ttk.Label(summary, text="", style="Status.TLabel", wraplength=300, justify="center")
        self._summary_name.pack(pady=(14, 2))
        self._summary_cedula = ttk.Label(summary, text="", style="Hint.TLabel")
        self._summary_cedula.pack()
        self._summary_course = ttk.Label(summary, text="", style="Hint.TLabel")
        self._summary_course.pack(pady=(2, 0))

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
        self._cedula_hint.configure(style="Success.TLabel")

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
            self._set_hint("Marque la autorización del estudiante para continuar.", True)
            return
        self._identity = (cedula, name)
        self._set_fields_enabled(False)
        self._stepper.set_active(1)
        set_chip(self._chip, "ESCANEANDO", COLOR_ACCENT)
        self._set_hint("Escaneo en curso. Siga las indicaciones de voz y de la pantalla.")
        self._enrollment = FaceEnrollment(self._engine)
        self._apply_status(self._enrollment.begin())

    def _loop(self) -> None:
        if self._closed:
            return
        frame = self._camera.read()
        if frame is not None:
            faces = self._engine.detect(frame)
            scan = None
            if self._enrollment is not None:
                status = self._enrollment.update(frame, faces)
                self._apply_status(status)
                if status.phase is Phase.SCAN:
                    scan = ScanOverlay(status.box, status.progress, time.monotonic())
            results = (
                ()
                if scan is not None
                else tuple(FaceResult(tuple(int(v) for v in face[:4]), "", True) for face in faces)
            )
            self._view.show(render_frame(frame, results, self._banner, scan))
        self._loop_id = self.after(FRAME_DELAY_MS, self._loop)

    def _apply_status(self, status: EnrollmentStatus) -> None:
        if status.speak:
            self._say(status.speak)
        self._progress["value"] = status.progress * 100
        self._percent_var.set(f"Escaneo: {int(status.progress * 100)} %")
        if status.phase is Phase.SCAN:
            self._banner = (status.prompt.upper(), BLUE)
        elif status.phase is Phase.DONE:
            self._finish_success()
        else:
            self._finish_failure(status)

    def _finish_success(self) -> None:
        enrollment = self._enrollment
        self._enrollment = None
        if enrollment is None or self._identity is None:
            return
        cedula, name = self._identity
        try:
            self._on_saved(Student(cedula, name, enrollment.samples))
        except ValidationError as error:
            self._banner = (str(error).upper(), RED)
            self._set_hint(str(error), True)
            set_chip(self._chip, "ERROR", COLOR_DANGER)
            self._stepper.set_active(0)
            self._set_fields_enabled(True)
            return
        self._banner = ("✔  ROSTRO REGISTRADO", GREEN)
        set_chip(self._chip, "COMPLETADO", COLOR_SUCCESS)
        self._stepper.set_active(3)
        self._summary_name.configure(text=name)
        self._summary_cedula.configure(text=f"Cédula: {cedula}")
        self._summary_course.configure(text=f"Curso: {self._course_name}")
        self._form.pack_forget()
        self._summary.pack(fill="both", expand=True)
        self.after(2400, self._close)

    def _finish_failure(self, status: EnrollmentStatus) -> None:
        self._enrollment = None
        self._banner = ("NO SE PUDO REGISTRAR EL ROSTRO", RED)
        set_chip(self._chip, "ERROR", COLOR_DANGER)
        self._stepper.set_active(0)
        self._set_hint(status.prompt, True)
        self._start_button.configure(text="🔁  Reintentar escaneo")
        self._set_fields_enabled(True)

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
        self.configure(bg="#EEF2F6")
        self.resizable(False, False)
        self._on_saved = on_saved
        self._day_vars = [tk.BooleanVar(value=index < 5) for index in range(7)]
        self._start_hour = tk.StringVar(value="07")
        self._start_minute = tk.StringVar(value="00")
        self._end_hour = tk.StringVar(value="07")
        self._end_minute = tk.StringVar(value="20")
        self._summary_var = tk.StringVar()
        self._build()
        for variable in (*self._day_vars, self._start_hour, self._start_minute, self._end_hour, self._end_minute):
            variable.trace_add("write", lambda *_: self._refresh_summary())
        self._refresh_summary()
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def _time_picker(self, parent: tk.Misc, title: str, hour: tk.StringVar, minute: tk.StringVar) -> None:
        box = tk.Frame(parent, bg="white", highlightthickness=1, highlightbackground=COLOR_BORDER)
        box.pack(side="left", padx=(0, 12))
        tk.Label(box, text=title, bg="white", fg=COLOR_MUTED, font=(FONT_FAMILY, 9, "bold")).pack(
            anchor="w", padx=12, pady=(8, 0)
        )
        row = tk.Frame(box, bg="white")
        row.pack(padx=12, pady=(2, 10))
        spin = {"font": (FONT_FAMILY, 20, "bold"), "width": 3, "wrap": True, "format": "%02.0f"}
        ttk.Spinbox(row, from_=0, to=23, textvariable=hour, **spin).pack(side="left")
        tk.Label(row, text=":", bg="white", fg=COLOR_TEXT, font=(FONT_FAMILY, 20, "bold")).pack(side="left", padx=3)
        ttk.Spinbox(row, from_=0, to=59, textvariable=minute, **spin).pack(side="left")

    def _build(self) -> None:
        build_header(self, "Agregar horario", "La lista solo se toma dentro del intervalo").pack(fill="x")
        card = Card(self, padding=18)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        body = card.body
        ttk.Label(body, text="Días de la semana", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        days = ttk.Frame(body, style="Card.TFrame")
        days.pack(anchor="w")
        for index, variable in enumerate(self._day_vars):
            ttk.Checkbutton(
                days, text=DAY_LABELS[index], variable=variable, style="Day.Toolbutton"
            ).pack(side="left", padx=(0, 6))
        ttk.Label(body, text="Intervalo en que se toma la lista", style="CardTitle.TLabel").pack(
            anchor="w", pady=(18, 8)
        )
        pickers = ttk.Frame(body, style="Card.TFrame")
        pickers.pack(anchor="w")
        self._time_picker(pickers, "HORA DE INICIO", self._start_hour, self._start_minute)
        self._time_picker(pickers, "HORA DE FIN", self._end_hour, self._end_minute)
        quick = ttk.Frame(body, style="Card.TFrame")
        quick.pack(anchor="w", pady=(10, 0))
        ttk.Label(quick, text="Duración rápida:", style="Hint.TLabel").pack(side="left", padx=(0, 8))
        for minutes in (10, 20, 30, 45):
            ttk.Button(
                quick,
                text=f"{minutes} min",
                style="Ghost.TButton",
                command=lambda value=minutes: self._apply_duration(value),
            ).pack(side="left", padx=(0, 6))
        summary = tk.Frame(body, bg=COLOR_INFO_BG, highlightthickness=1, highlightbackground=COLOR_BORDER)
        summary.pack(fill="x", pady=(16, 14))
        self._summary_label = tk.Label(
            summary,
            textvariable=self._summary_var,
            bg=COLOR_INFO_BG,
            fg=COLOR_PRIMARY,
            font=(FONT_FAMILY, 10, "bold"),
            wraplength=460,
            justify="left",
            padx=12,
            pady=10,
        )
        self._summary_label.pack(anchor="w")
        buttons = ttk.Frame(body, style="Card.TFrame")
        buttons.pack(fill="x")
        ttk.Button(buttons, text="💾  Guardar horario", style="Primary.TButton", command=self._save).pack(
            side="left"
        )
        ttk.Button(buttons, text="Cancelar", style="Ghost.TButton", command=self._close).pack(
            side="left", padx=8
        )

    def _times(self) -> tuple[str, str]:
        start = f"{int(self._start_hour.get()):02d}:{int(self._start_minute.get()):02d}"
        end = f"{int(self._end_hour.get()):02d}:{int(self._end_minute.get()):02d}"
        return start, end

    def _apply_duration(self, minutes: int) -> None:
        try:
            start = datetime.combine(datetime.today(), parse_time(self._times()[0]))
        except (ValueError, ValidationError):
            return
        end = start + timedelta(minutes=minutes)
        if end.date() != start.date():
            end = start.replace(hour=23, minute=59)
        self._end_hour.set(f"{end.hour:02d}")
        self._end_minute.set(f"{end.minute:02d}")

    def _refresh_summary(self) -> None:
        days = tuple(index for index, var in enumerate(self._day_vars) if var.get())
        try:
            start, end = self._times()
            slot = Slot(days, start, end)
        except (ValueError, ValidationError) as error:
            self._summary_var.set(f"⚠  {error}")
            self._summary_label.configure(fg=COLOR_DANGER)
            return
        self._summary_var.set(
            f"Se tomará lista los {slot.days_text}, de {slot.start} a {slot.end} ({slot.minutes} minutos)."
        )
        self._summary_label.configure(fg=COLOR_PRIMARY)

    def _save(self) -> None:
        days = tuple(index for index, var in enumerate(self._day_vars) if var.get())
        try:
            start, end = self._times()
            self._on_saved(Slot(days, start, end))
        except (ValueError, ValidationError) as error:
            self._summary_var.set(f"⚠  {error}")
            self._summary_label.configure(fg=COLOR_DANGER)
            return
        self._close()

    def _close(self) -> None:
        self.grab_release()
        self.destroy()


class NameDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        subtitle: str,
        initial: str,
        confirm_text: str,
        on_accept: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(bg="#EEF2F6")
        self.resizable(False, False)
        self._on_accept = on_accept
        self._value = tk.StringVar(value=initial)
        self._hint_var = tk.StringVar(value="Ejemplo: Infraestructura 2 · Paralelo A")
        build_header(self, title, subtitle).pack(fill="x")
        card = Card(self, padding=18)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card.body, text="Nombre del curso", style="Card.TLabel").pack(anchor="w")
        entry = ttk.Entry(card.body, textvariable=self._value, width=44, font=(FONT_FAMILY, 11))
        entry.pack(anchor="w", pady=(2, 4))
        self._hint = ttk.Label(card.body, textvariable=self._hint_var, style="Hint.TLabel", wraplength=380)
        self._hint.pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(card.body, style="Card.TFrame")
        buttons.pack(fill="x")
        ttk.Button(buttons, text=confirm_text, style="Primary.TButton", command=self._accept).pack(side="left")
        ttk.Button(buttons, text="Cancelar", style="Ghost.TButton", command=self._close).pack(
            side="left", padx=8
        )
        entry.bind("<Return>", lambda _: self._accept())
        entry.icursor("end")
        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        entry.focus_set()

    def _accept(self) -> None:
        try:
            self._on_accept(self._value.get())
        except ValidationError as error:
            self._hint_var.set(str(error))
            self._hint.configure(style="Error.TLabel")
            return
        self._close()

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
