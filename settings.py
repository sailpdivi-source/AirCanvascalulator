"""Centralized configuration loading, validation, and logging setup."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field, fields
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal, TextIO

from config import constants as C

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
SmootherType = Literal["ema", "one_euro"]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class LogSettings:
    level: LogLevel = "INFO"
    log_to_file: bool = True
    log_dir: Path = field(default_factory=lambda: _project_root() / "logs")
    log_filename: str = "aircanvas.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class CameraSettings:
    index: int = 0
    width: int = C.DEFAULT_CAMERA_WIDTH
    height: int = C.DEFAULT_CAMERA_HEIGHT
    fps: int = C.DEFAULT_CAMERA_FPS
    buffer_size: int = C.DEFAULT_CAMERA_BUFFER_SIZE
    mirror: bool = C.MIRROR_CAMERA


@dataclass(frozen=True)
class VisionSettings:
    num_hands: int = C.DEFAULT_NUM_HANDS
    min_hand_detection_confidence: float = C.MIN_HAND_DETECTION_CONFIDENCE
    min_hand_presence_confidence: float = C.MIN_HAND_PRESENCE_CONFIDENCE
    min_tracking_confidence: float = C.MIN_TRACKING_CONFIDENCE
    hand_model_path: Path = field(
        default_factory=lambda: _project_root() / "assets" / C.HAND_MODEL_FILENAME
    )
    pinch_threshold: float = C.PINCH_THRESHOLD
    pinch_release_threshold: float = C.PINCH_RELEASE_THRESHOLD
    gesture_debounce_frames: int = C.GESTURE_DEBOUNCE_FRAMES
    hand_lost_timeout_ms: int = C.HAND_LOST_TIMEOUT_MS
    draw_dead_zone_px: int = C.DRAW_DEAD_ZONE_PX


@dataclass(frozen=True)
class SmoothingSettings:
    smoother_type: SmootherType = "ema"
    ema_alpha: float = C.DEFAULT_SMOOTHER_ALPHA
    one_euro_min_cutoff: float = C.ONE_EURO_MIN_CUTOFF
    one_euro_beta: float = C.ONE_EURO_BETA
    one_euro_d_cutoff: float = C.ONE_EURO_D_CUTOFF
    outlier_jump_threshold_px: int = C.OUTLIER_JUMP_THRESHOLD_PX
    stroke_gap_interpolation_px: int = C.STROKE_GAP_INTERPOLATION_PX


@dataclass(frozen=True)
class OCRSettings:
    tesseract_cmd: Path | None = None
    confidence_threshold: float = C.TESSERACT_CONFIDENCE_THRESHOLD
    easyocr_min_confidence: float = C.EASYOCR_MIN_CONFIDENCE
    timeout_seconds: float = C.OCR_TIMEOUT_SECONDS
    whitelist: str = C.OCR_EVALUATE_WHITELIST
    psm: int = C.TESSERACT_PSM
    oem: int = C.TESSERACT_OEM
    preprocess_scale: float = C.OCR_PREPROCESS_SCALE
    preprocess_padding_px: int = C.OCR_PREPROCESS_PADDING_PX
    fallback_enabled: bool = C.FALLBACK_ENABLED
    warn_on_unavailable_fallback: bool = C.WARN_ON_UNAVAILABLE_FALLBACK
    easyocr_gpu: bool = False


@dataclass(frozen=True)
class DrawingSettings:
    canvas_width: int = C.CANVAS_DEFAULT_WIDTH
    canvas_height: int = C.CANVAS_DEFAULT_HEIGHT
    stroke_color: tuple[int, int, int] = (0, 0, 0)
    stroke_width: int = 4
    background_color: tuple[int, int, int] = (255, 255, 255)


@dataclass(frozen=True)
class HistorySettings:
    history_path: Path = field(
        default_factory=lambda: _project_root() / "history" / C.HISTORY_FILENAME
    )
    max_entries: int = C.MAX_HISTORY_ENTRIES
    save_debounce_ms: int = C.HISTORY_SAVE_DEBOUNCE_MS
    newest_first: bool = C.HISTORY_NEWEST_FIRST


@dataclass(frozen=True)
class UISettings:
    window_width: int = C.DEFAULT_WINDOW_WIDTH
    window_height: int = C.DEFAULT_WINDOW_HEIGHT
    sidebar_width: int = C.SIDEBAR_WIDTH_PX
    sidebar_collapsed_width: int = C.SIDEBAR_COLLAPSED_WIDTH_PX
    target_fps: int = C.TARGET_UI_FPS
    styles_dir: Path = field(default_factory=lambda: _project_root() / "ui" / "styles")
    enable_gesture_evaluate: bool = C.ENABLE_GESTURE_EVALUATE


@dataclass(frozen=True)
class Settings:
    """Root configuration object consumed by all application modules."""

    project_root: Path = field(default_factory=_project_root)
    app_name: str = C.APP_NAME
    app_version: str = C.APP_VERSION
    logging: LogSettings = field(default_factory=LogSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    smoothing: SmoothingSettings = field(default_factory=SmoothingSettings)
    ocr: OCRSettings = field(default_factory=OCRSettings)
    drawing: DrawingSettings = field(default_factory=DrawingSettings)
    history: HistorySettings = field(default_factory=HistorySettings)
    ui: UISettings = field(default_factory=UISettings)


class ConfigurationError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""


def _coerce_path(value: Any) -> Path:
    return Path(str(value)).expanduser()


def _coerce_log_level(value: str) -> LogLevel:
    normalized = value.strip().upper()
    allowed: tuple[LogLevel, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if normalized not in allowed:
        raise ConfigurationError(
            f"Invalid log level '{value}'. Expected one of: {', '.join(allowed)}"
        )
    return normalized  # type: ignore[return-value]


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean value '{value}'")


def _apply_mapping(target: Any, updates: dict[str, Any]) -> Any:
    """Return a new dataclass instance with field-level overrides."""
    cls = type(target)
    current = asdict(target)
    for key, value in updates.items():
        if key not in current:
            raise ConfigurationError(f"Unknown configuration key '{key}' for {cls.__name__}")
        current[key] = value
    return cls(**current)


def _path_field_names(cls: type[Any]) -> set[str]:
    return {
        field_def.name
        for field_def in fields(cls)
        if field_def.type in {Path, "Path", Path | None, "Path | None"}
        or "Path" in str(field_def.type)
    }


def _normalize_section(cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for name in _path_field_names(cls):
        if name in normalized and normalized[name] is not None:
            normalized[name] = _coerce_path(normalized[name])
    return normalized


def _load_json_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in configuration file '{path}': {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"Unable to read configuration file '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration file '{path}' must contain a JSON object")
    return data


def _apply_env_overrides(settings: Settings) -> Settings:
    logging_settings = settings.logging
    camera_settings = settings.camera
    ocr_settings = settings.ocr

    if C.ENV_LOG_LEVEL in os.environ:
        logging_settings = _apply_mapping(
            logging_settings,
            {"level": _coerce_log_level(os.environ[C.ENV_LOG_LEVEL])},
        )

    if C.ENV_CAMERA_INDEX in os.environ:
        try:
            camera_index = int(os.environ[C.ENV_CAMERA_INDEX])
        except ValueError as exc:
            raise ConfigurationError(
                f"{C.ENV_CAMERA_INDEX} must be an integer"
            ) from exc
        camera_settings = _apply_mapping(camera_settings, {"index": camera_index})

    if C.ENV_TESSERACT_CMD in os.environ:
        ocr_settings = _apply_mapping(
            ocr_settings,
            {"tesseract_cmd": _coerce_path(os.environ[C.ENV_TESSERACT_CMD])},
        )

    if C.ENV_FALLBACK_ENABLED in os.environ:
        ocr_settings = _apply_mapping(
            ocr_settings,
            {"fallback_enabled": _parse_bool(os.environ[C.ENV_FALLBACK_ENABLED])},
        )

    return Settings(
        project_root=settings.project_root,
        app_name=settings.app_name,
        app_version=settings.app_version,
        logging=logging_settings,
        camera=camera_settings,
        vision=settings.vision,
        smoothing=settings.smoothing,
        ocr=ocr_settings,
        drawing=settings.drawing,
        history=settings.history,
        ui=settings.ui,
    )


def _build_settings_from_mapping(data: dict[str, Any]) -> Settings:
    base = Settings()
    section_map: dict[str, Any] = {
        "logging": LogSettings,
        "camera": CameraSettings,
        "vision": VisionSettings,
        "smoothing": SmoothingSettings,
        "ocr": OCRSettings,
        "drawing": DrawingSettings,
        "history": HistorySettings,
        "ui": UISettings,
    }

    kwargs: dict[str, Any] = {
        "project_root": base.project_root,
        "app_name": base.app_name,
        "app_version": base.app_version,
    }

    for section_name, section_cls in section_map.items():
        section_payload = data.get(section_name, {})
        if section_payload is None:
            section_payload = {}
        if not isinstance(section_payload, dict):
            raise ConfigurationError(f"Section '{section_name}' must be a JSON object")
        merged = asdict(getattr(base, section_name))
        merged.update(_normalize_section(section_cls, section_payload))
        kwargs[section_name] = section_cls(**merged)

    top_level_keys = {"project_root", "app_name", "app_version"}
    for key in top_level_keys:
        if key in data:
            value = data[key]
            if key == "project_root":
                kwargs[key] = _coerce_path(value)
            else:
                kwargs[key] = value

    return Settings(**kwargs)


def load_settings(config_path: Path | None = None) -> Settings:
    """
    Load application settings from defaults, optional JSON file, and environment.

    Precedence (lowest to highest): defaults < JSON file < environment variables.
  """
    resolved_path = config_path
    if resolved_path is None and C.ENV_CONFIG_FILE in os.environ:
        resolved_path = _coerce_path(os.environ[C.ENV_CONFIG_FILE])

    settings = Settings()
    if resolved_path is not None:
        settings = _build_settings_from_mapping(_load_json_config(resolved_path))

    settings = _apply_env_overrides(settings)
    return settings


def resolve_tesseract_command(settings: Settings) -> Path | None:
    """Resolve the Tesseract executable path from settings and known locations."""
    if settings.ocr.tesseract_cmd is not None:
        candidate = settings.ocr.tesseract_cmd.expanduser()
        if candidate.is_file():
            return candidate

    discovered = shutil.which("tesseract")
    if discovered is not None:
        return Path(discovered)

    if sys.platform.startswith("win"):
        for candidate_str in C.WINDOWS_TESSERACT_CANDIDATES:
            candidate = Path(candidate_str)
            if candidate.is_file():
                return candidate

    return None


def configure_logging(settings: Settings) -> None:
    """Configure root logging for console and optional rotating file output."""
    log_settings = settings.logging
    level = getattr(logging, log_settings.level)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    formatter = logging.Formatter(log_settings.log_format, datefmt=log_settings.date_format)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if not log_settings.log_to_file:
        return

    try:
        log_settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_settings.log_dir / log_settings.log_filename
        file_handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=log_settings.max_bytes,
            backupCount=log_settings.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        root_logger.error("Failed to initialize file logging: %s", exc)


def _verify_tesseract(tesseract_cmd: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(tesseract_cmd), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Tesseract verification failed: {exc}"

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown error"
        return f"Tesseract returned exit code {completed.returncode}: {stderr}"

    return None


def _ensure_directory(path: Path, purpose: str) -> str | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Cannot create {purpose} directory '{path}': {exc}"
    return None


def _ensure_writable_file(path: Path, purpose: str) -> str | None:
    directory = path.parent
    dir_error = _ensure_directory(directory, purpose)
    if dir_error is not None:
        return dir_error

    if path.exists() and not os.access(path, os.W_OK):
        return f"{purpose} file is not writable: {path}"

    if not path.exists():
        try:
            path.touch()
        except OSError as exc:
            return f"Cannot create {purpose} file '{path}': {exc}"
    return None


def validate_environment(settings: Settings) -> list[str]:
    """
    Validate external dependencies and writable paths required at startup.

    Returns a list of human-readable error messages. An empty list means success.
    """
    errors: list[str] = []

    hand_model = settings.vision.hand_model_path
    if not hand_model.is_file():
        errors.append(
            "MediaPipe hand model not found at "
            f"'{hand_model}'. Download hand_landmarker.task into assets/."
        )

    tesseract_cmd = resolve_tesseract_command(settings)
    if tesseract_cmd is None:
        errors.append(
            "Tesseract OCR executable not found. Install Tesseract and/or set "
            f"{C.ENV_TESSERACT_CMD} to the full path of tesseract.exe."
        )
    else:
        tesseract_error = _verify_tesseract(tesseract_cmd)
        if tesseract_error is not None:
            errors.append(tesseract_error)

    log_dir_error = _ensure_directory(settings.logging.log_dir, "log")
    if log_dir_error is not None:
        errors.append(log_dir_error)

    history_error = _ensure_writable_file(settings.history.history_path, "history")
    if history_error is not None:
        errors.append(history_error)

    styles_dir = settings.ui.styles_dir
    if not styles_dir.is_dir():
        logging.getLogger(__name__).warning(
            "UI styles directory not found at '%s'. The UI may use built-in defaults.",
            styles_dir,
        )

    return errors


def apply_tesseract_to_pytesseract(settings: Settings) -> Path | None:
    """Configure pytesseract with the resolved Tesseract executable path."""
    tesseract_cmd = resolve_tesseract_command(settings)
    if tesseract_cmd is None:
        return None

    try:
        import pytesseract
    except ImportError as exc:
        raise ConfigurationError("pytesseract is not installed") from exc

    pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
    return tesseract_cmd


def dump_settings(settings: Settings, stream: TextIO | None = None) -> None:
    """Serialize effective settings to JSON for diagnostics."""
    payload = asdict(settings)

    def _default(value: Any) -> str:
        if isinstance(value, Path):
            return str(value)
        raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")

    target = stream if stream is not None else sys.stdout
    json.dump(payload, target, indent=2, default=_default)
    target.write("\n")
