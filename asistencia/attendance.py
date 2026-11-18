from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Sequence
from zipfile import BadZipFile

import numpy as np
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from .config import COLOR_PRIMARY, CONFIRM_FRAMES
from .errors import AttendanceError
from .face_engine import FaceEngine, Gallery
from .models import FaceResult, RecordResult, Student
from .validators import name_sort_key


class AttendanceSession:
    def __init__(self, engine: FaceEngine, gallery: Gallery, threshold: float) -> None:
        self._engine = engine
        self._gallery = gallery
        self._threshold = threshold
        self._streaks: dict[str, int] = {}
        self._present: dict[str, datetime] = {}
        self._events: list[tuple[str, str]] = []

    @property
    def present(self) -> dict[str, datetime]:
        return dict(self._present)

    def pop_events(self) -> tuple[tuple[str, str], ...]:
        events = tuple(self._events)
        self._events = []
        return events

    def process(self, frame: np.ndarray) -> tuple[FaceResult, ...]:
        results: list[FaceResult] = []
        seen: set[str] = set()
        for face in self._engine.detect(frame):
            x, y, w, h = (int(value) for value in face[:4])
            student = self._gallery.identify(
                self._engine.embed(frame, face), self._threshold
            )
            if student is None:
                results.append(FaceResult((x, y, w, h), "Desconocido", False))
                continue
            seen.add(student.student_id)
            results.append(FaceResult((x, y, w, h), student.name, True))
        self._streaks = {sid: self._streaks.get(sid, 0) + 1 for sid in seen}
        confirmed: dict[str, datetime] = {}
        new_events: list[tuple[str, str]] = []
        for student_id, count in self._streaks.items():
            if count != CONFIRM_FRAMES:
                continue
            if student_id in self._present:
                new_events.append(("already", student_id))
            else:
                confirmed[student_id] = datetime.now()
                new_events.append(("registered", student_id))
        self._present = {**self._present, **confirmed}
        self._events = [*self._events, *new_events]
        return tuple(results)


class AttendanceBook:
    HEADER_FORMAT = "DD/MM/YYYY HH:MM"

    def __init__(self, path: Path, sheet_title: str = "Asistencia") -> None:
        self._path = path
        cleaned = re.sub(r"[\[\]:*?/\\]", "", sheet_title).strip()
        self._sheet_title = cleaned[:31] or "Asistencia"

    @staticmethod
    def _text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @staticmethod
    def _style_header(cell) -> None:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=COLOR_PRIMARY.lstrip("#"))
        cell.alignment = Alignment(horizontal="center", vertical="center")

    def _load(self):
        is_new = not self._path.exists()
        if is_new:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise AttendanceError(
                    f"No se pudo crear la carpeta del Excel ({error})."
                ) from error
            workbook = Workbook()
        else:
            try:
                workbook = load_workbook(self._path)
            except PermissionError as error:
                raise AttendanceError(
                    "El Excel está abierto en otro programa. Ciérralo y vuelve a intentar."
                ) from error
            except (OSError, InvalidFileException, BadZipFile) as error:
                raise AttendanceError(f"No se pudo abrir el Excel ({error}).") from error
        sheet = workbook.active
        if is_new:
            sheet.title = self._sheet_title
        for column, title in ((1, "Cédula"), (2, "Apellidos y nombres")):
            cell = sheet.cell(1, column)
            if cell.value in (None, ""):
                cell.value = title
            self._style_header(cell)
        sheet.column_dimensions["A"].width = 16
        sheet.column_dimensions["B"].width = 38
        sheet.freeze_panes = "C2"
        return workbook, sheet

    def _last_header_column(self, sheet) -> int:
        column = sheet.max_column
        while column > 2 and sheet.cell(1, column).value in (None, ""):
            column -= 1
        return max(column, 2)

    def _student_rows(self, sheet) -> dict[str, int]:
        rows: dict[str, int] = {}
        for row in range(2, sheet.max_row + 1):
            student_id = self._text(sheet.cell(row, 1).value)
            if student_id:
                rows[student_id] = row
        return rows

    def _sort_rows(self, sheet) -> None:
        last_column = self._last_header_column(sheet)
        last_row = sheet.max_row
        entries = []
        for row in range(2, last_row + 1):
            values = [sheet.cell(row, column).value for column in range(1, last_column + 1)]
            if self._text(values[0]):
                entries.append(values)
        ordered = sorted(entries, key=lambda values: name_sort_key(self._text(values[1])))
        for offset in range(last_row - 1):
            row = 2 + offset
            values = ordered[offset] if offset < len(ordered) else [None] * last_column
            for column, value in enumerate(values, start=1):
                sheet.cell(row, column).value = value
                if column >= 3 and offset < len(ordered):
                    sheet.cell(row, column).alignment = Alignment(horizontal="center")

    def _with_students(self, sheet, students: Sequence[Student]) -> dict[str, int]:
        rows = self._student_rows(sheet)
        next_row = max(rows.values(), default=1) + 1
        added = 0
        for student in students:
            if student.student_id in rows:
                continue
            sheet.cell(next_row, 1, student.student_id)
            sheet.cell(next_row, 2, student.name)
            rows = {**rows, student.student_id: next_row}
            next_row += 1
            added += 1
        if not added:
            return rows
        self._sort_rows(sheet)
        return self._student_rows(sheet)

    def _save(self, workbook) -> None:
        try:
            workbook.save(self._path)
        except PermissionError as error:
            raise AttendanceError(
                "El Excel está abierto en otro programa. Ciérralo y vuelve a intentar."
            ) from error
        except OSError as error:
            raise AttendanceError(f"No se pudo guardar el Excel ({error}).") from error

    def sync_students(self, students: Sequence[Student]) -> None:
        workbook, sheet = self._load()
        self._with_students(sheet, students)
        self._save(workbook)

    def start_list(self, moment: datetime, students: Sequence[Student]) -> int:
        workbook, sheet = self._load()
        rows = self._with_students(sheet, students)
        column = self._last_header_column(sheet) + 1
        header = sheet.cell(1, column, moment.replace(second=0, microsecond=0))
        header.number_format = self.HEADER_FORMAT
        self._style_header(header)
        sheet.column_dimensions[get_column_letter(column)].width = 18
        for row in rows.values():
            cell = sheet.cell(row, column, 0)
            cell.alignment = Alignment(horizontal="center")
        self._save(workbook)
        return column

    def mark_present(self, column: int, student_id: str) -> None:
        workbook, sheet = self._load()
        row = self._student_rows(sheet).get(student_id)
        if row is None:
            raise AttendanceError(f"La cédula {student_id} no está en el Excel.")
        cell = sheet.cell(row, column, 1)
        cell.alignment = Alignment(horizontal="center")
        self._save(workbook)

    def finalize(
        self, column: int, present_ids: frozenset[str], students: Sequence[Student]
    ) -> RecordResult:
        workbook, sheet = self._load()
        rows = self._with_students(sheet, students)
        for student_id, row in rows.items():
            cell = sheet.cell(row, column, 1 if student_id in present_ids else 0)
            cell.alignment = Alignment(horizontal="center")
        self._save(workbook)
        present = sum(1 for student_id in rows if student_id in present_ids)
        return RecordResult(get_column_letter(column), present, len(rows))
