# AirCanvas Calculator — Implementation Summary

**Last updated:** 2026-06-22  
**Implementation phase:** Configuration layer + project scaffold (no application modules yet)

---

## 1. List of All Generated Files

### Python source (implemented)

| File | Status |
|------|--------|
| `main.py` | Implemented |
| `config/__init__.py` | Implemented |
| `config/settings.py` | Implemented |
| `config/constants.py` | Implemented |

### Project configuration & documentation

| File | Status |
|------|--------|
| `requirements.txt` | Implemented |
| `requirements-optional.txt` | Implemented |
| `.gitignore` | Implemented |
| `README.md` | Implemented |
| `IMPLEMENTATION_SUMMARY.md` | This document |

### Runtime / data files

| File | Status |
|------|--------|
| `history/history.json` | Seeded empty (`[]`) |
| `logs/aircanvas.log` | Created at runtime by logging setup |

### Directory placeholders (`.gitkeep` only — no source code)

| Path |
|------|
| `assets/fonts/.gitkeep` |
| `core/.gitkeep` |
| `drawing/.gitkeep` |
| `math/.gitkeep` |
| `ocr/.gitkeep` |
| `tests/.gitkeep` |
| `utils/.gitkeep` |
| `vision/.gitkeep` |
| `ui/sidebar/.gitkeep` |
| `ui/widgets/.gitkeep` |
| `ui/theme/.gitkeep` |
| `ui/styles/.gitkeep` |

### Planned but not yet created

All `.py` modules listed in `README.md` outside of `config/` and `main.py`, including:

- `core/` — `app_controller.py`, `state.py`, `events.py`, `ocr_worker.py`
- `vision/` — camera, hand tracking, gestures, smoothing
- `drawing/` — canvas engine, strokes, renderer
- `ocr/` — modular OCR system
- `math/` — parser and evaluator
- `history/` — manager, storage, entry dataclass
- `ui/` — main window, sidebar, widgets, theme, styles
- `utils/` — geometry, logger
- `tests/` — unit tests
- `assets/hand_landmarker.task` — MediaPipe model (download required)

---

## 2. Purpose of Each File

### `main.py`

Application entry point. Parses CLI arguments, loads configuration, configures logging, validates the environment, applies the Tesseract path to `pytesseract`, and launches the GUI when application modules are available.

**CLI flags:**

| Flag | Purpose |
|------|---------|
| `--config PATH` | Load overrides from a JSON file |
| `--log-level LEVEL` | Override logging level for the session |
| `--validate-only` | Run environment checks and exit |
| `--print-config` | Dump effective settings as JSON |
| `--version` | Print application version |

### `config/__init__.py`

Public configuration API. Re-exports settings loaders, validation helpers, dataclass types, and commonly used constants so other modules can import from `config` directly.

### `config/settings.py`

Central configuration management:

- Defines frozen dataclasses for all settings domains (`Settings`, `LogSettings`, `CameraSettings`, `VisionSettings`, `SmoothingSettings`, `OCRSettings`, `DrawingSettings`, `HistorySettings`, `UISettings`)
- `load_settings()` — merges defaults, optional JSON file, and environment variables
- `configure_logging()` — console + rotating file logging to `logs/aircanvas.log`
- `validate_environment()` — checks hand model, Tesseract, writable paths
- `resolve_tesseract_command()` — locates Tesseract on PATH or Windows install paths
- `apply_tesseract_to_pytesseract()` — wires resolved path into `pytesseract`
- `dump_settings()` — serializes effective config for diagnostics
- `ConfigurationError` — raised on invalid configuration input

### `config/constants.py`

Immutable application constants: app metadata, MediaPipe landmark indices, gesture thresholds, vision/OCR/history/UI defaults, feature flags, environment variable names, and Windows Tesseract candidate paths.

### `requirements.txt`

Pinned required Python dependencies: MediaPipe, OpenCV Contrib, NumPy, PyQt6, pytesseract, Pillow, packaging.

### `requirements-optional.txt`

Optional EasyOCR fallback dependencies. Extends `requirements.txt` with `easyocr==1.7.2`. Not required for the application to run.

### `.gitignore`

Excludes virtual environment, caches, runtime history, downloaded model assets, EasyOCR cache, and log files from version control.

### `README.md`

Project overview, full planned folder structure, installation guide (Tesseract, MediaPipe model, optional EasyOCR), development commands, and troubleshooting.

### `history/history.json`

Empty JSON array seed for the history store. Gitignored at runtime once populated; created locally for first-run setup.

### `.gitkeep` files

Preserve empty package directories in version control until their modules are implemented.

---

## 3. Dependencies Between Files

### Import graph (implemented code)

```
main.py
  └── config/__init__.py
        ├── config/constants.py    (no internal project imports)
        └── config/settings.py
              └── config/constants.py
```

### Runtime dependency graph

```
main.py
  ├── config (settings, logging, validation)
  ├── pytesseract          (via apply_tesseract_to_pytesseract)
  ├── PyQt6                  (deferred — only in _launch_application)
  ├── core.app_controller    (deferred — not yet implemented)
  └── ui.main_window         (deferred — not yet implemented)
```

### Configuration precedence

```
config/constants.py  →  default values
        ↓
config/settings.py   →  JSON file (optional, via --config or AIRCANVAS_CONFIG_FILE)
        ↓
Environment variables (AIRCANVAS_LOG_LEVEL, AIRCANVAS_CAMERA_INDEX, etc.)
        ↓
CLI overrides (--log-level)
        ↓
Effective Settings object passed to all future modules
```

### Planned module coupling (approved architecture)

| Module | May depend on | Must not depend on |
|--------|---------------|-------------------|
| `main.py` | `config`, `core`, `ui` | `ocr`, `vision`, `history` directly |
| `config` | `constants` only | Any other application package |
| `core` | `config`, `vision`, `drawing`, `ocr`, `math`, `history` | `ui` concrete widgets |
| `vision` | `config`, `utils` | `ocr`, `ui`, `history` |
| `drawing` | `config` | `vision`, `ocr`, `ui` |
| `ocr` | `config` | `ui`, `history` |
| `math` | None (pure logic) | All other packages |
| `history` | `config` | `ocr`, `vision`, `ui` |
| `ui` | `config`, `core` (signals) | Concrete OCR/vision engines |

No circular dependencies exist in the implemented code. The approved architecture enforces a hub-and-spoke pattern through `core.app_controller`.

---

## 4. Entry Point Flow (`main.py` → …)

```
python main.py
      │
      ▼
┌─────────────────────────┐
│  parse CLI arguments    │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  load_settings()        │  defaults + JSON + env vars
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  apply CLI overrides    │  --log-level
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  configure_logging()    │  stdout + logs/aircanvas.log
└───────────┬─────────────┘
            ▼
      --print-config? ──yes──► dump_settings() ──► exit 0
            │ no
            ▼
┌─────────────────────────┐
│  validate_environment() │
│  • hand_landmarker.task │
│  • Tesseract binary     │
│  • log dir writable     │
│  • history file writable│
└───────────┬─────────────┘
            │ errors? ──yes──► log errors ──► exit 1
            ▼ no
┌─────────────────────────┐
│ apply_tesseract_to_     │
│ pytesseract()           │
└───────────┬─────────────┘
            ▼
     --validate-only? ──yes──► log success ──► exit 0
            │ no
            ▼
┌─────────────────────────┐
│  _launch_application()  │
│  • import PyQt6         │
│  • import AppController│  ← not yet implemented
│  • import MainWindow    │  ← not yet implemented
│  • QApplication         │
│  • controller.start()   │
│  • app.exec()           │
└───────────┬─────────────┘
            ▼
         exit code
```

### Future full application flow (once modules are implemented)

```
main.py
  → core.app_controller.AppController
       ├── vision/          (camera thread, hand tracking, smoothing)
       ├── drawing/         (canvas engine, stroke rendering)
       ├── ocr/             (OCR worker thread on Evaluate)
       ├── math/            (expression parsing and evaluation)
       ├── history/         (persist and emit history entries)
       └── ui.main_window   (dashboard, sidebar, widgets, theme)
```

---

## 5. Known Issues and Assumptions

### Known issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| `core.app_controller` and `ui.main_window` do not exist | `python main.py` without flags fails at GUI launch | Use `--validate-only` or `--print-config` |
| Tesseract not installed on system PATH | `validate_environment()` fails | Install via `winget install UB-Mannheim.TesseractOCR` or set `AIRCANVAS_TESSERACT_CMD` |
| `assets/hand_landmarker.task` not downloaded | `validate_environment()` fails | Download per README instructions |
| `ui/styles/` directory empty | Warning logged at validation; non-fatal | Styles will be added with UI implementation |
| `utils/logger.py` not implemented | Logging is configured in `config/settings.py` instead | Acceptable for current phase; may be extracted later |
| Existing `venv` may contain both `opencv-python` and `opencv-contrib-python` | Potential OpenCV conflict | Reinstall from `requirements.txt` using only `opencv-contrib-python` |

### Assumptions

| Assumption | Detail |
|------------|--------|
| Python version | 3.10–3.13; developed and tested on 3.13.1 |
| Operating system | Windows 10/11 primary; Tesseract path resolution includes Windows candidates |
| Entry point | `python main.py` from project root (ensures `config` package resolves) |
| Configuration is immutable | `Settings` and nested dataclasses are frozen; overrides produce new instances |
| Tesseract is required | Application cannot evaluate expressions without the Tesseract binary |
| EasyOCR is optional | Not imported or loaded at startup; lazy fallback deferred to `ocr/` module |
| OCR trigger | Evaluate button only in v1; `ENABLE_GESTURE_EVALUATE = False` |
| History persistence | `history/history.json` with atomic writes (to be implemented in `history/`) |
| MediaPipe model | Uses Tasks API (`hand_landmarker.task`), not legacy `mp.solutions.hands` |
| High DPI | `AA_EnableHighDpiScaling` enabled before `QApplication` creation |
| Logging directory | `logs/` is auto-created; listed in `.gitignore` |
| Phased implementation | Each package (`core`, `vision`, `drawing`, etc.) will be built incrementally |

### Commands verified in current phase

```powershell
python main.py --version          # Works
python main.py --print-config     # Works
python main.py --validate-only    # Works only if Tesseract + hand model are present
python main.py                    # Fails until core/ and ui/ modules exist
```

---

## Implementation Progress

| Layer | Progress |
|-------|----------|
| Project scaffold | Complete |
| Dependencies & docs | Complete |
| Configuration (`config/`) | Complete |
| Entry point (`main.py`) | Complete (bootstrap only) |
| Core orchestration | Not started |
| Vision pipeline | Not started |
| Drawing engine | Not started |
| OCR system | Not started |
| Math / calculator | Not started |
| History module | Not started |
| UI / theme | Not started |
| Utilities | Not started |
| Tests | Not started |

**Recommended next implementation phase:** `core/` (`app_controller.py`, `state.py`, `events.py`, `ocr_worker.py`)
