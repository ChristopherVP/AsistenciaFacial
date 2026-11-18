from __future__ import annotations

from typing import Callable

from ..auth import User, UserRepository
from ..camera import Camera, resolve_camera_index
from ..errors import AuthError
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
        users: UserRepository,
    ) -> None:
        self.engine = engine
        self.repository = repository
        self.settings = settings
        self.users = users
        self.current_user: User | None = None
        self.session_active = False
        self._settings_repository = settings_repository
        self._listeners: list[Callable[[], None]] = []

    def sign_in(self, user: User) -> None:
        self.current_user = user

    def sign_out(self) -> None:
        self.current_user = None

    def set_remember_current_user(self, remembered: bool) -> User:
        if self.current_user is None:
            raise AuthError("No hay una sesión iniciada.")
        self.current_user = self.users.set_remembered(self.current_user.cedula, remembered)
        return self.current_user

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

    def open_camera(self) -> Camera:
        index = resolve_camera_index(
            self.settings.camera_name, self.settings.camera_index
        )
        return Camera(index)
