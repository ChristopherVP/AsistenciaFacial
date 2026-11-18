from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from dataclasses import asdict, fields, replace
from pathlib import Path

from .config import COURSES_DIR, SETTINGS_FILE
from .errors import AppError, ValidationError
from .models import AppSettings, Course, course_from_dict

COURSE_FILE = "curso.json"
LEGACY_EXCEL_NAME = "asistencia.xlsx"
EXCEL_SUFFIX = "_ListaAsistencia.xlsx"
MAX_NAME_LENGTH = 60


def excel_file_name(course_name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", course_name).strip().rstrip(".")
    return f"{safe or 'Curso'}{EXCEL_SUFFIX}"


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


class SettingsRepository:
    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self._path = path

    def load(self) -> tuple[AppSettings, str | None]:
        if not self._path.exists():
            return AppSettings(), None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            known = {item.name for item in fields(AppSettings)}
            values = {key: value for key, value in raw.items() if key in known}
            return AppSettings(**values), None
        except (OSError, ValueError, TypeError, AttributeError) as error:
            message = (
                f"No se pudieron leer los ajustes ({error}). "
                "Se usarán los valores por defecto."
            )
            return AppSettings(), message

    def save(self, settings: AppSettings) -> None:
        write_json_atomic(self._path, asdict(settings))


class CourseRepository:
    def __init__(self, root: Path = COURSES_DIR) -> None:
        self._root = root
        self.load_warnings: list[str] = []
        self._courses: dict[str, Course] = self._load_all()

    @property
    def courses(self) -> tuple[Course, ...]:
        return tuple(sorted(self._courses.values(), key=lambda c: c.name.casefold()))

    def get(self, course_id: str | None) -> Course | None:
        return self._courses.get(course_id) if course_id else None

    def _load_all(self) -> dict[str, Course]:
        courses: dict[str, Course] = {}
        if not self._root.exists():
            return courses
        for folder in sorted(self._root.iterdir()):
            file = folder / COURSE_FILE
            if not file.is_file():
                continue
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                course = course_from_dict(raw)
            except (OSError, ValueError, KeyError, TypeError, AppError) as error:
                self.load_warnings.append(
                    f"No se pudo leer el curso de la carpeta {folder.name} ({error})."
                )
                continue
            course = self._migrate_excel_name(folder, course)
            courses[course.course_id] = course
        return courses

    def _migrate_excel_name(self, folder: Path, course: Course) -> Course:
        if Path(course.excel_path) != folder / LEGACY_EXCEL_NAME:
            return course
        target = folder / excel_file_name(course.name)
        try:
            if (folder / LEGACY_EXCEL_NAME).exists() and not target.exists():
                os.replace(folder / LEGACY_EXCEL_NAME, target)
            migrated = replace(course, excel_path=str(target))
            write_json_atomic(folder / COURSE_FILE, asdict(migrated))
        except OSError as error:
            self.load_warnings.append(
                f"No se pudo renombrar el Excel de «{course.name}» ({error})."
            )
            return course
        return migrated

    @staticmethod
    def _slug(name: str) -> str:
        ascii_name = (
            unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        )
        return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "curso"

    def _validated_name(self, name: str, ignore_id: str | None = None) -> str:
        clean = " ".join(name.split())
        if not clean:
            raise ValidationError("Escribe el nombre del curso.")
        if len(clean) > MAX_NAME_LENGTH:
            raise ValidationError(
                f"El nombre del curso no puede pasar de {MAX_NAME_LENGTH} caracteres."
            )
        for course in self._courses.values():
            if course.course_id != ignore_id and course.name.casefold() == clean.casefold():
                raise ValidationError("Ya existe un curso con ese nombre.")
        return clean

    def create(self, name: str) -> Course:
        clean = self._validated_name(name)
        course_id = f"{self._slug(clean)}-{uuid.uuid4().hex[:6]}"
        course = Course(
            course_id=course_id,
            name=clean,
            excel_path=str(self._root / course_id / excel_file_name(clean)),
        )
        self.save(course)
        return course

    def rename(self, course_id: str, name: str) -> Course:
        course = self._courses[course_id]
        new_name = self._validated_name(name, course_id)
        excel_path = course.excel_path
        current_default = self._root / course_id / excel_file_name(course.name)
        if Path(excel_path) == current_default:
            new_path = self._root / course_id / excel_file_name(new_name)
            if current_default.exists() and not new_path.exists():
                os.replace(current_default, new_path)
            excel_path = str(new_path)
        renamed = replace(course, name=new_name, excel_path=excel_path)
        self.save(renamed)
        return renamed

    def save(self, course: Course) -> None:
        write_json_atomic(self._root / course.course_id / COURSE_FILE, asdict(course))
        self._courses = {**self._courses, course.course_id: course}

    def delete(self, course_id: str) -> None:
        (self._root / course_id / COURSE_FILE).unlink(missing_ok=True)
        self._courses = {k: v for k, v in self._courses.items() if k != course_id}
