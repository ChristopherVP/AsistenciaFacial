from __future__ import annotations

import sys
from functools import lru_cache
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import MAX_CAMERA_INDEX, VIEW_HEIGHT, VIEW_WIDTH
from .errors import CameraError
from .models import CameraInfo, FaceResult


class Camera:
    def __init__(self, index: int) -> None:
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        self._capture = cv2.VideoCapture(index, backend)
        if not self._capture.isOpened():
            self._capture.release()
            raise CameraError(
                f"No se pudo abrir la cámara {index}. Verifica que esté conectada, "
                "que ninguna otra aplicación la esté usando y que Windows permita el "
                "acceso a la cámara (Configuración → Privacidad y seguridad → Cámara)."
            )
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, VIEW_WIDTH)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, VIEW_HEIGHT)

    def read(self) -> np.ndarray | None:
        success, frame = self._capture.read()
        return frame if success else None

    def release(self) -> None:
        self._capture.release()


def device_names() -> list[str]:
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return []
    try:
        return [str(name) for name in FilterGraph().get_input_devices()]
    except Exception:
        return []


def detect_cameras() -> tuple[CameraInfo, ...]:
    names = device_names()
    candidates = len(names) if names else MAX_CAMERA_INDEX
    found: list[CameraInfo] = []
    for index in range(candidates):
        try:
            camera = Camera(index)
        except CameraError:
            continue
        frame = None
        for _ in range(5):
            frame = camera.read()
            if frame is not None:
                break
        camera.release()
        if frame is not None:
            name = names[index] if index < len(names) else f"Cámara {index}"
            found.append(CameraInfo(index, name))
    return tuple(found)


@lru_cache(maxsize=1)
def label_font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 18)
    except OSError:
        return ImageFont.load_default()


def render_frame(frame: np.ndarray, results: Sequence[FaceResult]) -> Image.Image:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = label_font()
    for result in results:
        x, y, w, h = result.box
        color = (46, 139, 87) if result.recognized else (176, 58, 46)
        draw.rectangle((x, y, x + w, y + h), outline=color, width=3)
        text_y = max(0, y - 26)
        left, top, right, bottom = draw.textbbox((x, text_y), result.label, font=font)
        draw.rectangle((left - 4, top - 2, right + 4, bottom + 2), fill=color)
        draw.text((x, text_y), result.label, fill="white", font=font)
    return image
