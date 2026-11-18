from __future__ import annotations

import re
import unicodedata

from .config import MAX_PROVINCE_CODE, NAME_MAX_LENGTH
from .errors import ValidationError

LETTERS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
NAME_PATTERN = re.compile(rf"^[{LETTERS}]+( [{LETTERS}]+)*$")
CEDULA_INPUT_PATTERN = re.compile(r"^[0-9]{0,10}$")
NAME_INPUT_PATTERN = re.compile(rf"^[{LETTERS} ]{{0,{NAME_MAX_LENGTH}}}$")
DIGITS_ONLY = re.compile(r"^[0-9]+$")


def allows_cedula_input(text: str) -> bool:
    return CEDULA_INPUT_PATTERN.match(text) is not None


def allows_name_input(text: str) -> bool:
    return NAME_INPUT_PATTERN.match(text) is not None


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
