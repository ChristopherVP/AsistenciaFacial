from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np

from .config import (
    DETECTOR_FILE,
    MIN_MODEL_BYTES,
    MODEL_URLS,
    MODELS_DIR,
    RECOGNIZER_FILE,
)
from .errors import ModelError
from .models import Student

ProgressCallback = Callable[[str, float], None]


def ensure_model(
    file_name: str,
    models_dir: Path = MODELS_DIR,
    report: Callable[[float], None] | None = None,
) -> Path:
    target = models_dir / file_name
    if target.exists() and target.stat().st_size > MIN_MODEL_BYTES:
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".descarga")

    def hook(blocks: int, block_size: int, total: int) -> None:
        if report is not None and total > 0:
            report(min(1.0, blocks * block_size / total))

    try:
        urllib.request.urlretrieve(MODEL_URLS[file_name], temporary, hook)
        if temporary.stat().st_size <= MIN_MODEL_BYTES:
            raise ModelError(f"La descarga de {file_name} quedó incompleta.")
        os.replace(temporary, target)
    except (urllib.error.URLError, OSError) as error:
        raise ModelError(
            f"No se pudo descargar el modelo {file_name}: {error}\n\n"
            f"Descárgalo manualmente desde:\n{MODEL_URLS[file_name]}\n"
            f"y guárdalo en:\n{models_dir}"
        ) from error
    return target


class FaceEngine:
    def __init__(
        self,
        models_dir: Path = MODELS_DIR,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        progress = on_progress or (lambda message, fraction: None)
        progress("Preparando detector de rostros…", 0.05)
        detector_path = ensure_model(DETECTOR_FILE, models_dir)
        download_message = "Descargando modelo de reconocimiento (solo la primera vez)…"
        progress(download_message, 0.10)
        recognizer_path = ensure_model(
            RECOGNIZER_FILE,
            models_dir,
            lambda fraction: progress(download_message, 0.10 + 0.80 * fraction),
        )
        progress("Cargando modelos…", 0.95)
        self._detector = cv2.FaceDetectorYN.create(
            str(detector_path), "", (320, 320), 0.85, 0.3, 5000
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")

    def detect(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(frame)
        return faces if faces is not None else np.empty((0, 15), np.float32)

    def embed(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray:
        aligned = self._recognizer.alignCrop(frame, face)
        return self._recognizer.feature(aligned)


class Gallery:
    def __init__(self, students: Sequence[Student]) -> None:
        self._students = tuple(students)
        rows: list[np.ndarray] = []
        owners: list[int] = []
        for index, student in enumerate(self._students):
            for embedding in student.embeddings:
                vector = np.asarray(embedding, dtype=np.float32)
                rows.append(vector / np.linalg.norm(vector))
                owners.append(index)
        self._matrix = np.vstack(rows) if rows else np.empty((0, 128), np.float32)
        self._owners = np.asarray(owners, dtype=int)

    def identify(self, feature: np.ndarray, threshold: float) -> Student | None:
        if self._matrix.shape[0] == 0:
            return None
        vector = feature.flatten().astype(np.float32)
        vector = vector / np.linalg.norm(vector)
        similarities = self._matrix @ vector
        best = int(np.argmax(similarities))
        if similarities[best] < threshold:
            return None
        return self._students[int(self._owners[best])]
