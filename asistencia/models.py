from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time

from .config import DAY_LABELS, TIME_PATTERN
from .errors import ValidationError
from .validators import name_sort_key

def parse_time(text: str) -> time:
    match = TIME_PATTERN.match(text)
    if match is None:
        raise ValidationError(f"Hora inválida: {text!r}. Usa el formato HH:MM.")
    return time(int(match.group(1)), int(match.group(2)))


@dataclass(frozen=True)
class Student:
    student_id: str
    name: str
    embeddings: tuple[tuple[float, ...], ...]


def sorted_students(students) -> tuple[Student, ...]:
    return tuple(sorted(students, key=lambda student: name_sort_key(student.name)))


@dataclass(frozen=True)
class Slot:
    days: tuple[int, ...]
    start: str
    end: str

    def __post_init__(self) -> None:
        if not self.days or any(day not in range(7) for day in self.days):
            raise ValidationError("Selecciona al menos un día de la semana.")
        if parse_time(self.start) >= parse_time(self.end):
            raise ValidationError(
                "La hora de fin debe ser posterior a la hora de inicio."
            )

    def contains(self, moment: datetime) -> bool:
        return (
            moment.weekday() in self.days
            and parse_time(self.start) <= moment.time() < parse_time(self.end)
        )

    @property
    def days_text(self) -> str:
        return ", ".join(DAY_LABELS[day] for day in sorted(self.days))

    @property
    def minutes(self) -> int:
        start = datetime.combine(date.today(), parse_time(self.start))
        end = datetime.combine(date.today(), parse_time(self.end))
        return int((end - start).total_seconds() // 60)

    @property
    def label(self) -> str:
        return f"{self.days_text}   ·   {self.start} a {self.end}"


@dataclass(frozen=True)
class Course:
    course_id: str
    name: str
    excel_path: str
    students: tuple[Student, ...] = ()
    slots: tuple[Slot, ...] = ()
    schedule_enabled: bool = False
    last_auto_date: str = ""

    def add_student(self, student: Student) -> Course:
        if any(item.student_id == student.student_id for item in self.students):
            raise ValidationError(
                f"Ya existe un estudiante con la cédula {student.student_id} en este curso."
            )
        return replace(self, students=sorted_students((*self.students, student)))

    def remove_student(self, student_id: str) -> Course:
        remaining = tuple(s for s in self.students if s.student_id != student_id)
        return replace(self, students=remaining)

    def add_slot(self, slot: Slot) -> Course:
        if slot in self.slots:
            raise ValidationError("Ese horario ya existe en el curso.")
        return replace(self, slots=(*self.slots, slot))

    def remove_slot(self, index: int) -> Course:
        remaining = tuple(s for i, s in enumerate(self.slots) if i != index)
        return replace(self, slots=remaining)


def course_from_dict(raw: dict) -> Course:
    students = sorted_students(
        Student(
            student_id=str(item["student_id"]),
            name=str(item["name"]),
            embeddings=tuple(
                tuple(float(value) for value in vector)
                for vector in item["embeddings"]
            ),
        )
        for item in raw.get("students", [])
    )
    slots = tuple(
        Slot(
            days=tuple(int(day) for day in item["days"]),
            start=str(item["start"]),
            end=str(item["end"]),
        )
        for item in raw.get("slots", [])
    )
    return Course(
        course_id=str(raw["course_id"]),
        name=str(raw["name"]),
        excel_path=str(raw["excel_path"]),
        students=students,
        slots=slots,
        schedule_enabled=bool(raw.get("schedule_enabled", False)),
        last_auto_date=str(raw.get("last_auto_date", "")),
    )


@dataclass(frozen=True)
class AppSettings:
    camera_index: int = 0
    camera_name: str = ""
    threshold: float = 0.40


@dataclass(frozen=True)
class FaceResult:
    box: tuple[int, int, int, int]
    label: str
    recognized: bool


@dataclass(frozen=True)
class CameraInfo:
    index: int
    name: str
    kind: str = "unknown"
    available: bool = True

    @property
    def is_integrated(self) -> bool:
        return self.kind == "integrated"


@dataclass(frozen=True)
class RecordResult:
    column_letter: str
    present: int
    total: int
