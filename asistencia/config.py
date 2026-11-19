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
USERS_FILE = DATA_DIR / "usuarios.json"
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

SAMPLE_INTERVAL = 0.6
MAX_SAMPLES = 5
MIN_FACE_SCORE = 0.9
SCAN_TIMEOUT_SECONDS = 60.0
REMIND_SECONDS = 8.0
MAX_YAW_RATIO = 0.25
MAX_ROLL_RATIO = 0.30
MANUAL_SESSION_MINUTES = 20

PRECISION_LEVELS = (
    ("Flexible", 0.33, "Reconoce con más facilidad. Úselo si el sistema no reconoce a los estudiantes."),
    ("Equilibrado", 0.40, "Recomendado para la mayoría de los casos."),
    ("Estricto", 0.50, "Evita confundir a una persona con otra. Úselo si hay falsos registros."),
)

MIN_USERNAME_LENGTH = 4
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 64
MIN_ANSWER_LENGTH = 3
PBKDF2_ITERATIONS = 200_000
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 30.0
SECURITY_QUESTIONS = (
    "¿Cómo se llamaba su primera mascota?",
    "¿En qué ciudad nació su madre?",
    "¿Cuál es el nombre de su mejor amigo de la infancia?",
    "¿Cómo se llamaba su escuela primaria?",
    "¿Cuál es su comida favorita?",
)

DAY_LABELS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

COLOR_PRIMARY = "#1F4E79"
COLOR_PRIMARY_DARK = "#163A5A"
COLOR_SUCCESS = "#2E8B57"
COLOR_DANGER = "#B03A2E"
COLOR_WARNING = "#B9770E"
COLOR_BG = "#EEF2F6"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1B2631"
COLOR_MUTED = "#5D6D7E"
COLOR_BORDER = "#D5DCE4"
COLOR_ZEBRA = "#F5F8FB"
COLOR_SELECT = "#D6E9F8"
COLOR_ACCENT = "#2E86C1"
COLOR_INFO_BG = "#EAF2FB"
FONT_FAMILY = "Segoe UI"
