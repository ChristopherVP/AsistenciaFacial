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

INTEGRATED_HINTS = (
    "integrated",
    "internal",
    "built-in",
    "builtin",
    "laptop",
    "hp wide vision",
    "hp truevision",
    "hp true vision",
    "hp webcam",
    "hp hd camera",
    "facetime",
    "front camera",
    "surface camera",
    "integrada",
    "frontal",
)
EXTERNAL_HINTS = ("usb", "webcam", "web cam", "external", "logitech", "pc camera", "hd full")

Banner = tuple[str, tuple[int, int, int]]


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


def resolve_camera_index(name: str, fallback: int) -> int:
    if not name:
        return fallback
    names = device_names()
    if not names:
        return fallback
    if name not in names:
        raise CameraError(
            f"No se encuentra la cámara «{name}». Conéctala y pulsa Buscar cámaras en Ajustes."
        )
    return names.index(name)


def classify_camera(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in INTEGRATED_HINTS):
        return "integrated"
    if any(hint in lowered for hint in EXTERNAL_HINTS):
        return "external"
    return "unknown"


def assign_kinds(entries: Sequence[tuple[int, str]]) -> tuple[CameraInfo, ...]:
    kinds = [classify_camera(name) for _, name in entries]
    if len(entries) >= 2:
        if "integrated" in kinds:
            kinds = ["external" if kind == "unknown" else kind for kind in kinds]
        elif "external" in kinds:
            kinds = ["integrated" if kind == "unknown" else kind for kind in kinds]
        else:
            kinds = ["integrated", *["external"] * (len(kinds) - 1)]
    return tuple(
        CameraInfo(index, name, kind) for (index, name), kind in zip(entries, kinds)
    )


def detect_cameras() -> tuple[CameraInfo, ...]:
    names = device_names()
    candidates = len(names) if names else MAX_CAMERA_INDEX
    found: list[tuple[int, str]] = []
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
            found.append((index, names[index] if index < len(names) else f"Cámara {index}"))
    return assign_kinds(found)


@lru_cache(maxsize=4)
def label_font(size: int = 18) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_frame(
    frame: np.ndarray,
    results: Sequence[FaceResult],
    banner: Banner | None = None,
) -> Image.Image:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = label_font(18)
    for result in results:
        x, y, w, h = result.box
        color = (46, 139, 87) if result.recognized else (176, 58, 46)
        draw.rectangle((x, y, x + w, y + h), outline=color, width=3)
        if not result.label:
            continue
        text_y = max(0, y - 26)
        left, top, right, bottom = draw.textbbox((x, text_y), result.label, font=font)
        draw.rectangle((left - 4, top - 2, right + 4, bottom + 2), fill=color)
        draw.text((x, text_y), result.label, fill="white", font=font)
    if banner is not None:
        text, color = banner
        draw.rectangle((0, 0, image.width, 46), fill=color)
        draw.text((14, 9), text, fill="white", font=label_font(24))
    return image
