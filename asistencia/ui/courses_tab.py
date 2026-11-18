from __future__ import annotations

import os
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from ..attendance import AttendanceBook
from ..config import (
    APP_TITLE,
    COLOR_ACCENT,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
)
from ..errors import AttendanceError, CameraError, ValidationError
from ..models import Course, Student
from .dialogs import NameDialog, RegistrationDialog, SlotDialog
from .state import AppState
from .widgets import Card, Table, make_chip

GRAY = "#7F8C8D"


class CoursesTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._selected_id: str | None = None
        self._refreshing = False
        self._title_var = tk.StringVar()
        self._excel_var = tk.StringVar()
        self._schedule_text_var = tk.StringVar()
        self._enabled_var = tk.BooleanVar()
        self._build()
        state.subscribe(self._refresh_list)
        self._refresh_list()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        left = Card(self, padding=14)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left.body, text="Mis cursos", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self._courses_table = Table(
            left.body,
            (("curso", "Curso", 190, "w", True), ("est", "Estud.", 60, "center", False)),
            height=12,
        )
        self._courses_table.pack(fill="both", expand=True)
        self._courses_table.tree.bind("<<TreeviewSelect>>", lambda _: self._on_select())
        ttk.Button(left.body, text="➕  Nuevo curso", style="Primary.TButton", command=self._new_course).pack(
            fill="x", pady=(12, 4)
        )
        ttk.Button(left.body, text="✏  Renombrar", style="Ghost.TButton", command=self._rename_course).pack(
            fill="x", pady=4
        )
        ttk.Button(left.body, text="🗑  Eliminar curso", style="Danger.TButton", command=self._delete_course).pack(
            fill="x", pady=4
        )
        self._right = ttk.Frame(self)
        self._right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        self._empty = Card(self._right, padding=30)
        ttk.Label(
            self._empty.body,
            text="Cree o seleccione un curso\npara administrar sus estudiantes, horarios y Excel.",
            style="Hint.TLabel",
            justify="center",
        ).pack()
        self._detail = ttk.Frame(self._right)
        self._build_detail(self._detail)

    def _build_detail(self, detail: ttk.Frame) -> None:
        header = Card(detail)
        header.pack(fill="x")
        row = ttk.Frame(header.body, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, textvariable=self._title_var, style="Title.TLabel").pack(side="left")
        self._students_chip = make_chip(row, "0 ESTUDIANTES", COLOR_PRIMARY)
        self._students_chip.pack(side="right")
        self._schedule_chip = make_chip(row, "SIN HORARIO", GRAY)
        self._schedule_chip.pack(side="right", padx=8)
        excel = Card(detail)
        excel.pack(fill="x", pady=(10, 0))
        ttk.Label(excel.body, text="📊  Archivo de asistencia (Excel)", style="CardTitle.TLabel").pack(anchor="w")
        excel_row = ttk.Frame(excel.body, style="Card.TFrame")
        excel_row.pack(fill="x", pady=(6, 0))
        ttk.Entry(excel_row, textvariable=self._excel_var, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(excel_row, text="Abrir", style="Ghost.TButton", command=self._open_excel).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(excel_row, text="Cambiar…", style="Ghost.TButton", command=self._choose_excel).pack(
            side="left", padx=(8, 0)
        )
        students = Card(detail)
        students.pack(fill="x", pady=(10, 0))
        ttk.Label(students.body, text="👥  Estudiantes (A-Z por apellidos)", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        self._students_table = Table(
            students.body,
            (
                ("n", "#", 40, "center", False),
                ("cedula", "Cédula", 140, "center", False),
                ("nombre", "Apellidos y nombres", 420, "w", True),
            ),
            height=6,
        )
        self._students_table.pack(fill="x")
        student_buttons = ttk.Frame(students.body, style="Card.TFrame")
        student_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(
            student_buttons, text="➕  Agregar estudiante", style="Primary.TButton", command=self._add_student
        ).pack(side="left")
        ttk.Button(
            student_buttons, text="Quitar seleccionado", style="Ghost.TButton", command=self._remove_student
        ).pack(side="left", padx=8)
        schedule = Card(detail)
        schedule.pack(fill="x", pady=(10, 0))
        title_row = ttk.Frame(schedule.body, style="Card.TFrame")
        title_row.pack(fill="x", pady=(0, 6))
        ttk.Label(title_row, text="⏰  Horario de lista automática", style="CardTitle.TLabel").pack(side="left")
        ttk.Checkbutton(
            title_row,
            textvariable=self._schedule_text_var,
            variable=self._enabled_var,
            style="Day.Toolbutton",
            command=self._toggle_schedule,
        ).pack(side="right")
        self._slots_table = Table(
            schedule.body,
            (
                ("dias", "Días", 300, "w", True),
                ("inicio", "Inicio", 80, "center", False),
                ("fin", "Fin", 80, "center", False),
                ("duracion", "Duración", 90, "center", False),
            ),
            height=3,
        )
        self._slots_table.pack(fill="x")
        slot_buttons = ttk.Frame(schedule.body, style="Card.TFrame")
        slot_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(slot_buttons, text="➕  Agregar horario", style="Primary.TButton", command=self._add_slot).pack(
            side="left"
        )
        ttk.Button(slot_buttons, text="Quitar horario", style="Ghost.TButton", command=self._remove_slot).pack(
            side="left", padx=8
        )
        ttk.Label(
            schedule.body,
            text="La lista se toma sola dentro de cada intervalo, solo a los estudiantes de este curso. "
            "El programa debe estar abierto.",
            style="Hint.TLabel",
            wraplength=680,
        ).pack(anchor="w", pady=(8, 0))

    def _current(self) -> Course | None:
        return self._state.repository.get(self._selected_id)

    def _locked(self) -> bool:
        if self._state.session_active:
            messagebox.showinfo(APP_TITLE, "Finalice la lista en curso antes de hacer cambios.")
            return True
        return False

    def _refresh_list(self) -> None:
        self._refreshing = True
        self._courses_table.clear()
        courses = self._state.repository.courses
        for course in courses:
            self._courses_table.add((course.name, len(course.students)), iid=course.course_id)
        if self._selected_id and any(course.course_id == self._selected_id for course in courses):
            self._courses_table.select(self._selected_id)
        else:
            self._selected_id = None
        self._refreshing = False
        self._show_selected()

    def _on_select(self) -> None:
        if self._refreshing:
            return
        self._selected_id = self._courses_table.selected()
        self._show_selected()

    def _show_selected(self) -> None:
        course = self._current()
        self._empty.pack_forget()
        self._detail.pack_forget()
        if course is None:
            self._empty.pack(fill="x")
            return
        self._detail.pack(fill="both", expand=True)
        self._title_var.set(course.name)
        self._excel_var.set(course.excel_path)
        self._enabled_var.set(course.schedule_enabled)
        self._schedule_text_var.set("● ACTIVADA" if course.schedule_enabled else "○ DESACTIVADA")
        count = len(course.students)
        self._students_chip.configure(text=f"{count} ESTUDIANTE" + ("" if count == 1 else "S"))
        if not course.slots:
            self._schedule_chip.configure(text="SIN HORARIO", bg=GRAY)
        elif course.schedule_enabled:
            self._schedule_chip.configure(text="AUTOMÁTICA ACTIVA", bg=COLOR_SUCCESS)
        else:
            self._schedule_chip.configure(text="AUTOMÁTICA APAGADA", bg=COLOR_ACCENT)
        self._students_table.clear()
        for number, student in enumerate(course.students, start=1):
            self._students_table.add((number, student.student_id, student.name), iid=student.student_id)
        self._slots_table.clear()
        for index, slot in enumerate(course.slots):
            self._slots_table.add(
                (slot.days_text, slot.start, slot.end, f"{slot.minutes} min"), iid=str(index)
            )

    def _save_update(self, update: Callable[[Course], Course]) -> Course:
        course = self._current()
        if course is None:
            raise ValidationError("Seleccione un curso.")
        updated = update(course)
        try:
            self._state.save_course(updated)
        except OSError as error:
            raise ValidationError(f"No se pudo guardar el curso: {error}") from error
        return updated

    def _run(self, update: Callable[[Course], Course]) -> bool:
        try:
            self._save_update(update)
        except ValidationError as error:
            messagebox.showerror(APP_TITLE, str(error))
            self._show_selected()
            return False
        return True

    def _new_course(self) -> None:
        if self._locked():
            return

        def accept(name: str) -> None:
            try:
                course = self._state.repository.create(name)
            except OSError as error:
                raise ValidationError(f"No se pudo crear el curso: {error}") from error
            self._selected_id = course.course_id
            self._state.notify_courses_changed()

        NameDialog(self, "Nuevo curso", "Se creará con su propio Excel", "", "Crear curso", accept)

    def _rename_course(self) -> None:
        course = self._current()
        if course is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un curso de la lista.")
            return
        if self._locked():
            return

        def accept(name: str) -> None:
            try:
                self._state.repository.rename(course.course_id, name)
            except OSError as error:
                raise ValidationError(
                    f"No se pudo renombrar el curso (¿el Excel está abierto?): {error}"
                ) from error
            self._state.notify_courses_changed()

        NameDialog(self, "Renombrar curso", course.name, course.name, "Guardar nombre", accept)

    def _delete_course(self) -> None:
        course = self._current()
        if course is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un curso de la lista.")
            return
        if self._locked():
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"¿Eliminar el curso «{course.name}» y sus {len(course.students)} estudiantes registrados?\n"
            "El archivo de Excel no se borra.",
        ):
            return
        try:
            self._state.repository.delete(course.course_id)
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"No se pudo eliminar el curso: {error}")
            return
        self._selected_id = None
        self._state.notify_courses_changed()

    def _choose_excel(self) -> None:
        course = self._current()
        if course is None or self._locked():
            return
        path = filedialog.asksaveasfilename(
            title=f"Excel de asistencia de {course.name}",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            confirmoverwrite=False,
            initialdir=str(Path(course.excel_path).parent),
            initialfile=Path(course.excel_path).name,
        )
        if path:
            self._run(lambda c: replace(c, excel_path=path))

    def _open_excel(self) -> None:
        course = self._current()
        if course is None:
            return
        path = Path(course.excel_path)
        if not path.exists():
            messagebox.showinfo(APP_TITLE, "El Excel aún no existe. Se crea al tomar la primera lista.")
            return
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            messagebox.showinfo(APP_TITLE, f"El archivo está en:\n{path}")

    def _add_student(self) -> None:
        course = self._current()
        if course is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un curso de la lista.")
            return
        if self._locked():
            return
        try:
            camera = self._state.open_camera()
        except CameraError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        taken = {student.student_id for student in course.students}
        RegistrationDialog(
            self,
            self._state.engine,
            camera,
            course.name,
            lambda cedula: cedula in taken,
            self._student_saved,
        )

    def _student_saved(self, student: Student) -> None:
        updated = self._save_update(lambda course: course.add_student(student))
        try:
            AttendanceBook(Path(updated.excel_path), updated.name).sync_students(updated.students)
        except AttendanceError as error:
            messagebox.showwarning(
                APP_TITLE,
                f"El estudiante se guardó, pero aún no se agregó al Excel:\n{error}\n\n"
                "Se agregará automáticamente en la próxima lista.",
            )

    def _remove_student(self) -> None:
        student_id = self._students_table.selected()
        if student_id is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un estudiante de la lista.")
            return
        if self._locked():
            return
        if messagebox.askyesno(
            APP_TITLE,
            f"¿Quitar la cédula {student_id} de este curso?\nSu fila en el Excel se conserva.",
        ):
            self._run(lambda course: course.remove_student(student_id))

    def _add_slot(self) -> None:
        if self._current() is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un curso de la lista.")
            return
        if self._locked():
            return
        SlotDialog(self, lambda slot: self._save_update(lambda course: course.add_slot(slot)))

    def _remove_slot(self) -> None:
        selected = self._slots_table.selected()
        if selected is None:
            messagebox.showinfo(APP_TITLE, "Seleccione un horario de la lista.")
            return
        if self._locked():
            return
        self._run(lambda course: course.remove_slot(int(selected)))

    def _toggle_schedule(self) -> None:
        if self._locked():
            self._show_selected()
            return
        enabled = self._enabled_var.get()
        course = self._current()
        if enabled and course is not None and not course.slots:
            messagebox.showinfo(APP_TITLE, "Agregue al menos un horario para que la lista automática funcione.")
        self._run(lambda c: replace(c, schedule_enabled=enabled))
