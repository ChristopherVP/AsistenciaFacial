from __future__ import annotations

import sys
from dataclasses import dataclass
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
    "facetime",
    "front camera",
    "surface camera",
    "integrada",
)
CYAN = (0, 220, 255)

Banner = tuple[str, tuple[int, int, int]]


@dataclass(frozen=True)
class ScanOverlay:
    box: tuple[int, int, int, int] | None
    progress: float
    tick: float


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


def names_available() -> bool:
    return bool(device_names())


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
    return "integrated" if any(hint in lowered for hint in INTEGRATED_HINTS) else "unknown"


def _delivers_frames(index: int) -> bool:
    try:
        camera = Camera(index)
    except CameraError:
        return False
    try:
        return any(camera.read() is not None for _ in range(8))
    finally:
        camera.release()


def detect_cameras() -> tuple[CameraInfo, ...]:
    """Lista las cámaras por nombre. Con nombres reales (pygrabber) también
    muestra las que no se pudieron abrir, marcadas como no disponibles."""
    names = device_names()
    candidates = len(names) if names else MAX_CAMERA_INDEX
    found: list[CameraInfo] = []
    for index in range(candidates):
        name = names[index] if index < len(names) else f"Cámara {index}"
        available = _delivers_frames(index)
        if not available and not names:
            continue
        found.append(CameraInfo(index, name, classify_camera(name), available))
    return tuple(found)


@lru_cache(maxsize=6)
def label_font(size: int = 18) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default(size)


def _draw_scan(image: Image.Image, scan: ScanOverlay) -> Image.Image:
    if scan.box is None:
        return image
    x, y, w, h = scan.box
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    length = max(18, int(min(w, h) * 0.22))
    for corner_x, corner_y, step_x, step_y in (
        (x, y, 1, 1),
        (x + w, y, -1, 1),
        (x, y + h, 1, -1),
        (x + w, y + h, -1, -1),
    ):
        draw.line(
            [(corner_x, corner_y + step_y * length), (corner_x, corner_y), (corner_x + step_x * length, corner_y)],
            fill=(*CYAN, 255),
            width=4,
        )
    phase = (scan.tick * 0.9) % 2.0
    fraction = phase if phase <= 1.0 else 2.0 - phase
    line_y = y + int(fraction * h)
    for offset, alpha in ((0, 235), (-3, 150), (-6, 95), (-9, 55), (-12, 25)):
        draw.line([(x, line_y + offset), (x + w, line_y + offset)], fill=(*CYAN, alpha), width=3)
    caption = f"ESCANEANDO  {int(scan.progress * 100)} %"
    draw.text((x, min(image.height - 28, y + h + 6)), caption, fill=(*CYAN, 255), font=label_font(17))
    base = image.convert("RGBA")
    base.alpha_composite(layer)
    return base.convert("RGB")


def render_frame(
    frame: np.ndarray,
    results: Sequence[FaceResult],
    banner: Banner | None = None,
    scan: ScanOverlay | None = None,
) -> Image.Image:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = label_font(17)
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
    if scan is not None:
        image = _draw_scan(image, scan)
    if banner is not None:
        draw = ImageDraw.Draw(image)
        text, color = banner
        draw.rectangle((0, 0, image.width, 46), fill=color)
        draw.text((14, 8), text, fill="white", font=label_font(23))
    return image
