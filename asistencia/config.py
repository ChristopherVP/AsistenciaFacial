from __future__ import annotations

import re
from pathlib import Path

APP_TITLE = "Asistencia Facial"
APP_ID = "AsistenciaFacial.App"

DATA_DIR = Path.home() / "AsistenciaFacial"
MODELS_DIR = DATA_DIR / "modelos"
COURSES_DIR = DATA_DIR / "cursos"
BACKUP_DIR = DATA_DIR / "respaldos"
SETTINGS_FILE = DATA_DIR / "ajustes.json"

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
MODEL_URLS = {
    DETECTOR_FILE: (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx"
    ),
    RECOGNIZER_FILE: (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx"
    ),
}
MIN_MODEL_BYTES = 100_000

REQUIRED_SAMPLES = 3
CONFIRM_FRAMES = 3
PROCESS_EVERY_N_FRAMES = 2
FRAME_DELAY_MS = 33
MAX_READ_FAILURES = 90
MAX_CAMERA_INDEX = 4
VIEW_WIDTH = 640
VIEW_HEIGHT = 480
MIN_THRESHOLD = 0.30
MAX_THRESHOLD = 0.80

DAY_LABELS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{3,20}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

COLOR_PRIMARY = "#1F4E79"
COLOR_PRIMARY_DARK = "#163A5A"
COLOR_SUCCESS = "#2E8B57"
COLOR_DANGER = "#B03A2E"
COLOR_BG = "#F4F6F8"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1B2631"
COLOR_MUTED = "#5D6D7E"
FONT_FAMILY = "Segoe UI"
