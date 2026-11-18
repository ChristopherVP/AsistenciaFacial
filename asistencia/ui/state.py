from __future__ import annotations

from typing import Callable

from ..face_engine import FaceEngine
from ..models import AppSettings, Course
from ..storage import CourseRepository, SettingsRepository


class AppState:
    def __init__(
        self,
        engine: FaceEngine,
        repository: CourseRepository,
        settings_repository: SettingsRepository,
        settings: AppSettings,
    ) -> None:
        self.engine = engine
        self.repository = repository
        self.settings = settings
        self.session_active = False
        self._settings_repository = settings_repository
        self._listeners: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def notify_courses_changed(self) -> None:
        for callback in tuple(self._listeners):
            callback()

    def save_course(self, course: Course, notify: bool = True) -> None:
        self.repository.save(course)
        if notify:
            self.notify_courses_changed()

    def update_settings(self, settings: AppSettings) -> None:
        self._settings_repository.save(settings)
        self.settings = settings
