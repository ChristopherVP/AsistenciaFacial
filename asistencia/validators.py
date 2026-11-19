from __future__ import annotations

import re
import unicodedata

from .config import (
    MAX_PASSWORD_LENGTH,
    MAX_USERNAME_LENGTH,
    MAX_PROVINCE_CODE,
    MIN_ANSWER_LENGTH,
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    NAME_MAX_LENGTH,
)
from .errors import ValidationError

LETTERS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
NAME_PATTERN = re.compile(rf"^[{LETTERS}]+( [{LETTERS}]+)*$")
CEDULA_INPUT_PATTERN = re.compile(r"^[0-9]{0,10}$")
NAME_INPUT_PATTERN = re.compile(rf"^[{LETTERS} ]{{0,{NAME_MAX_LENGTH}}}$")
DIGITS_ONLY = re.compile(r"^[0-9]+$")
USERNAME_INPUT_PATTERN = re.compile(rf"^[A-Za-z0-9._]{{0,{MAX_USERNAME_LENGTH}}}$")
USERNAME_PATTERN = re.compile(
    rf"^[a-z][a-z0-9._]{{{MIN_USERNAME_LENGTH - 1},{MAX_USERNAME_LENGTH - 1}}}$"
)


def allows_cedula_input(text: str) -> bool:
    return CEDULA_INPUT_PATTERN.match(text) is not None


def allows_name_input(text: str) -> bool:
    return NAME_INPUT_PATTERN.match(text) is not None


def allows_username_input(text: str) -> bool:
    return USERNAME_INPUT_PATTERN.match(text) is not None


def normalize_username(text: str) -> str:
    value = text.strip().lower()
    if not value:
        raise ValidationError("Escribe el nombre de usuario.")
    if USERNAME_PATTERN.match(value) is None:
        raise ValidationError(
            f"Usuario de {MIN_USERNAME_LENGTH} a {MAX_USERNAME_LENGTH} caracteres: "
            "empieza con letra; solo letras, números, punto o guion bajo."
        )
    return value


def validate_cedula(text: str) -> str:
    value = text.strip()
    if not value:
        raise ValidationError("Escribe la cédula.")
    if DIGITS_ONLY.match(value) is None:
        raise ValidationError("La cédula solo puede tener números.")
    if len(value) != 10:
        raise ValidationError("La cédula debe tener exactamente 10 dígitos.")
    province = int(value[:2])
    if not 1 <= province <= MAX_PROVINCE_CODE:
        raise ValidationError(
            f"Los dos primeros dígitos deben estar entre 01 y {MAX_PROVINCE_CODE}."
        )
    if int(value[2]) > 5:
        raise ValidationError("El tercer dígito de la cédula debe ser de 0 a 5.")
    total = 0
    for position, char in enumerate(value[:9]):
        product = int(char) * (2 if position % 2 == 0 else 1)
        total += product - 9 if product > 9 else product
    check_digit = (10 - total % 10) % 10
    if check_digit != int(value[9]):
        raise ValidationError("Cédula no válida: el dígito verificador no coincide.")
    return value


def normalize_full_name(text: str) -> str:
    clean = " ".join(text.split())
    if not clean:
        raise ValidationError("Escribe los apellidos y nombres.")
    if NAME_PATTERN.match(clean) is None:
        raise ValidationError("Los apellidos y nombres solo pueden tener letras y espacios.")
    if len(clean.split()) < 2:
        raise ValidationError("Escribe apellidos y nombres (al menos dos palabras).")
    if len(clean) > NAME_MAX_LENGTH:
        raise ValidationError(f"Máximo {NAME_MAX_LENGTH} caracteres.")
    return clean.upper()


def name_sort_key(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold()


def validate_password(password: str, confirmation: str) -> str:
    if not password:
        raise ValidationError("Escribe la contraseña.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError(
            f"La contraseña no puede pasar de {MAX_PASSWORD_LENGTH} caracteres."
        )
    if password != confirmation:
        raise ValidationError("Las contraseñas no coinciden.")
    return password


def normalize_answer(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", " ".join(text.split()))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    answer = stripped.casefold()
    if len(answer) < MIN_ANSWER_LENGTH:
        raise ValidationError(
            f"La respuesta de seguridad debe tener al menos {MIN_ANSWER_LENGTH} caracteres."
        )
    return answer
