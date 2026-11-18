from __future__ import annotations

import os
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from ..attendance import AttendanceBook
from ..config import APP_TITLE
from ..errors import AttendanceError, CameraError, ValidationError
from ..models import Course, Student
from .dialogs import RegistrationDialog, SlotDialog
from .state import AppState


class CoursesTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, state: AppState) -> None:
        super().__init__(parent, padding=14)
        self._state = state
        self._selected_id: str | None = None
        self._refreshing = False
        self._title_var = tk.StringVar()
        self._excel_var = tk.StringVar()
        self._enabled_var = tk.BooleanVar()
        self._build()
        state.subscribe(self._refresh_list)
        self._refresh_list()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self, style="Card.TFrame", padding=14)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Cursos", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self._courses_tree = ttk.Treeview(
            left, columns=("nombre",), show="headings", height=14, selectmode="browse"
        )
        self._courses_tree.heading("nombre", text="Curso")
        self._courses_tree.column("nombre", width=230)
        self._courses_tree.pack(fill="y", expand=True)
        self._courses_tree.bind("<<TreeviewSelect>>", lambda _: self._on_select())
        ttk.Button(left, text="➕  Nuevo curso", style="Primary.TButton", command=self._new_course).pack(
            fill="x", pady=(10, 4)
        )
        ttk.Button(left, text="✏  Renombrar", command=self._rename_course).pack(fill="x", pady=4)
        ttk.Button(left, text="🗑  Eliminar curso", style="Danger.TButton", command=self._delete_course).pack(
            fill="x", pady=4
        )
        right = ttk.Frame(self, style="Card.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        self._empty_label = ttk.Label(
            right,
            text="Crea o selecciona un curso para ver sus estudiantes, su horario y su Excel.",
            style="Hint.TLabel",
        )
        self._detail = ttk.Frame(right, style="Card.TFrame")
        self._build_detail(self._detail)

    def _build_detail(self, detail: ttk.Frame) -> None:
        ttk.Label(detail, textvariable=self._title_var, style="Status.TLabel").pack(anchor="w")
        ttk.Label(detail, text="Excel de este curso", style="CardTitle.TLabel").pack(
            anchor="w", pady=(10, 2)
        )
        excel_row = ttk.Frame(detail, style="Card.TFrame")
        excel_row.pack(fill="x")
        ttk.Entry(excel_row, textvariable=self._excel_var, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(excel_row, text="Cambiar…", command=self._choose_excel).pack(side="left", padx=(8, 0))
        ttk.Button(excel_row, text="Abrir", command=self._open_excel).pack(side="left", padx=(8, 0))
        ttk.Label(detail, text="Estudiantes", style="CardTitle.TLabel").pack(anchor="w", pady=(12, 2))
        self._students_tree = ttk.Treeview(
            detail, columns=("cedula", "nombre"), show="headings", height=8
        )
        for column, title, width, anchor in (
            ("cedula", "Cédula", 140, "center"),
            ("nombre", "Apellidos y nombres (A-Z)", 420, "w"),
        ):
            self._students_tree.heading(column, text=title)
            self._students_tree.column(column, width=width, anchor=anchor, stretch=column == "nombre")
        self._students_tree.pack(fill="x")
        student_buttons = ttk.Frame(detail, style="Card.TFrame")
        student_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(
            student_buttons, text="➕  Agregar estudiante", style="Primary.TButton", command=self._add_student
        ).pack(side="left")
        ttk.Button(
            student_buttons, text="Eliminar seleccionado", command=self._remove_student
        ).pack(side="left", padx=8)
        ttk.Label(detail, text="Horario de la lista automática", style="CardTitle.TLabel").pack(
            anchor="w", pady=(12, 2)
        )
        self._slots_tree = ttk.Treeview(detail, columns=("horario",), show="headings", height=3)
        self._slots_tree.heading("horario", text="Días y horas en que se toma lista")
        self._slots_tree.column("horario", width=520)
        self._slots_tree.pack(fill="x")
        slot_buttons = ttk.Frame(detail, style="Card.TFrame")
        slot_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(slot_buttons, text="➕  Agregar horario", style="Primary.TButton", command=self._add_slot).pack(
            side="left"
        )
        ttk.Button(slot_buttons, text="Quitar horario", command=self._remove_slot).pack(side="left", padx=8)
        ttk.Checkbutton(
            detail,
            text="Tomar lista automáticamente en estos horarios (el programa debe estar abierto)",
            variable=self._enabled_var,
            style="Card.TCheckbutton",
            command=self._toggle_schedule,
        ).pack(anchor="w", pady=(8, 0))

    def _current(self) -> Course | None:
        return self._state.repository.get(self._selected_id)

    def _locked(self) -> bool:
        if self._state.session_active:
            messagebox.showinfo(APP_TITLE, "Finaliza la lista en curso antes de hacer cambios.")
            return True
        return False

    def _refresh_list(self) -> None:
        self._refreshing = True
        self._courses_tree.delete(*self._courses_tree.get_children())
        courses = self._state.repository.courses
        for course in courses:
            self._courses_tree.insert("", "end", iid=course.course_id, values=(course.name,))
        if self._selected_id and any(c.course_id == self._selected_id for c in courses):
            self._courses_tree.selection_set(self._selected_id)
        else:
            self._selected_id = None
        self._refreshing = False
        self._show_selected()

    def _on_select(self) -> None:
        if self._refreshing:
            return
        selection = self._courses_tree.selection()
        self._selected_id = selection[0] if selection else None
        self._show_selected()

    def _show_selected(self) -> None:
        course = self._current()
        self._empty_label.pack_forget()
        self._detail.pack_forget()
        if course is None:
            self._empty_label.pack(anchor="w")
            return
        self._detail.pack(fill="both", expand=True)
        self._title_var.set(course.name)
        self._excel_var.set(course.excel_path)
        self._enabled_var.set(course.schedule_enabled)
        self._students_tree.delete(*self._students_tree.get_children())
        for student in course.students:
            self._students_tree.insert(
                "", "end", iid=student.student_id,
                values=(student.student_id, student.name),
            )
        self._slots_tree.delete(*self._slots_tree.get_children())
        for index, slot in enumerate(course.slots):
            self._slots_tree.insert("", "end", iid=str(index), values=(slot.label,))

    def _save_update(self, update: Callable[[Course], Course]) -> Course:
        course = self._current()
        if course is None:
            raise ValidationError("Selecciona un curso.")
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
        name = simpledialog.askstring(APP_TITLE, "Nombre del nuevo curso:", parent=self)
        if name is None:
            return
        try:
            course = self._state.repository.create(name)
        except ValidationError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"No se pudo crear el curso: {error}")
            return
        self._selected_id = course.course_id
        self._state.notify_courses_changed()

    def _rename_course(self) -> None:
        course = self._current()
        if course is None or self._locked():
            return
        name = simpledialog.askstring(
            APP_TITLE, "Nuevo nombre del curso:", initialvalue=course.name, parent=self
        )
        if name is None:
            return
        try:
            self._state.repository.rename(course.course_id, name)
        except ValidationError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"No se pudo renombrar el curso: {error}")
            return
        self._state.notify_courses_changed()

    def _delete_course(self) -> None:
        course = self._current()
        if course is None or self._locked():
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"¿Eliminar el curso «{course.name}» y sus {len(course.students)} estudiantes "
            "registrados?\nEl archivo de Excel no se borra.",
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
        if course is None or self._locked():
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
            self._state.eyes,
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
        selection = self._students_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "Selecciona un estudiante de la lista.")
            return
        if self._locked():
            return
        student_id = selection[0]
        if messagebox.askyesno(
            APP_TITLE,
            f"¿Quitar la cédula {student_id} de este curso?\nSu fila en el Excel se conserva.",
        ):
            self._run(lambda course: course.remove_student(student_id))

    def _add_slot(self) -> None:
        if self._current() is None or self._locked():
            return
        SlotDialog(self, lambda slot: self._save_update(lambda course: course.add_slot(slot)))

    def _remove_slot(self) -> None:
        selection = self._slots_tree.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "Selecciona un horario de la lista.")
            return
        if self._locked():
            return
        index = int(selection[0])
        self._run(lambda course: course.remove_slot(index))

    def _toggle_schedule(self) -> None:
        if self._locked():
            self._show_selected()
            return
        enabled = self._enabled_var.get()
        course = self._current()
        if enabled and course is not None and not course.slots:
            messagebox.showinfo(
                APP_TITLE, "Agrega al menos un horario para que la lista automática funcione."
            )
        self._run(lambda c: replace(c, schedule_enabled=enabled))
