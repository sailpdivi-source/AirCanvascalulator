# AirCanvas Calculator

A gesture-controlled air canvas desktop application. Draw mathematical expressions in the air using hand tracking, then evaluate them with OCR-powered recognition.

**Stack:** Python · MediaPipe · OpenCV · PyQt6 · Tesseract OCR · EasyOCR (optional fallback)

---

## Features (planned)

- Real-time hand tracking with pinch-to-draw
- Air canvas with stroke smoothing
- OCR evaluation via **Evaluate** button (Tesseract primary)
- Optional EasyOCR fallback on low-confidence results (lazy-loaded)
- Persistent evaluation history sidebar
- Premium glassmorphism dashboard UI

---

## Project Structure

```
AirCanvasCalculator/
├── main.py                         # ★ Application entry point (python main.py)
├── requirements.txt                # Required Python dependencies
├── requirements-optional.txt       # Optional EasyOCR fallback dependencies
├── README.md
├── .gitignore
│
├── config/                         # ── Configuration ──
│   ├── __init__.py
│   ├── settings.py                 # Global configuration (camera, OCR, theme)
│   └── constants.py                # Landmark indices, gesture thresholds
│
├── core/                           # ── Application Core ──
│   ├── __init__.py
│   ├── app_controller.py           # Pipeline orchestration + threading
│   ├── state.py                    # Application state machine
│   ├── events.py                   # Typed events and signal definitions
│   └── ocr_worker.py               # Background OCR evaluation thread
│
├── vision/                         # ── Vision Pipeline ──
│   ├── __init__.py
│   ├── camera.py                   # Webcam capture
│   ├── hand_tracker.py             # MediaPipe Hand Landmarker wrapper
│   ├── gesture_detector.py         # Pinch draw / clear gestures
│   └── smoother.py                 # Coordinate smoothing (EMA / One Euro)
│
├── drawing/                        # ── Drawing Engine ──
│   ├── __init__.py
│   ├── canvas_engine.py            # Stroke storage and coordinate mapping
│   ├── stroke.py                   # Stroke and Point dataclasses
│   └── renderer.py                 # Canvas rendering
│
├── ocr/                            # ── Modular OCR System ──
│   ├── __init__.py
│   ├── base_engine.py              # Abstract BaseOCREngine interface
│   ├── ocr_result.py               # OCRResult dataclass
│   ├── ocr_router.py               # Primary → fallback routing logic
│   ├── tesseract_engine.py         # Tesseract primary engine
│   ├── easyocr_engine.py           # EasyOCR optional fallback (lazy-loaded)
│   ├── confidence_evaluator.py     # Confidence threshold logic
│   └── preprocessor.py             # Image preprocessing pipeline
│
├── math/                           # ── Calculator / Math Engine ──
│   ├── __init__.py
│   ├── math_parser.py              # Expression tokenization and validation
│   └── expression_evaluator.py     # Safe math evaluation
│
├── history/                        # ── History Module ──
│   ├── __init__.py
│   ├── history_manager.py          # History business logic
│   ├── history_storage.py          # JSON persistence (atomic writes)
│   ├── history_entry.py            # HistoryEntry dataclass
│   └── history.json                # Persisted history store (runtime data)
│
├── ui/                             # ── Premium Dashboard UI ──
│   ├── __init__.py
│   ├── main_window.py              # Dashboard shell and layout
│   ├── sidebar/
│   │   ├── __init__.py
│   │   ├── sidebar.py              # Collapsible navigation sidebar
│   │   └── history_panel.py        # Chronological history list
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── video_widget.py         # Live camera feed with overlay
│   │   ├── canvas_widget.py        # Drawing surface
│   │   ├── result_panel.py         # Expression and result display
│   │   └── toolbar.py              # Clear, Evaluate, settings controls
│   ├── theme/
│   │   ├── __init__.py
│   │   ├── theme_engine.py         # Colors, radii, shadows
│   │   ├── glass_panel.py          # Glassmorphism container widget
│   │   ├── neon_button.py          # Neon glow button component
│   │   └── animations.py           # UI transitions and animations
│   └── styles/
│       ├── base.qss                # Base stylesheet
│       ├── glass.qss               # Glassmorphism styles
│       └── neon.qss                # Neon accent styles
│
├── assets/
│   ├── hand_landmarker.task        # MediaPipe hand model (download separately)
│   └── fonts/                      # Optional UI fonts
│
├── utils/
│   ├── __init__.py
│   ├── geometry.py                 # Distance, pinch detection, transforms
│   └── logger.py                   # Logging configuration
│
├── tests/
│   ├── __init__.py
│   ├── test_ocr_router.py
│   ├── test_tesseract_engine.py
│   ├── test_easyocr_engine.py
│   ├── test_history_manager.py
│   ├── test_history_storage.py
│   ├── test_math_parser.py
│   └── test_smoother.py
│
└── venv/                           # Local virtual environment (not committed)
```

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.10 – 3.13** | 3.13 tested |
| **Webcam** | Built-in or USB |
| **Tesseract OCR** | Required system binary |
| **~2 GB disk** | Minimum install (no EasyOCR) |
| **~4 GB disk** | With optional EasyOCR / PyTorch |

---

## Installation

### 1. Clone or open the project

```powershell
cd C:\Users\sailp\OneDrive\Desktop\AirCanvasCalculator
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install required Python dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Tesseract OCR (required)

Tesseract is the **primary OCR engine**. The application will not evaluate expressions without it.

#### Windows (recommended)

```powershell
winget install UB-Mannheim.TesseractOCR
```

Or download the installer from the [UB Mannheim Tesseract wiki](https://github.com/UB-Mannheim/tesseract/wiki).

After installation, verify:

```powershell
tesseract --version
```

If `tesseract` is not found, add the install directory to your `PATH` (typically `C:\Program Files\Tesseract-OCR`), or configure the path in `config/settings.py` once implemented:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

#### macOS

```bash
brew install tesseract
```

#### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install tesseract-ocr
```

### 5. Download the MediaPipe hand model

Download `hand_landmarker.task` and place it in `assets/`:

**URL:**
```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
```

**PowerShell:**

```powershell
Invoke-WebRequest `
  -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task" `
  -OutFile "assets\hand_landmarker.task"
```

### 6. Optional — EasyOCR fallback support

EasyOCR is **not required**. The application runs fully with Tesseract alone.

Install optional dependencies only if you want automatic fallback when Tesseract confidence is low:

```powershell
pip install -r requirements-optional.txt
```

| Behavior | Detail |
|----------|--------|
| Startup | EasyOCR is **never** loaded at launch |
| Trigger | Loaded lazily on first low-confidence Tesseract result |
| Unavailable | App shows a warning and continues with the Tesseract result |
| Models | Downloaded automatically on first fallback use (~100 MB) |

To pre-download EasyOCR models (optional):

```powershell
python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"
```

---

## Development

### Activate the environment

```powershell
.\venv\Scripts\Activate.ps1
```

### Verify core dependencies

```powershell
python -c "import mediapipe, cv2, numpy; from PyQt6.QtWidgets import QApplication; import pytesseract; print('Core imports OK')"
tesseract --version
```

### Verify optional EasyOCR (if installed)

```powershell
python -c "import easyocr; print('EasyOCR available')"
```

### Run tests (once implemented)

```powershell
python -m pytest tests/ -v
```

### Run the application (once implemented)

```powershell
python main.py
```

### Keyboard shortcuts (planned)

| Key | Action |
|-----|--------|
| `E` | Evaluate expression |
| `Ctrl+Enter` | Evaluate expression |
| `C` | Clear canvas |
| `Esc` | Quit |

---

## Run Commands (quick reference)

```powershell
# First-time setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install UB-Mannheim.TesseractOCR

# Optional fallback OCR
pip install -r requirements-optional.txt

# Launch (after implementation)
python main.py
```

---

## OCR Architecture

```
Evaluate button
      │
      ▼
Preprocessor ──► Tesseract (primary)
                      │
          confidence < threshold?
                 │         │
                yes        no
                 │         └──► Use Tesseract result
                 ▼
         EasyOCR installed?
           │           │
          yes          no
           │           └──► Warning toast + Tesseract result
           ▼
    EasyOCR (lazy load, first use only)
           │
           └──► Use best result
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `TesseractNotFoundError` | Install Tesseract and verify `tesseract --version` |
| Camera not detected | Close other apps using the webcam; try `camera_index=1` in settings |
| Low OCR accuracy | Draw larger, clearer strokes; ensure white canvas background |
| EasyOCR warning on evaluate | Install optional deps, or ignore — Tesseract result is still shown |
| `hand_landmarker.task` missing | Download model into `assets/` (see step 5) |
| Low FPS | Ensure camera runs at 640×480; close heavy background apps |

---

## License

Not yet specified.
