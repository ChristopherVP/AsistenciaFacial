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
ICON_FILE = DATA_DIR / "icono.ico"

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

CONFIRM_FRAMES = 3
PROCESS_EVERY_N_FRAMES = 2
FRAME_DELAY_MS = 33
MAX_READ_FAILURES = 90
MAX_CAMERA_INDEX = 4
VIEW_WIDTH = 640
VIEW_HEIGHT = 480
MIN_THRESHOLD = 0.30
MAX_THRESHOLD = 0.80
NOTICE_MS = 4000

MAX_PROVINCE_CODE = 24
NAME_MAX_LENGTH = 60

LOOK_SECONDS = 3.0
CLOSE_SECONDS = 3.0
CLOSE_GRACE_SECONDS = 1.2
MIN_SAMPLES = 3
MAX_SAMPLES = 5
SAMPLE_INTERVAL = 0.5
MIN_FACE_SCORE = 0.9
MIN_EYE_CONTRAST = 0.08
EYE_CLOSED_FACTOR = 0.75
CLOSED_RATIO_MIN = 0.6
MIN_CLOSED_FRAMES = 4

DAY_LABELS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

COLOR_PRIMARY = "#1F4E79"
COLOR_PRIMARY_DARK = "#163A5A"
COLOR_SUCCESS = "#2E8B57"
COLOR_DANGER = "#B03A2E"
COLOR_WARNING = "#B9770E"
COLOR_BG = "#F4F6F8"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1B2631"
COLOR_MUTED = "#5D6D7E"
FONT_FAMILY = "Segoe UI"
