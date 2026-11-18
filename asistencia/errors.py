from __future__ import annotations


class AppError(Exception):
    pass


class ValidationError(AppError):
    pass


class ModelError(AppError):
    pass


class CameraError(AppError):
    pass


class AttendanceError(AppError):
    pass


class AlreadyTakenError(AttendanceError):
    pass


class AuthError(AppError):
    pass
