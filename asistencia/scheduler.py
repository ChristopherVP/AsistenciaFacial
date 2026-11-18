from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from .config import DAY_LABELS
from .models import Course, Slot, parse_time


def active_slot(course: Course, now: datetime) -> Slot | None:
    return next((slot for slot in course.slots if slot.contains(now)), None)


def due_courses(
    courses: Sequence[Course], now: datetime
) -> tuple[tuple[Course, Slot], ...]:
    today = now.date().isoformat()
    due: list[tuple[Course, Slot]] = []
    for course in courses:
        if not course.schedule_enabled or course.last_auto_date == today:
            continue
        slot = active_slot(course, now)
        if slot is not None:
            due.append((course, slot))
    return tuple(due)


def next_run(course: Course, now: datetime) -> tuple[datetime, Slot] | None:
    if not course.schedule_enabled:
        return None
    best: tuple[datetime, Slot] | None = None
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        if offset == 0 and course.last_auto_date == day.isoformat():
            continue
        for slot in course.slots:
            if day.weekday() not in slot.days:
                continue
            start = datetime.combine(day, parse_time(slot.start))
            end = datetime.combine(day, parse_time(slot.end))
            if end <= now:
                continue
            if best is None or start < best[0]:
                best = (start, slot)
    return best


def describe_next(courses: Sequence[Course], now: datetime) -> str:
    candidates = [
        (run, course) for course in courses if (run := next_run(course, now)) is not None
    ]
    if not candidates:
        return "Sin listas automáticas programadas"
    (start, slot), course = min(candidates, key=lambda item: item[0][0])
    if start <= now:
        return f"En horario ahora: {course.name} · hasta las {slot.end}"
    return (
        f"Próxima lista automática: {course.name} · "
        f"{DAY_LABELS[start.weekday()]} {start:%d/%m} de {slot.start} a {slot.end}"
    )
