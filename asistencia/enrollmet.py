from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

import numpy as np

from .config import (
    CLOSE_GRACE_SECONDS,
    CLOSE_SECONDS,
    CLOSED_RATIO_MIN,
    EYE_CLOSED_FACTOR,
    LOOK_SECONDS,
    MAX_SAMPLES,
    MIN_CLOSED_FRAMES,
    MIN_EYE_CONTRAST,
    MIN_FACE_SCORE,
    MIN_SAMPLES,
    SAMPLE_INTERVAL,
)

SAY_LOOK = "Mire fijamente a la cámara"
SAY_CLOSE = "Ahora cierre los ojos"
SAY_DONE = "Listo. Registro confirmado."
SAY_FAIL = "No se pudo verificar. Intente de nuevo."
TEXT_FIND_FACE = "Ubique su rostro frente a la cámara"
TEXT_KEEP_CLOSED = "Mantenga los ojos cerrados"
TEXT_DONE = "Registro confirmado"
FAIL_OPEN = "No se pudo ver bien su rostro. Mejore la luz y quítese los lentes oscuros."
FAIL_CLOSE = (
    "No se confirmó que cerrara los ojos. Puede haber poca luz, o ser una foto en lugar de una persona."
)


class Phase(Enum):
    LOOK = "look"
    CLOSE = "close"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class EnrollmentStatus:
    phase: Phase
    prompt: str
    progress: float
    speak: str | None = None
    failed_phase: Phase | None = None


class Embedder(Protocol):
    def embed(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray: ...


class EyeChecker(Protocol):
    def openness(self, frame: np.ndarray, face: np.ndarray) -> float: ...


class FaceEnrollment:
    def __init__(
        self,
        engine: Embedder,
        eyes: EyeChecker,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._engine = engine
        self._eyes = eyes
        self._clock = clock
        self._phase = Phase.LOOK
        self._samples: tuple[tuple[float, ...], ...] = ()
        self._look_started: float | None = None
        self._last_sample = 0.0
        self._look_contrasts: list[float] = []
        self._baseline = 0.0
        self._close_entered = 0.0
        self._close_started: float | None = None
        self._closed_frames = 0
        self._open_frames = 0
        self._failure: tuple[Phase, str] | None = None

    @property
    def samples(self) -> tuple[tuple[float, ...], ...]:
        return self._samples

    def begin(self) -> EnrollmentStatus:
        return EnrollmentStatus(Phase.LOOK, SAY_LOOK, 0.0, speak=SAY_LOOK)

    def update(self, frame: np.ndarray, faces: np.ndarray) -> EnrollmentStatus:
        now = self._clock()
        if self._phase is Phase.DONE:
            return EnrollmentStatus(Phase.DONE, TEXT_DONE, 1.0)
        if self._phase is Phase.FAILED and self._failure is not None:
            phase, message = self._failure
            return EnrollmentStatus(Phase.FAILED, message, 0.0, failed_phase=phase)
        if self._phase is Phase.LOOK:
            return self._update_look(frame, faces, now)
        return self._update_close(frame, faces, now)

    def _fail(self, phase: Phase, message: str) -> EnrollmentStatus:
        self._phase = Phase.FAILED
        self._failure = (phase, message)
        return EnrollmentStatus(
            Phase.FAILED, message, 0.0, speak=SAY_FAIL, failed_phase=phase
        )

    def _reset_look(self) -> None:
        self._look_started = None
        self._samples = ()
        self._look_contrasts = []

    def _update_look(self, frame: np.ndarray, faces: np.ndarray, now: float) -> EnrollmentStatus:
        if len(faces) != 1 or float(faces[0][14]) < MIN_FACE_SCORE:
            self._reset_look()
            return EnrollmentStatus(Phase.LOOK, TEXT_FIND_FACE, 0.0)
        face = faces[0]
        if self._look_started is None:
            self._look_started = now
            self._last_sample = now - SAMPLE_INTERVAL
        elapsed = now - self._look_started
        self._look_contrasts.append(self._eyes.openness(frame, face))
        if now - self._last_sample >= SAMPLE_INTERVAL and len(self._samples) < MAX_SAMPLES:
            feature = self._engine.embed(frame, face)
            vector = tuple(float(value) for value in feature.flatten())
            self._samples = (*self._samples, vector)
            self._last_sample = now
        if elapsed < LOOK_SECONDS:
            return EnrollmentStatus(Phase.LOOK, SAY_LOOK, min(1.0, elapsed / LOOK_SECONDS))
        self._baseline = statistics.median(self._look_contrasts)
        if len(self._samples) < MIN_SAMPLES or self._baseline < MIN_EYE_CONTRAST:
            return self._fail(Phase.LOOK, FAIL_OPEN)
        self._phase = Phase.CLOSE
        self._close_entered = now
        return EnrollmentStatus(Phase.CLOSE, SAY_CLOSE, 0.0, speak=SAY_CLOSE)

    def _update_close(self, frame: np.ndarray, faces: np.ndarray, now: float) -> EnrollmentStatus:
        if self._close_started is None:
            if now - self._close_entered < CLOSE_GRACE_SECONDS:
                return EnrollmentStatus(Phase.CLOSE, SAY_CLOSE, 0.0)
            self._close_started = now
        elapsed = now - self._close_started
        if len(faces) == 1:
            if self._eyes.openness(frame, faces[0]) < self._baseline * EYE_CLOSED_FACTOR:
                self._closed_frames += 1
            else:
                self._open_frames += 1
        if elapsed < CLOSE_SECONDS:
            return EnrollmentStatus(Phase.CLOSE, TEXT_KEEP_CLOSED, min(1.0, elapsed / CLOSE_SECONDS))
        seen = self._closed_frames + self._open_frames
        closed_ratio = self._closed_frames / seen if seen else 0.0
        if self._closed_frames < MIN_CLOSED_FRAMES or closed_ratio < CLOSED_RATIO_MIN:
            return self._fail(Phase.CLOSE, FAIL_CLOSE)
        self._phase = Phase.DONE
        return EnrollmentStatus(Phase.DONE, TEXT_DONE, 1.0, speak=SAY_DONE)


def seconds_left(duration: float, progress: float) -> int:
    return max(0, math.ceil(duration * (1.0 - progress)))
