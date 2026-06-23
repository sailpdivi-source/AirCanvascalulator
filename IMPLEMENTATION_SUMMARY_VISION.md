# AirCanvas Calculator — Vision Package Implementation Summary

**Phase:** 3 — Vision Layer  
**Date:** 2026-06-22  
**Status:** Complete and validated

---

## Pre-Implementation Dependency Analysis

### Project import graph (before Vision)

| Module | Project dependencies |
|--------|---------------------|
| `main.py` | `config`, `core`, `ui` (deferred) |
| `config/` | `config` (internal only) |
| `config/constants.py` | none |
| `config/settings.py` | `config` |
| `core/state.py` | none |
| `core/events.py` | none |
| `core/ocr_worker.py` | `config`, `core` (+ lazy `ocr`, `math`) |
| `core/app_controller.py` | `config`, `core` (+ lazy `history`) |

### Post-Vision import graph

| Module | Project dependencies |
|--------|---------------------|
| `vision/__init__.py` | `vision` (internal re-exports) |
| `vision/camera.py` | `config` |
| `vision/hand_tracker.py` | `config` |
| `vision/gesture_detector.py` | `config`, `vision` |
| `vision/smoother.py` | `config` (+ stdlib `math`) |

### Circular dependency check

| Check | Result |
|-------|--------|
| `vision` → `core` | **None** — verified |
| `vision` → `ocr` / `ui` / `history` | **None** — verified |
| `core` → `vision` | **None** (integration deferred to future phase) |
| `config` internal cycle | `config/__init__` → `config.constants` / `config.settings` — acyclic |

**Note:** Static analysis flags `vision.smoother` → `math`; this is Python's **standard library** `math` module (`import math`), not the planned `math/` application package.

### Import verification

```text
import main          OK
import config        OK
import core          OK
import vision        OK
py_compile vision/*   OK
```

---

## Generated Files

| File | Lines (approx.) | Purpose |
|------|-----------------|---------|
| `vision/__init__.py` | 40 | Public API exports |
| `vision/camera.py` | 200 | OpenCV capture + reconnect |
| `vision/hand_tracker.py` | 230 | MediaPipe Hand Landmarker (Tasks API) |
| `vision/gesture_detector.py` | 200 | Pinch + open-palm gesture detection |
| `vision/smoother.py` | 165 | EMA coordinate smoothing |

---

## Module Details

### `vision/camera.py`

**Classes:** `CameraCapture`, `CameraFrame`, `CameraState`, `CameraError`

| Feature | Implementation |
|---------|----------------|
| OpenCV capture | `cv2.VideoCapture` with configurable index, resolution, FPS, buffer size |
| Platform backend | `CAP_DSHOW` on Windows, default backend elsewhere |
| Mirror | Optional horizontal flip via `CameraSettings.mirror` |
| Reconnect | After 5 consecutive read failures, up to 5 reconnect attempts with 0.5s delay |
| Context manager | `with CameraCapture(...) as cam:` support |
| Logging | Open, close, read failures, reconnect attempts |

### `vision/hand_tracker.py`

**Classes:** `HandTracker`, `TrackedHand`, `LandmarkPoint`, `HandTrackingResult`

| Feature | Implementation |
|---------|----------------|
| API | MediaPipe Tasks `HandLandmarker` in `VIDEO` mode |
| Model | `hand_landmarker.task` from `VisionSettings.hand_model_path` |
| Input | BGR OpenCV frame → RGB `mp.Image` |
| Timestamps | Monotonic ms; auto-incremented if duplicate |
| Output | Up to `num_hands` tracked hands with 21 normalized landmarks |
| Derived data | Index fingertip, thumb tip, handedness label |
| Errors | `HandTrackerError` on missing model or detection failure |

### `vision/gesture_detector.py`

**Classes:** `GestureDetector`, `GestureFrame`, `GestureKind`

| Gesture | Detection logic |
|---------|-----------------|
| `HOVER` | Hand visible, pinch inactive |
| `PINCH_DRAW` | Thumb–index distance below threshold with debounce |
| `OPEN_PALM_CLEAR` | All four fingers extended, held ≥ `PALM_CLEAR_HOLD_MS` (1500 ms) |
| `NONE` | No hand detected (resets after `hand_lost_timeout_ms`) |

| Feature | Implementation |
|---------|----------------|
| Pinch hysteresis | Separate activate (`pinch_threshold`) / release (`pinch_release_threshold`) |
| Debounce | `gesture_debounce_frames` consecutive frames required |
| Cursor | Normalized index fingertip coordinates in `GestureFrame` |

### `vision/smoother.py`

**Classes:** `EMASmoother`, `SmoothedPoint`

| Feature | Implementation |
|---------|----------------|
| Algorithm | Exponential moving average (`SmoothingSettings.ema_alpha`) |
| Dead zone | Ignores movement below `dead_zone_px` (from `VisionSettings`) |
| Outlier rejection | Rejects jumps above `outlier_jump_threshold_px` |
| Input | Normalized (0–1) or raw pixel coordinates |
| Reset | `reset()` clears internal state on hand loss / canvas clear |

---

## Configuration Integration

| Setting source | Used by |
|----------------|---------|
| `CameraSettings` | `CameraCapture` |
| `VisionSettings` | `HandTracker`, `GestureDetector` |
| `SmoothingSettings` | `EMASmoother` |
| `config.constants` | Landmark indices, `PALM_CLEAR_HOLD_MS`, `DRAW_DEAD_ZONE_PX` |

Example wiring:

```python
from config import load_settings
from vision import CameraCapture, HandTracker, GestureDetector, EMASmoother

settings = load_settings()

camera = CameraCapture(settings.camera)
tracker = HandTracker(settings.vision)
gestures = GestureDetector(settings.vision)
smoother = EMASmoother(
    settings.smoothing,
    dead_zone_px=settings.vision.draw_dead_zone_px,
)

camera.open()
tracker.initialize()

frame = camera.read()
tracking = tracker.process_frame(frame.image, frame.timestamp_ms)
gesture = gestures.process(tracking, monotonic_ms=frame.timestamp_ms)

if gesture.hand_detected:
    point = smoother.smooth(
        gesture.cursor_normalized_x,
        gesture.cursor_normalized_y,
        frame_width=settings.camera.width,
        frame_height=settings.camera.height,
    )
```

---

## Intended Integration with Core (future phase)

```
CameraCapture.read()
    → HandTracker.process_frame()
        → GestureDetector.process()
            → EMASmoother.smooth()
                → AppController.begin_drawing() / complete_stroke()
```

The vision package does **not** import `core` — wiring will occur in `core/app_controller.py` or a future vision worker thread in a subsequent phase.

---

## Internal Validation Results

| Test | Result |
|------|--------|
| `py_compile` all vision modules | Pass |
| `import vision` | Pass |
| `EMASmoother` unit smoke test | Pass |
| `GestureDetector` pinch debounce test | Pass → `GestureKind.PINCH_DRAW` |
| `vision` does not import `core` | Pass |
| Linter diagnostics | No errors |
| Existing `main`, `config`, `core` imports | Unchanged — Pass |

---

## Known Assumptions and Limitations

| Item | Detail |
|------|--------|
| Hand model required | `assets/hand_landmarker.task` must exist before `HandTracker.initialize()` |
| Camera hardware | Physical webcam needed for live capture tests |
| Open palm detection | Assumes upright hand facing camera; finger extension uses normalized Y comparison |
| `CAP_DSHOW` | Windows-only backend; other platforms use default OpenCV backend |
| No vision worker thread yet | Modules are synchronous; threading integration is a future step |
| No drawing integration | Vision outputs coordinates only; canvas wiring is Phase 4+ |
| Math package naming | Future `math/` app package will shadow stdlib; use explicit imports in workers |

---

## Files Not Modified

- `main.py`
- `config/`
- `core/`
- `ocr/`, `drawing/`, `ui/`, `history/`, `math/`
- `IMPLEMENTATION_SUMMARY.md` (original; this is a separate vision-phase document)

---

## Recommended Next Phase

**Drawing engine** (`drawing/`) — consume smoothed coordinates from vision and commit strokes to the canvas, calling `AppController.begin_drawing()` and `complete_stroke()`.
