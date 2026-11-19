from __future__ import annotations

import csv
import tkinter as tk
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

from ..attendance import AttendanceBook, AttendanceSession
from ..camera import Camera, render_frame
from ..config import (
    APP_TITLE,
    BACKUP_DIR,
    COLOR_ACCENT,
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
    precision_for,
)
from ..errors import AttendanceError, CameraError
from ..face_engine import Gallery
from ..models import Course, FaceResult, RecordResult, Slot, parse_time
from ..scheduler import describe_next, due_courses
from ..voice import Speaker
from .state import AppState
from .widgets import Card, CameraView, StatCard, Table, make_chip, set_chip

NOTICE_COLORS = {
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "info": COLOR_PRIMARY,
    "error": COLOR_DANGER,
}
GRAY = "#7F8C8D"
ALL_PRESENT_DELAY_MS = 1500  # deja ver el último «registrado» antes de guardar
END_WARNING_SECONDS = 60
SAY_ALL_PRESENT = "Lista guardada. Todos los estudiantes han asistido."


@dataclass(frozen=True)
class ListSnapshot:
    """Resultado de UNA lista: solo los estudiantes que estaban en ese momento."""

    course_id: str
    moment: datetime
    roster_ids: frozenset[str]
    present: dict[str, datetime]

    @property
    def present_count(self) -> int:
        return len(self.roster_ids & self.present.keys())

    @property
    def absent_count(self) -> int:
        return len(self.roster_ids) - self.present_count


class AttendanceTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._session: AttendanceSession | None = None
        self._course: Course | None = None
        self._camera: Camera | None = None
        self._column: int | None = None
        self._live_failed = False
        self._session_start = datetime.now()
        self._session_end: datetime | None = None  # None = lista manual, sin hora de fin
        self._results: tuple[FaceResult, ...] = ()
        self._frame_count = 0
        self._read_failures = 0
        self._loop_id: str | None = None
        self._notice_job: str | None = None
        self._final: ListSnapshot | None = None
        self._auto_attempts: set[tuple[str, str]] = set()
        self._speaker = Speaker()
        self._saved_ok = False
        self._all_present_job: str | None = None
        self._end_warned = False
        self._course_ids: dict[str, str] = {}
        self._course_var = tk.StringVar()
        self._status_var = tk.StringVar()
        self._timer_var = tk.StringVar()
        self._timer_caption_var = tk.StringVar()
        self._next_var = tk.StringVar()
        self._build()
        state.subscribe(self.refresh_courses)
        self.refresh_courses()

    @property
    def is_running(self) -> bool:
        return self._session is not None

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        camera_card = Card(self, padding=14)
        camera_card.grid(row=0, column=0, sticky="n")
        top = ttk.Frame(camera_card.body, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Cámara en vivo", style="CardTitle.TLabel").pack(side="left")
        self._chip = make_chip(top, "LISTO", COLOR_ACCENT)
        self._chip.pack(side="right")
        self._notice = tk.Label(
            camera_card.body,
            text="",
            bg="white",
            fg="white",
            font=(FONT_FAMILY, 12, "bold"),
            anchor="w",
            justify="left",
            height=2,
            padx=12,
            wraplength=VIEW_WIDTH - 24,
        )
        self._notice.pack(fill="x", pady=(0, 8))
        self._view = CameraView(camera_card.body, "Cámara apagada")
        self._view.pack()
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        info = Card(right)
        info.pack(fill="x")
        ttk.Label(info.body, text="Curso", style="CardTitle.TLabel").pack(anchor="w")
        self._course_combo = ttk.Combobox(
            info.body, textvariable=self._course_var, state="readonly", font=(FONT_FAMILY, 11)
        )
        self._course_combo.pack(fill="x", pady=(2, 8))
        self._course_combo.bind("<<ComboboxSelected>>", lambda _: self._render_roster())
        ttk.Label(info.body, textvariable=self._status_var, style="Status.TLabel", wraplength=380).pack(
            anchor="w"
        )
        ttk.Label(info.body, textvariable=self._timer_caption_var, style="Hint.TLabel").pack(anchor="w")
        ttk.Label(info.body, textvariable=self._timer_var, style="Timer.TLabel").pack(anchor="w")
        ttk.Label(info.body, textvariable=self._next_var, style="Hint.TLabel", wraplength=380).pack(
            anchor="w", pady=(2, 0)
        )
        stats = ttk.Frame(right)
        stats.pack(fill="x", pady=10)
        for column in range(3):
            stats.columnconfigure(column, weight=1, uniform="stats")
        self._present_stat = StatCard(stats, "Presentes", COLOR_SUCCESS)
        self._absent_stat = StatCard(stats, "Sin registrar", COLOR_DANGER)
        self._total_stat = StatCard(stats, "Total", COLOR_PRIMARY)
        for column, card in enumerate((self._present_stat, self._absent_stat, self._total_stat)):
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        roster = Card(right)
        roster.pack(fill="both", expand=True)
        ttk.Label(roster.body, text="Lista del curso (A-Z por apellidos)", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        self._table = Table(
            roster.body,
            (
                ("n", "#", 32, "center", False),
                ("nombre", "Apellidos y nombres", 170, "w", True),
                ("estado", "Estado", 95, "center", False),
                ("hora", "Hora", 72, "center", False),
            ),
            height=9,
        )
        self._table.tag("present", foreground=COLOR_SUCCESS)
        self._table.tag("absent", foreground=COLOR_DANGER)
        self._table.tag("waiting", foreground=COLOR_MUTED)
        self._table.pack(fill="both", expand=True)
        buttons = ttk.Frame(roster.body, style="Card.TFrame")
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
        self._notice.configure(text="", bg="white")

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
                else "Cree un curso en la pestaña Cursos para empezar"
            )
        self._render_roster()

    def _selected_course(self) -> Course | None:
        return self._state.repository.get(self._course_ids.get(self._course_var.get()))

    def _roster_context(self) -> tuple[Course | None, dict[str, datetime], str]:
        if self._session is not None and self._course is not None:
            return self._course, self._session.present, "live"
        course = self._selected_course()
        if course is not None and self._final is not None and self._final.course_id == course.course_id:
            return course, self._final.present, "final"
        return course, {}, "idle"

    def _render_roster(self) -> None:
        course, present, mode = self._roster_context()
        self._table.clear()
        if course is None:
            for stat in (self._present_stat, self._absent_stat, self._total_stat):
                stat.set("–")
            return
        final = self._final if mode == "final" else None
        for number, student in enumerate(course.students, start=1):
            moment = present.get(student.student_id)
            if final is not None and student.student_id not in final.roster_ids:
                values, tag = ("Nuevo", "–"), "waiting"  # se registró después de esa lista
            elif moment is not None:
                values, tag = ("Presente", f"{moment:%H:%M:%S}"), "present"
            elif mode == "final":
                values, tag = ("Falta", "–"), "absent"
            elif mode == "live":
                values, tag = ("Sin registrar", "–"), "waiting"
            else:
                values, tag = ("–", "–"), "waiting"
            self._table.add((number, student.name, *values), iid=student.student_id, tags=(tag,))
        total = len(course.students)
        if mode == "idle":
            self._present_stat.set("–", "Presentes")
            self._absent_stat.set("–", "Sin registrar")
        elif final is not None:
            # Cifras de esa lista, no del curso actual: nunca dan negativos.
            self._present_stat.set(str(final.present_count), "Presentes")
            self._absent_stat.set(str(final.absent_count), "Faltas")
            total = len(final.roster_ids)
        else:
            self._present_stat.set(str(len(present)), "Presentes")
            self._absent_stat.set(str(total - len(present)), "Sin registrar")
        self._total_stat.set(str(total))

    @staticmethod
    def _book(course: Course) -> AttendanceBook:
        return AttendanceBook(Path(course.excel_path), course.name)

    def _start_manual(self) -> None:
        course = self._selected_course()
        if course is None:
            self._show_notice("Primero cree un curso en la pestaña Cursos.", "info")
            return
        if not course.students:
            self._show_notice(f"«{course.name}» no tiene estudiantes registrados.", "warning")
            return
        # Manual: sin hora de fin. Corre desde ahora y la cámara sigue encendida
        # hasta que se pulse «Finalizar y guardar».
        self._begin(course, None, automatic=False)

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
        window = self.winfo_toplevel()
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)
        window.after(1500, lambda: window.attributes("-topmost", False))
        end = datetime.combine(now.date(), parse_time(slot.end))
        self._begin(course, end, automatic=True)
        if self._session is not None:  # la cámara abrió bien
            self._speaker.speak(
                f"La lista de {course.name} va a empezar. Acérquese a la cámara para registrarse."
            )

    def _begin(self, course: Course, end: datetime | None, automatic: bool) -> None:
        try:
            camera = self._state.open_camera()
        except CameraError as error:
            self._report_start_error(str(error), automatic)
            return
        try:
            column = self._book(course).start_list(datetime.now(), course.students)
        except AttendanceError as error:
            camera.release()
            self._report_start_error(str(error), automatic)
            return
        self._camera = camera
        self._course = course
        self._column = column
        self._live_failed = False
        self._final = None
        level = precision_for(self._state.settings.threshold)
        self._session = AttendanceSession(
            self._state.engine,
            Gallery(course.students),
            level.threshold,
            level.margin,
            level.confirm_frames,
        )
        self._session_start = datetime.now()
        self._session_end = end
        self._end_warned = False
        self._saved_ok = False
        self._timer_caption_var.set(
            "Tiempo transcurrido (termina al pulsar «Finalizar y guardar»)"
            if end is None
            else "Tiempo restante de la clase (termina sola)"
        )
        self._update_timer(self._session_start)
        self._results = ()
        self._frame_count = 0
        self._read_failures = 0
        self._state.session_active = True
        self._course_combo.configure(state="disabled")
        self._status_var.set(f"Tomando lista · {course.name}")
        set_chip(self._chip, "EN CURSO", COLOR_SUCCESS)
        self._start_button.configure(state="disabled")
        self._stop_button.configure(state="normal")
        self._show_notice("Cámara activa: acérquese para registrarse", "info")
        self._render_roster()
        self._frame_loop()

    def _report_start_error(self, message: str, automatic: bool) -> None:
        if automatic:
            self._skip_automatic(f"Lista automática omitida: {message}")
        else:
            messagebox.showerror(APP_TITLE, message)

    def _mark_live(self, student_id: str) -> None:
        if self._live_failed or self._column is None or self._course is None:
            return
        try:
            self._book(self._course).mark_present(self._column, student_id)
        except AttendanceError:
            self._live_failed = True
            self._show_notice(
                "Excel abierto: la asistencia se guardará al finalizar la lista", "warning", NOTICE_MS * 2
            )

    def _handle_events(self, events: tuple[tuple[str, str], ...]) -> None:
        if not events or self._course is None:
            return
        names = {student.student_id: student.name for student in self._course.students}
        registered = False
        for kind, student_id in events:
            name = names.get(student_id, student_id)
            if kind == "registered":
                self._show_notice(f"✔  {name}  registrado", "success")
                self._mark_live(student_id)
                registered = True
            else:
                self._show_notice(f"ℹ  {name}  ya está registrado", "warning")
        if registered:
            self._render_roster()
            self._check_all_present()

    def _all_present(self) -> bool:
        if self._session is None or self._course is None or not self._course.students:
            return False
        present = self._session.present
        return all(student.student_id in present for student in self._course.students)

    def _check_all_present(self) -> None:
        if self._all_present() and self._all_present_job is None:
            self._show_notice("✔  Todos asistieron · guardando la lista…", "success", ALL_PRESENT_DELAY_MS * 2)
            self._all_present_job = self.after(ALL_PRESENT_DELAY_MS, self._finish_all_present)

    def _finish_all_present(self) -> None:
        self._all_present_job = None
        if not self._all_present():  # el usuario ya finalizó a mano
            return
        self.finish_session()
        if self._saved_ok:
            self._speaker.speak(SAY_ALL_PRESENT)

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
        session, course, column = self._session, self._course, self._column
        if session is None or course is None or column is None:
            return
        self._session = None
        self._course = None
        self._column = None
        if self._all_present_job is not None:
            self.after_cancel(self._all_present_job)
            self._all_present_job = None
        if self._loop_id is not None:
            self.after_cancel(self._loop_id)
            self._loop_id = None
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        self._state.session_active = False
        self._view.clear()
        self._timer_var.set("")
        self._timer_caption_var.set("")
        self._course_combo.configure(state="readonly")
        self._start_button.configure(state="normal")
        self._stop_button.configure(state="disabled")
        self._status_var.set("Guardando lista…")
        set_chip(self._chip, "GUARDANDO", COLOR_WARNING)
        self.update_idletasks()
        present = session.present
        self._final = ListSnapshot(
            course_id=course.course_id,
            moment=datetime.now(),
            roster_ids=frozenset(student.student_id for student in course.students),
            present=present,
        )
        result = self._finalize(course, column, frozenset(present))
        if result is None:
            self._status_var.set("Lista no guardada en Excel")
            set_chip(self._chip, "ERROR", COLOR_DANGER)
            self._show_notice("La lista no se guardó en el Excel", "error", NOTICE_MS * 2)
        else:
            self._saved_ok = True
            self._status_var.set(f"Lista guardada · {course.name} · {self._final.moment:%d/%m/%Y %H:%M}")
            set_chip(self._chip, "FINALIZADA", GRAY)
            self._show_notice(
                f"Lista guardada · Presentes {result.present} · Faltas {result.total - result.present} · "
                f"columna {result.column_letter}",
                "success",
                NOTICE_MS * 2,
            )
        self._render_roster()

    def _finalize(self, course: Course, column: int, present_ids: frozenset[str]) -> RecordResult | None:
        while True:
            try:
                return self._book(course).finalize(column, present_ids, course.students)
            except AttendanceError as error:
                if messagebox.askretrycancel("No se pudo guardar", f"{error}\n\n¿Reintentar?"):
                    continue
                self._write_backup(course, present_ids)
                return None

    def _write_backup(self, course: Course, present_ids: frozenset[str]) -> None:
        moment = datetime.now()
        target = BACKUP_DIR / f"lista_{course.course_id}_{moment:%Y-%m-%d_%H%M%S}.csv"
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Cédula", "Apellidos y nombres", date.today().isoformat()])
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
        if self._session_end is not None and now >= self._session_end:
            self.finish_session()
            return
        self._update_timer(now)
        if (
            self._session_end is not None
            and not self._end_warned
            and (self._session_end - now).total_seconds() <= END_WARNING_SECONDS
        ):
            self._end_warned = True
            self._speaker.speak("Queda un minuto para finalizar la lista.")

    def _update_timer(self, now: datetime) -> None:
        """Manual: cronómetro desde que se pulsó «Iniciar». Automática: cuenta regresiva."""
        if self._session_end is None:
            seconds_total = max(0, int((now - self._session_start).total_seconds()))
        else:
            seconds_total = max(0, int((self._session_end - now).total_seconds()))
        hours, rest = divmod(seconds_total, 3600)
        minutes, seconds = divmod(rest, 60)
        self._timer_var.set(
            f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
        )
