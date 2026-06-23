"""Application-wide constants and MediaPipe landmark definitions."""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_NAME: Final[str] = "AirCanvas Calculator"
APP_VERSION: Final[str] = "1.0.0"
APP_ORGANIZATION: Final[str] = "AirCanvas"

# ---------------------------------------------------------------------------
# MediaPipe hand landmark indices (21-point model)
# ---------------------------------------------------------------------------

WRIST: Final[int] = 0
THUMB_CMC: Final[int] = 1
THUMB_MCP: Final[int] = 2
THUMB_IP: Final[int] = 3
THUMB_TIP: Final[int] = 4
INDEX_FINGER_MCP: Final[int] = 5
INDEX_FINGER_PIP: Final[int] = 6
INDEX_FINGER_DIP: Final[int] = 7
INDEX_FINGER_TIP: Final[int] = 8
MIDDLE_FINGER_MCP: Final[int] = 9
MIDDLE_FINGER_PIP: Final[int] = 10
MIDDLE_FINGER_DIP: Final[int] = 11
MIDDLE_FINGER_TIP: Final[int] = 12
RING_FINGER_MCP: Final[int] = 13
RING_FINGER_PIP: Final[int] = 14
RING_FINGER_DIP: Final[int] = 15
RING_FINGER_TIP: Final[int] = 16
PINKY_MCP: Final[int] = 17
PINKY_PIP: Final[int] = 18
PINKY_DIP: Final[int] = 19
PINKY_TIP: Final[int] = 20

# Landmarks used by the drawing pipeline
DRAW_CURSOR_LANDMARK: Final[int] = INDEX_FINGER_TIP
PINCH_LANDMARK_A: Final[int] = THUMB_TIP
PINCH_LANDMARK_B: Final[int] = INDEX_FINGER_TIP

# ---------------------------------------------------------------------------
# Gesture detection
# ---------------------------------------------------------------------------

PINCH_THRESHOLD: Final[float] = 0.05
PINCH_RELEASE_THRESHOLD: Final[float] = 0.07
GESTURE_DEBOUNCE_FRAMES: Final[int] = 3
HAND_LOST_TIMEOUT_MS: Final[int] = 500
PALM_CLEAR_HOLD_MS: Final[int] = 1500
DRAW_DEAD_ZONE_PX: Final[int] = 3
STROKE_GAP_INTERPOLATION_PX: Final[int] = 25
OUTLIER_JUMP_THRESHOLD_PX: Final[int] = 50

# ---------------------------------------------------------------------------
# Vision pipeline
# ---------------------------------------------------------------------------

DEFAULT_CAMERA_WIDTH: Final[int] = 640
DEFAULT_CAMERA_HEIGHT: Final[int] = 480
DEFAULT_CAMERA_FPS: Final[int] = 30
DEFAULT_CAMERA_BUFFER_SIZE: Final[int] = 1
DEFAULT_NUM_HANDS: Final[int] = 1
MIN_HAND_DETECTION_CONFIDENCE: Final[float] = 0.7
MIN_HAND_PRESENCE_CONFIDENCE: Final[float] = 0.7
MIN_TRACKING_CONFIDENCE: Final[float] = 0.7
MIRROR_CAMERA: Final[bool] = True

# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

DEFAULT_SMOOTHER_ALPHA: Final[float] = 0.4
ONE_EURO_MIN_CUTOFF: Final[float] = 1.0
ONE_EURO_BETA: Final[float] = 0.007
ONE_EURO_D_CUTOFF: Final[float] = 1.0

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

TESSERACT_CONFIDENCE_THRESHOLD: Final[float] = 0.65
EASYOCR_MIN_CONFIDENCE: Final[float] = 0.50
OCR_TIMEOUT_SECONDS: Final[float] = 5.0
OCR_EVALUATE_WHITELIST: Final[str] = r"0123456789+-*/().=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
TESSERACT_PSM: Final[int] = 7
TESSERACT_OEM: Final[int] = 3
OCR_PREPROCESS_SCALE: Final[float] = 3.0
OCR_PREPROCESS_PADDING_PX: Final[int] = 20
FALLBACK_ENABLED: Final[bool] = True
WARN_ON_UNAVAILABLE_FALLBACK: Final[bool] = True

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

MAX_HISTORY_ENTRIES: Final[int] = 500
HISTORY_SAVE_DEBOUNCE_MS: Final[int] = 500
HISTORY_NEWEST_FIRST: Final[bool] = True

# ---------------------------------------------------------------------------
# UI / theme tokens
# ---------------------------------------------------------------------------

DEFAULT_WINDOW_WIDTH: Final[int] = 1280
DEFAULT_WINDOW_HEIGHT: Final[int] = 800
SIDEBAR_WIDTH_PX: Final[int] = 260
SIDEBAR_COLLAPSED_WIDTH_PX: Final[int] = 64
CANVAS_DEFAULT_WIDTH: Final[int] = 960
CANVAS_DEFAULT_HEIGHT: Final[int] = 480
TARGET_UI_FPS: Final[int] = 60

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

ENABLE_GESTURE_EVALUATE: Final[bool] = False

# ---------------------------------------------------------------------------
# Environment variable names
# ---------------------------------------------------------------------------

ENV_LOG_LEVEL: Final[str] = "AIRCANVAS_LOG_LEVEL"
ENV_CONFIG_FILE: Final[str] = "AIRCANVAS_CONFIG_FILE"
ENV_CAMERA_INDEX: Final[str] = "AIRCANVAS_CAMERA_INDEX"
ENV_TESSERACT_CMD: Final[str] = "AIRCANVAS_TESSERACT_CMD"
ENV_FALLBACK_ENABLED: Final[str] = "AIRCANVAS_FALLBACK_ENABLED"

# ---------------------------------------------------------------------------
# Asset filenames
# ---------------------------------------------------------------------------

HAND_MODEL_FILENAME: Final[str] = "hand_landmarker.task"
HISTORY_FILENAME: Final[str] = "history.json"
HISTORY_TEMP_FILENAME: Final[str] = "history.json.tmp"

# ---------------------------------------------------------------------------
# Windows Tesseract install candidates
# ---------------------------------------------------------------------------

WINDOWS_TESSERACT_CANDIDATES: Final[tuple[str, ...]] = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
