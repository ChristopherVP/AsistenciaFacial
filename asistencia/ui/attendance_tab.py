from __future__ import annotations

import csv
import tkinter as tk
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from ..attendance import AttendanceBook, AttendanceSession
from ..camera import Camera, render_frame
from ..config import (
    APP_TITLE,
    BACKUP_DIR,
    FRAME_DELAY_MS,
    MAX_READ_FAILURES,
    PROCESS_EVERY_N_FRAMES,
)
from ..errors import AlreadyTakenError, AttendanceError, CameraError
from ..face_engine import Gallery
from ..models import Course, FaceResult, Slot, parse_time
from ..scheduler import describe_next, due_courses
from .state import AppState
from .widgets import CameraView


class AttendanceTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._session: AttendanceSession | None = None
        self._course: Course | None = None
        self._camera: Camera | None = None
        self._session_end = datetime.now()
        self._replace_existing = False
        self._results: tuple[FaceResult, ...] = ()
        self._frame_count = 0
        self._read_failures = 0
        self._shown_present = -1
        self._loop_id: str | None = None
        self._auto_attempts: set[tuple[str, str]] = set()
        self._course_ids: dict[str, str] = {}
        self._course_var = tk.StringVar()
        self._status_var = tk.StringVar()
        self._timer_var = tk.StringVar()
        self._next_var = tk.StringVar()
        self._count_var = tk.StringVar()
        self._build()
        state.subscribe(self.refresh_courses)
        self.refresh_courses()

    @property
    def is_running(self) -> bool:
        return self._session is not None

    def _build(self) -> None:
        self._view = CameraView(self, "Cámara apagada")
        self._view.grid(row=0, column=0, sticky="n")
        panel = ttk.Frame(self, style="Card.TFrame", padding=16)
        panel.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        ttk.Label(panel, text="Curso", style="CardTitle.TLabel").pack(anchor="w")
        self._course_combo = ttk.Combobox(
            panel, textvariable=self._course_var, state="readonly", width=34
        )
        self._course_combo.pack(fill="x", pady=(2, 10))
        self._course_combo.bind("<<ComboboxSelected>>", lambda _: self._refresh_counter())
        ttk.Label(panel, textvariable=self._status_var, style="Status.TLabel", wraplength=330).pack(
            anchor="w"
        )
        ttk.Label(panel, textvariable=self._timer_var, style="Card.TLabel").pack(
            anchor="w", pady=(2, 0)
        )
        ttk.Label(panel, textvariable=self._next_var, style="Hint.TLabel", wraplength=330).pack(
            anchor="w", pady=(2, 10)
        )
        ttk.Label(panel, textvariable=self._count_var, style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        self._present_tree = ttk.Treeview(
            panel, columns=("hora", "nombre"), show="headings", height=8
        )
        self._present_tree.heading("hora", text="Hora")
        self._present_tree.heading("nombre", text="Estudiante presente")
        self._present_tree.column("hora", width=80, anchor="center", stretch=False)
        self._present_tree.column("nombre", width=240)
        self._present_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(panel, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        self._start_button = ttk.Button(
            buttons, text="▶  Iniciar lista", style="Success.TButton", command=self._start_manual
        )
        self._start_button.pack(fill="x", pady=(0, 6))
        self._stop_button = ttk.Button(
            buttons,
            text="■  Finalizar y guardar",
            style="Danger.TButton",
            command=self.finish_session,
            state="disabled",
        )
        self._stop_button.pack(fill="x")

    def refresh_courses(self) -> None:
        courses = self._state.repository.courses
        names = tuple(course.name for course in courses)
        self._course_ids = {course.name: course.course_id for course in courses}
        self._course_combo.configure(values=names)
        if self._course_var.get() not in names:
            self._course_var.set(names[0] if names else "")
        if self._session is None:
            self._status_var.set(
                "Listo para tomar lista"
                if names
                else "Crea un curso en la pestaña Cursos para empezar"
            )
        self._refresh_counter()

    def _selected_course(self) -> Course | None:
        return self._state.repository.get(self._course_ids.get(self._course_var.get()))

    def _refresh_counter(self) -> None:
        course = self._course if self._session is not None else self._selected_course()
        total = len(course.students) if course else 0
        present = len(self._session.present) if self._session else 0
        self._count_var.set(f"Presentes: {present} de {total} estudiantes")

    def _refresh_present(self) -> None:
        if self._session is None or self._course is None:
            return
        present = self._session.present
        if len(present) == self._shown_present:
            return
        self._shown_present = len(present)
        names = {student.student_id: student.name for student in self._course.students}
        self._present_tree.delete(*self._present_tree.get_children())
        for student_id, moment in sorted(present.items(), key=lambda item: item[1]):
            self._present_tree.insert(
                "", "end", values=(f"{moment:%H:%M:%S}", names.get(student_id, student_id))
            )
        self._refresh_counter()

    @staticmethod
    def _book(course: Course) -> AttendanceBook:
        return AttendanceBook(Path(course.excel_path), course.name)

    def _start_manual(self) -> None:
        course = self._selected_course()
        if course is None:
            messagebox.showinfo(APP_TITLE, "Primero crea un curso en la pestaña Cursos.")
            return
        if not course.students:
            messagebox.showinfo(
                APP_TITLE, f"El curso «{course.name}» no tiene estudiantes registrados."
            )
            return
        try:
            exists = self._book(course).has_date(date.today())
        except AttendanceError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        if exists and not messagebox.askyesno(
            APP_TITLE,
            f"Ya existe la lista de hoy de «{course.name}» en el Excel.\n"
            "¿Tomarla de nuevo y reemplazarla?",
        ):
            return
        end = datetime.now() + timedelta(minutes=self._state.settings.manual_minutes)
        self._begin(course, end, exists, automatic=False)

    def _try_auto_start(self, now: datetime) -> None:
        for course, slot in due_courses(self._state.repository.courses, now):
            key = (course.course_id, now.date().isoformat())
            if key in self._auto_attempts:
                continue
            self._auto_attempts.add(key)
            self._start_automatic(course, slot, now)
            return

    def _start_automatic(self, course: Course, slot: Slot, now: datetime) -> None:
        try:
            self._state.save_course(
                replace(course, last_auto_date=now.date().isoformat()), notify=False
            )
        except OSError as error:
            self._status_var.set(f"No se pudo registrar la lista automática: {error}")
            return
        if not course.students:
            self._status_var.set(f"Lista automática omitida: «{course.name}» no tiene estudiantes")
            return
        try:
            exists = self._book(course).has_date(now.date())
        except AttendanceError as error:
            self._status_var.set(f"Lista automática omitida: {error}")
            return
        if exists:
            self._status_var.set(f"Lista automática omitida: «{course.name}» ya tiene la lista de hoy")
            return
        window = self.winfo_toplevel()
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)
        window.after(1500, lambda: window.attributes("-topmost", False))
        end = datetime.combine(now.date(), parse_time(slot.end))
        self._begin(course, end, False, automatic=True)

    def _begin(self, course: Course, end: datetime, replace_existing: bool, automatic: bool) -> None:
        try:
            camera = Camera(self._state.settings.camera_index)
        except CameraError as error:
            if automatic:
                self._status_var.set(f"Lista automática omitida: {error}")
            else:
                messagebox.showerror(APP_TITLE, str(error))
            return
        self._camera = camera
        self._course = course
        self._session = AttendanceSession(
            self._state.engine,
            Gallery(course.students),
            self._state.settings.threshold,
            frozenset(student.student_id for student in course.students),
        )
        self._session_end = end
        self._replace_existing = replace_existing
        self._results = ()
        self._frame_count = 0
        self._read_failures = 0
        self._shown_present = -1
        self._present_tree.delete(*self._present_tree.get_children())
        self._state.session_active = True
        self._course_combo.configure(state="disabled")
        self._status_var.set(f"Tomando lista: {course.name}")
        self._start_button.configure(state="disabled")
        self._stop_button.configure(state="normal")
        self._refresh_counter()
        self._frame_loop()

    def _frame_loop(self) -> None:
        if self._session is None or self._camera is None or self._course is None:
            return
        frame = self._camera.read()
        if frame is None:
            self._read_failures += 1
            if self._read_failures >= MAX_READ_FAILURES:
                messagebox.showerror(
                    APP_TITLE, "Se perdió la señal de la cámara. Se guardará lo registrado."
                )
                self.finish_session()
                return
        else:
            self._read_failures = 0
            self._frame_count += 1
            if self._frame_count % PROCESS_EVERY_N_FRAMES == 0:
                self._results = self._session.process(frame)
            self._view.show(render_frame(frame, self._results))
            self._refresh_present()
            if self._course.finish_when_complete and self._session.complete:
                self.finish_session()
                return
        self._loop_id = self.after(FRAME_DELAY_MS, self._frame_loop)

    def finish_session(self) -> None:
        session, course = self._session, self._course
        if session is None or course is None:
            return
        self._session = None
        self._course = None
        if self._loop_id is not None:
            self.after_cancel(self._loop_id)
            self._loop_id = None
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        self._state.session_active = False
        self._view.clear()
        self._timer_var.set("")
        self._course_combo.configure(state="readonly")
        self._start_button.configure(state="normal")
        self._stop_button.configure(state="disabled")
        self._status_var.set("Guardando lista…")
        self.update_idletasks()
        saved = self._save_attendance(course, frozenset(session.present))
        self._status_var.set(
            f"Lista de «{course.name}» guardada" if saved else "Lista no guardada en Excel"
        )

    def _save_attendance(self, course: Course, present_ids: frozenset[str]) -> bool:
        day = date.today()
        replace_existing = self._replace_existing
        while True:
            try:
                result = self._book(course).record(
                    day, present_ids, course.students, replace_existing
                )
                break
            except AlreadyTakenError:
                if messagebox.askyesno(
                    APP_TITLE,
                    f"Ya existe una lista de hoy de «{course.name}».\n¿Reemplazarla con esta?",
                ):
                    replace_existing = True
                    continue
                self._write_backup(course, day, present_ids)
                return False
            except AttendanceError as error:
                if messagebox.askretrycancel("No se pudo guardar", f"{error}\n\n¿Reintentar?"):
                    continue
                self._write_backup(course, day, present_ids)
                return False
        messagebox.showinfo(
            APP_TITLE,
            f"Lista de «{course.name}» guardada en la columna {result.column_letter}.\n"
            f"Presentes: {result.present} de {result.total}.",
        )
        return True

    def _write_backup(self, course: Course, day: date, present_ids: frozenset[str]) -> None:
        target = BACKUP_DIR / f"lista_{course.course_id}_{day:%Y-%m-%d}_{datetime.now():%H%M%S}.csv"
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["ID", "Nombre", day.isoformat()])
                for student in course.students:
                    writer.writerow(
                        [student.student_id, student.name, 1 if student.student_id in present_ids else 0]
                    )
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"No se pudo crear el respaldo de la lista:\n{error}")
            return
        messagebox.showwarning(
            APP_TITLE, f"La lista no entró al Excel. Se guardó un respaldo en:\n{target}"
        )

    def on_tick(self, now: datetime) -> None:
        self._next_var.set(describe_next(self._state.repository.courses, now))
        if self._session is None:
            self._try_auto_start(now)
            return
        remaining = int((self._session_end - now).total_seconds())
        if remaining <= 0:
            self.finish_session()
            return
        minutes, seconds = divmod(remaining, 60)
        self._timer_var.set(f"Tiempo restante: {minutes:02d}:{seconds:02d}")
