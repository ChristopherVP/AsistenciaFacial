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
    COLOR_BG,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    FONT_FAMILY,
    FRAME_DELAY_MS,
    MAX_READ_FAILURES,
    NOTICE_MS,
    PROCESS_EVERY_N_FRAMES,
    VIEW_WIDTH,
)
from ..errors import AlreadyTakenError, AttendanceError, CameraError
from ..face_engine import Gallery
from ..models import Course, FaceResult, RecordResult, Slot, parse_time
from ..scheduler import describe_next, due_courses
from .state import AppState
from .widgets import CameraView

NOTICE_COLORS = {
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "info": COLOR_PRIMARY,
    "error": COLOR_DANGER,
}


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
        self._loop_id: str | None = None
        self._notice_job: str | None = None
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
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="n")
        self._notice = tk.Label(
            left,
            text="",
            bg=COLOR_BG,
            fg="white",
            font=(FONT_FAMILY, 12, "bold"),
            anchor="w",
            justify="left",
            height=2,
            padx=12,
            wraplength=VIEW_WIDTH - 24,
        )
        self._notice.pack(fill="x", pady=(0, 8))
        self._view = CameraView(left, "Cámara apagada")
        self._view.pack()
        panel = ttk.Frame(self, style="Card.TFrame", padding=16)
        panel.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        self.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Curso", style="CardTitle.TLabel").pack(anchor="w")
        self._course_combo = ttk.Combobox(
            panel, textvariable=self._course_var, state="readonly", width=34
        )
        self._course_combo.pack(fill="x", pady=(2, 10))
        self._course_combo.bind("<<ComboboxSelected>>", lambda _: self._render_roster())
        ttk.Label(panel, textvariable=self._status_var, style="Status.TLabel", wraplength=340).pack(
            anchor="w"
        )
        ttk.Label(panel, textvariable=self._timer_var, style="Card.TLabel").pack(
            anchor="w", pady=(2, 0)
        )
        ttk.Label(panel, textvariable=self._next_var, style="Hint.TLabel", wraplength=340).pack(
            anchor="w", pady=(2, 10)
        )
        ttk.Label(panel, textvariable=self._count_var, style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        self._roster_tree = ttk.Treeview(
            panel, columns=("nombre", "estado"), show="headings", height=12
        )
        self._roster_tree.heading("nombre", text="Apellidos y nombres")
        self._roster_tree.heading("estado", text="Estado")
        self._roster_tree.column("nombre", width=250)
        self._roster_tree.column("estado", width=100, anchor="center", stretch=False)
        self._roster_tree.tag_configure("present", foreground=COLOR_SUCCESS)
        self._roster_tree.tag_configure("pending", foreground=COLOR_MUTED)
        self._roster_tree.pack(fill="both", expand=True)
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

    def _show_notice(self, text: str, kind: str, milliseconds: int = NOTICE_MS) -> None:
        if self._notice_job is not None:
            self.after_cancel(self._notice_job)
        self._notice.configure(text=text, bg=NOTICE_COLORS[kind])
        self._notice_job = self.after(milliseconds, self._clear_notice)

    def _clear_notice(self) -> None:
        self._notice_job = None
        self._notice.configure(text="", bg=COLOR_BG)

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
        self._render_roster()

    def _selected_course(self) -> Course | None:
        return self._state.repository.get(self._course_ids.get(self._course_var.get()))

    def _render_roster(self) -> None:
        course = self._course if self._session is not None else self._selected_course()
        present = self._session.present if self._session is not None else {}
        self._roster_tree.delete(*self._roster_tree.get_children())
        if course is None:
            self._count_var.set("Presentes: 0 de 0 estudiantes")
            return
        for student in course.students:
            moment = present.get(student.student_id)
            self._roster_tree.insert(
                "",
                "end",
                iid=student.student_id,
                values=(student.name, f"✔ {moment:%H:%M:%S}" if moment else "Pendiente"),
                tags=("present" if moment else "pending",),
            )
        self._count_var.set(f"Presentes: {len(present)} de {len(course.students)} estudiantes")

    @staticmethod
    def _book(course: Course) -> AttendanceBook:
        return AttendanceBook(Path(course.excel_path), course.name)

    def _start_manual(self) -> None:
        course = self._selected_course()
        if course is None:
            self._show_notice("Primero crea un curso en la pestaña Cursos.", "info")
            return
        if not course.students:
            self._show_notice(f"«{course.name}» no tiene estudiantes registrados.", "warning")
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

    def _skip_automatic(self, message: str) -> None:
        self._status_var.set(message)
        self._show_notice(message, "warning", NOTICE_MS * 2)

    def _start_automatic(self, course: Course, slot: Slot, now: datetime) -> None:
        try:
            self._state.save_course(
                replace(course, last_auto_date=now.date().isoformat()), notify=False
            )
        except OSError as error:
            self._skip_automatic(f"No se pudo registrar la lista automática: {error}")
            return
        if not course.students:
            self._skip_automatic(f"Lista automática omitida: «{course.name}» no tiene estudiantes")
            return
        try:
            exists = self._book(course).has_date(now.date())
        except AttendanceError as error:
            self._skip_automatic(f"Lista automática omitida: {error}")
            return
        if exists:
            self._skip_automatic(f"Lista automática omitida: «{course.name}» ya tiene la lista de hoy")
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
            camera = self._state.open_camera()
        except CameraError as error:
            if automatic:
                self._skip_automatic(f"Lista automática omitida: {error}")
            else:
                messagebox.showerror(APP_TITLE, str(error))
            return
        self._camera = camera
        self._course = course
        self._session = AttendanceSession(
            self._state.engine, Gallery(course.students), self._state.settings.threshold
        )
        self._session_end = end
        self._replace_existing = replace_existing
        self._results = ()
        self._frame_count = 0
        self._read_failures = 0
        self._state.session_active = True
        self._course_combo.configure(state="disabled")
        self._status_var.set(f"Tomando lista: {course.name}")
        self._start_button.configure(state="disabled")
        self._stop_button.configure(state="normal")
        self._show_notice("Cámara activa: acérquese para registrarse", "info")
        self._render_roster()
        self._frame_loop()

    def _handle_events(self, events: tuple[tuple[str, str], ...]) -> None:
        if not events or self._course is None:
            return
        names = {student.student_id: student.name for student in self._course.students}
        registered = False
        for kind, student_id in events:
            name = names.get(student_id, student_id)
            if kind == "registered":
                self._show_notice(f"✔  {name}  registrado", "success")
                registered = True
            else:
                self._show_notice(f"ℹ  {name}  ya está registrado", "warning")
        if registered:
            self._render_roster()

    def _frame_loop(self) -> None:
        if self._session is None or self._camera is None:
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
                self._handle_events(self._session.pop_events())
            self._view.show(render_frame(frame, self._results))
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
        result = self._save_attendance(course, frozenset(session.present))
        if result is None:
            self._status_var.set("Lista no guardada en Excel")
            self._show_notice("La lista no se guardó en el Excel", "error", NOTICE_MS * 2)
        else:
            self._status_var.set(f"Lista de «{course.name}» guardada")
            self._show_notice(
                f"Lista guardada · Presentes {result.present} de {result.total} · "
                f"columna {result.column_letter}",
                "success",
                NOTICE_MS * 2,
            )
        self._render_roster()

    def _save_attendance(self, course: Course, present_ids: frozenset[str]) -> RecordResult | None:
        day = date.today()
        replace_existing = self._replace_existing
        while True:
            try:
                return self._book(course).record(
                    day, present_ids, course.students, replace_existing
                )
            except AlreadyTakenError:
                if messagebox.askyesno(
                    APP_TITLE,
                    f"Ya existe una lista de hoy de «{course.name}».\n¿Reemplazarla con esta?",
                ):
                    replace_existing = True
                    continue
                self._write_backup(course, day, present_ids)
                return None
            except AttendanceError as error:
                if messagebox.askretrycancel("No se pudo guardar", f"{error}\n\n¿Reintentar?"):
                    continue
                self._write_backup(course, day, present_ids)
                return None

    def _write_backup(self, course: Course, day: date, present_ids: frozenset[str]) -> None:
        target = BACKUP_DIR / f"lista_{course.course_id}_{day:%Y-%m-%d}_{datetime.now():%H%M%S}.csv"
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Cédula", "Apellidos y nombres", day.isoformat()])
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
