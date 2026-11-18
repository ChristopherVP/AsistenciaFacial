from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

import numpy as np

from .config import (
    MAX_ROLL_RATIO,
    MAX_SAMPLES,
    MAX_YAW_RATIO,
    MIN_FACE_SCORE,
    REMIND_SECONDS,
    SAMPLE_INTERVAL,
    SCAN_TIMEOUT_SECONDS,
)

SAY_APPROACH = "Acerque su cara a la cámara, por favor."
SAY_REMIND = "Por favor, mire fijamente a la cámara."
SAY_DONE = "Rostro registrado."
SAY_DUPLICATE = "Este rostro ya está registrado. No se creó un registro nuevo."
SAY_FAIL = "No se pudo registrar el rostro. Intente de nuevo."
TEXT_APPROACH = "Acerque su cara a la cámara"
TEXT_LOOK = "Mire fijamente a la cámara"
TEXT_FIND_FACE = "Ubique su rostro frente a la cámara"
TEXT_FRONTAL = "Mire de frente a la cámara"
TEXT_DONE = "Rostro registrado"
TEXT_TIMEOUT = "No se pudo registrar el rostro. Mejore la luz, quítese gorra o lentes oscuros e intente de nuevo."

Box = tuple[int, int, int, int]


class Phase(Enum):
    SCAN = "scan"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class EnrollmentStatus:
    phase: Phase
    prompt: str
    progress: float
    speak: str | None = None
    box: Box | None = None


class Embedder(Protocol):
    def embed(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray: ...


def is_frontal(face: np.ndarray) -> bool:
    right_x, right_y = float(face[4]), float(face[5])
    left_x, left_y = float(face[6]), float(face[7])
    nose_x = float(face[8])
    eye_distance = abs(left_x - right_x)
    if eye_distance < 1.0:
        return False
    yaw = abs(nose_x - (left_x + right_x) / 2) / eye_distance
    roll = abs(left_y - right_y) / eye_distance
    return yaw <= MAX_YAW_RATIO and roll <= MAX_ROLL_RATIO


class FaceEnrollment:
    def __init__(self, engine: Embedder, clock: Callable[[], float] = time.monotonic) -> None:
        self._engine = engine
        self._clock = clock
        self._phase = Phase.SCAN
        self._samples: tuple[tuple[float, ...], ...] = ()
        self._started = clock()
        self._last_sample = self._started - SAMPLE_INTERVAL
        self._last_activity = self._started

    @property
    def samples(self) -> tuple[tuple[float, ...], ...]:
        return self._samples

    @property
    def progress(self) -> float:
        return min(1.0, len(self._samples) / MAX_SAMPLES)

    def begin(self) -> EnrollmentStatus:
        return EnrollmentStatus(Phase.SCAN, TEXT_LOOK, 0.0)

    def update(self, frame: np.ndarray, faces: np.ndarray) -> EnrollmentStatus:
        if self._phase is Phase.DONE:
            return EnrollmentStatus(Phase.DONE, TEXT_DONE, 1.0)
        if self._phase is Phase.FAILED:
            return EnrollmentStatus(Phase.FAILED, TEXT_TIMEOUT, self.progress)
        now = self._clock()
        if now - self._started >= SCAN_TIMEOUT_SECONDS:
            self._phase = Phase.FAILED
            return EnrollmentStatus(Phase.FAILED, TEXT_TIMEOUT, self.progress, speak=SAY_FAIL)
        speak = None
        if now - self._last_activity >= REMIND_SECONDS:
            speak = SAY_REMIND
            self._last_activity = now
        if len(faces) != 1 or float(faces[0][14]) < MIN_FACE_SCORE:
            return EnrollmentStatus(Phase.SCAN, TEXT_FIND_FACE, self.progress, speak=speak)
        face = faces[0]
        box = tuple(int(value) for value in face[:4])
        if not is_frontal(face):
            return EnrollmentStatus(Phase.SCAN, TEXT_FRONTAL, self.progress, speak=speak, box=box)
        if now - self._last_sample >= SAMPLE_INTERVAL:
            feature = self._engine.embed(frame, face)
            vector = tuple(float(value) for value in feature.flatten())
            self._samples = (*self._samples, vector)
            self._last_sample = now
            self._last_activity = now
        if len(self._samples) >= MAX_SAMPLES:
            self._phase = Phase.DONE
            return EnrollmentStatus(Phase.DONE, TEXT_DONE, 1.0, box=box)
        return EnrollmentStatus(Phase.SCAN, TEXT_LOOK, self.progress, speak=speak, box=box)
