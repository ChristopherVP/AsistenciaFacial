from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable

from .config import (
    LOCKOUT_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    PBKDF2_ITERATIONS,
    SECURITY_QUESTIONS,
    USERS_FILE,
)
from .errors import AuthError, ValidationError
from .storage import write_json_atomic
from .validators import (
    name_sort_key,
    normalize_answer,
    normalize_full_name,
    normalize_username,
    validate_cedula,
    validate_password,
)

BAD_CREDENTIALS = "Usuario o contraseña incorrecta."


@dataclass(frozen=True)
class User:
    cedula: str
    full_name: str
    password_salt: str
    password_hash: str
    question: str
    answer_salt: str
    answer_hash: str
    iterations: int = PBKDF2_ITERATIONS
    remembered: bool = False
    username: str = ""


def _hash_secret(secret: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations).hex()


def _protect(secret: str, iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return salt.hex(), _hash_secret(secret, salt, iterations)


def _matches(secret: str, salt_hex: str, expected_hash: str, iterations: int) -> bool:
    candidate = _hash_secret(secret, bytes.fromhex(salt_hex), iterations)
    return hmac.compare_digest(candidate, expected_hash)


class LoginThrottle:
    """Bloquea unos segundos tras varios intentos fallidos (solo en memoria)."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_attempts: int = MAX_LOGIN_ATTEMPTS,
        lockout_seconds: float = LOCKOUT_SECONDS,
    ) -> None:
        self._clock = clock
        self._max_attempts = max_attempts
        self._lockout_seconds = lockout_seconds
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def check(self, key: str) -> None:
        remaining = self._locked_until.get(key, 0.0) - self._clock()
        if remaining > 0:
            raise AuthError(
                f"Demasiados intentos fallidos. Espere {int(remaining) + 1} s e intente de nuevo."
            )

    def register_failure(self, key: str) -> None:
        count = self._failures.get(key, 0) + 1
        if count >= self._max_attempts:
            self._failures.pop(key, None)
            self._locked_until[key] = self._clock() + self._lockout_seconds
        else:
            self._failures[key] = count

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)


def _user_from_dict(raw: dict) -> User:
    known = {item.name for item in fields(User)}
    user = User(**{key: value for key, value in raw.items() if key in known})
    bytes.fromhex(user.password_salt)
    bytes.fromhex(user.answer_salt)
    return user if user.username else replace(user, username=user.cedula)


class UserRepository:
    def __init__(
        self,
        path: Path = USERS_FILE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path = path
        self._throttle = LoginThrottle(clock)
        self.load_warning: str | None = None
        self._users: dict[str, User] = self._load()

    @property
    def has_users(self) -> bool:
        return bool(self._users)

    def get(self, cedula: str) -> User | None:
        return self._users.get(cedula)

    def find_by_username(self, username: str) -> User | None:
        wanted = username.strip().lower()
        return next((user for user in self._users.values() if user.username == wanted), None)

    def username_taken(self, username: str) -> bool:
        return self.find_by_username(username) is not None

    def remembered_users(self) -> tuple[User, ...]:
        saved = (user for user in self._users.values() if user.remembered)
        return tuple(sorted(saved, key=lambda user: name_sort_key(user.full_name)))

    def _load(self) -> dict[str, User]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            users = [_user_from_dict(item) for item in raw["users"]]
            return {user.cedula: user for user in users}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            self.load_warning = self._quarantine(error)
            return {}

    def _quarantine(self, error: Exception) -> str:
        backup = self._path.with_suffix(".corrupto")
        try:
            os.replace(self._path, backup)
            saved_in = f"Se guardó una copia en {backup.name}."
        except OSError:
            saved_in = "No se pudo guardar una copia del archivo."
        return f"No se pudo leer el archivo de usuarios ({error}). {saved_in}"

    def _persist(self, users: dict[str, User]) -> None:
        payload = {"users": [asdict(user) for user in users.values()]}
        try:
            write_json_atomic(self._path, payload)
        except OSError as error:
            raise AuthError(f"No se pudo guardar el archivo de usuarios: {error}") from error
        self._users = users

    def register(
        self,
        cedula: str,
        full_name: str,
        username: str,
        password: str,
        confirmation: str,
        question: str,
        answer: str,
    ) -> User:
        valid_cedula = validate_cedula(cedula)
        name = normalize_full_name(full_name)
        valid_username = normalize_username(username)
        validate_password(password, confirmation)
        if question not in SECURITY_QUESTIONS:
            raise ValidationError("Elija una pregunta de seguridad de la lista.")
        normalized_answer = normalize_answer(answer)
        if valid_cedula in self._users:
            raise ValidationError("Ya existe un usuario con esa cédula.")
        if self.username_taken(valid_username):
            raise ValidationError("Ese nombre de usuario ya está en uso. Elija otro.")
        password_salt, password_hash = _protect(password)
        answer_salt, answer_hash = _protect(normalized_answer)
        user = User(
            cedula=valid_cedula,
            full_name=name,
            username=valid_username,
            password_salt=password_salt,
            password_hash=password_hash,
            question=question,
            answer_salt=answer_salt,
            answer_hash=answer_hash,
        )
        self._persist({**self._users, user.cedula: user})
        return user

    def authenticate(self, username: str, password: str) -> User:
        key = f"login:{username.strip().lower()}"
        self._throttle.check(key)
        user = self.find_by_username(username)
        if user is None or not _matches(
            password, user.password_salt, user.password_hash, user.iterations
        ):
            self._throttle.register_failure(key)
            raise AuthError(BAD_CREDENTIALS)
        self._throttle.reset(key)
        return user

    def authenticate_remembered(self, cedula: str) -> User:
        user = self._users.get(cedula)
        if user is None or not user.remembered:
            raise AuthError("Este usuario ya no está guardado. Escriba su contraseña.")
        return user

    def security_question(self, username: str) -> str:
        user = self.find_by_username(username)
        if user is None:
            raise AuthError("No existe ese usuario.")
        return user.question

    def recover_password(
        self, username: str, answer: str, new_password: str, confirmation: str
    ) -> User:
        key = f"recover:{username.strip().lower()}"
        self._throttle.check(key)
        user = self.find_by_username(username)
        if user is None:
            raise AuthError("No existe ese usuario.")
        normalized_answer = normalize_answer(answer)
        if not _matches(normalized_answer, user.answer_salt, user.answer_hash, user.iterations):
            self._throttle.register_failure(key)
            raise AuthError("La respuesta de seguridad es incorrecta.")
        validate_password(new_password, confirmation)
        salt, password_hash = _protect(new_password, user.iterations)
        updated = replace(user, password_salt=salt, password_hash=password_hash)
        self._persist({**self._users, user.cedula: updated})
        self._throttle.reset(key)
        self._throttle.reset(f"login:{user.username}")
        return updated

    def set_remembered(self, cedula: str, remembered: bool) -> User:
        user = self._users.get(cedula)
        if user is None:
            raise AuthError("El usuario ya no existe.")
        updated = replace(user, remembered=remembered)
        self._persist({**self._users, cedula: updated})
        return updated
