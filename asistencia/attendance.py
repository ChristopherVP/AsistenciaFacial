from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Sequence
from zipfile import BadZipFile

import numpy as np
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from .config import COLOR_PRIMARY, CONFIRM_FRAMES
from .errors import AlreadyTakenError, AttendanceError
from .face_engine import FaceEngine, Gallery
from .models import FaceResult, RecordResult, Student


class AttendanceSession:
    def __init__(
        self,
        engine: FaceEngine,
        gallery: Gallery,
        threshold: float,
        roster_ids: frozenset[str],
    ) -> None:
        self._engine = engine
        self._gallery = gallery
        self._threshold = threshold
        self._roster_ids = roster_ids
        self._streaks: dict[str, int] = {}
        self._present: dict[str, datetime] = {}

    @property
    def present(self) -> dict[str, datetime]:
        return dict(self._present)

    @property
    def complete(self) -> bool:
        return bool(self._roster_ids) and self._roster_ids <= self._present.keys()

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
        confirmed = {
            sid: datetime.now()
            for sid, count in self._streaks.items()
            if count >= CONFIRM_FRAMES and sid not in self._present
        }
        self._present = {**self._present, **confirmed}
        return tuple(results)


class AttendanceBook:
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
    def _as_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(value.strip(), pattern).date()
                except ValueError:
                    continue
        return None

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
            except (OSError, InvalidFileException, BadZipFile) as error:
                raise AttendanceError(f"No se pudo abrir el Excel ({error}).") from error
        sheet = workbook.active
        if is_new:
            sheet.title = self._sheet_title
        for column, title in ((1, "ID"), (2, "Nombre")):
            cell = sheet.cell(1, column)
            if cell.value in (None, ""):
                cell.value = title
            self._style_header(cell)
        sheet.column_dimensions["A"].width = 16
        sheet.column_dimensions["B"].width = 34
        sheet.freeze_panes = "C2"
        return workbook, sheet

    def _last_header_column(self, sheet) -> int:
        column = sheet.max_column
        while column > 2 and sheet.cell(1, column).value in (None, ""):
            column -= 1
        return max(column, 2)

    def _date_columns(self, sheet) -> dict[date, int]:
        columns: dict[date, int] = {}
        for column in range(3, self._last_header_column(sheet) + 1):
            day = self._as_date(sheet.cell(1, column).value)
            if day is not None:
                columns[day] = column
        return columns

    def _student_rows(self, sheet) -> dict[str, int]:
        rows: dict[str, int] = {}
        for row in range(2, sheet.max_row + 1):
            student_id = self._text(sheet.cell(row, 1).value)
            if student_id:
                rows[student_id] = row
        return rows

    def _with_students(self, sheet, students: Sequence[Student]) -> dict[str, int]:
        rows = self._student_rows(sheet)
        next_row = max(rows.values(), default=1) + 1
        added: dict[str, int] = {}
        for student in students:
            if student.student_id in rows or student.student_id in added:
                continue
            sheet.cell(next_row, 1, student.student_id)
            sheet.cell(next_row, 2, student.name)
            added = {**added, student.student_id: next_row}
            next_row += 1
        return {**rows, **added}

    def _save(self, workbook) -> None:
        try:
            workbook.save(self._path)
        except PermissionError as error:
            raise AttendanceError(
                "El Excel está abierto en otro programa. Ciérralo y vuelve a intentar."
            ) from error
        except OSError as error:
            raise AttendanceError(f"No se pudo guardar el Excel ({error}).") from error

    def has_date(self, day: date) -> bool:
        if not self._path.exists():
            return False
        _, sheet = self._load()
        return day in self._date_columns(sheet)

    def sync_students(self, students: Sequence[Student]) -> None:
        workbook, sheet = self._load()
        self._with_students(sheet, students)
        self._save(workbook)

    def record(
        self,
        day: date,
        present_ids: frozenset[str],
        students: Sequence[Student],
        replace_existing: bool = False,
    ) -> RecordResult:
        workbook, sheet = self._load()
        rows = self._with_students(sheet, students)
        columns = self._date_columns(sheet)
        if day in columns:
            if not replace_existing:
                raise AlreadyTakenError(f"Ya existe una lista para el {day:%d/%m/%Y}.")
            column = columns[day]
        else:
            column = self._last_header_column(sheet) + 1
            header = sheet.cell(1, column, day)
            header.number_format = "DD/MM/YYYY"
            self._style_header(header)
        sheet.column_dimensions[get_column_letter(column)].width = 12
        for student_id, row in rows.items():
            cell = sheet.cell(row, column, 1 if student_id in present_ids else 0)
            cell.alignment = Alignment(horizontal="center")
        self._save(workbook)
        present = sum(1 for student_id in rows if student_id in present_ids)
        return RecordResult(get_column_letter(column), present, len(rows))
