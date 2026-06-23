# AirCanvas Calculator — Drawing Package Implementation Summary

**Phase:** 4 — Drawing Layer  
**Date:** 2026-06-22  
**Status:** Complete and validated

---

## Pre-Implementation Verification

### Import validation (unchanged modules)

```text
import main     OK
import config   OK
import core      OK
import vision    OK
```

### Vision integration points (verified, not wired yet)

| Vision output | Drawing hook |
|---------------|--------------|
| `SmoothedPoint.x/y` (camera pixels) | `CanvasEngine.add_camera_smoothed_point()` |
| Camera pixel coordinates | `CanvasEngine.add_camera_point()` |
| `GestureFrame.cursor_normalized_x/y` | `CanvasEngine.add_normalized_point()` |
| Pinch draw start/stop (future) | `begin_stroke()` / `end_stroke()` via orchestration layer |

### Circular dependency check

| Check | Result |
|-------|--------|
| `drawing` → `vision` | **None** — uses `CameraPointSource` Protocol (duck typing) |
| `drawing` → `core` | **None** |
| `vision` → `drawing` | **None** |
| `core` → `drawing` | **None** (integration deferred) |

**Note:** Static analysis may flag `drawing.canvas_engine` → `math`; this is Python's **standard library** `math` module, not the planned `math/` application package.

### Post-drawing dependency graph

| Module | Project dependencies |
|--------|---------------------|
| `drawing/__init__.py` | `drawing` |
| `drawing/stroke.py` | none |
| `drawing/renderer.py` | `config`, `drawing` |
| `drawing/canvas_engine.py` | `config`, `drawing`, stdlib `math` |

---

## Generated Files

| File | Purpose |
|------|---------|
| `drawing/stroke.py` | `Point`, `Stroke`, `ActiveStroke` data structures |
| `drawing/renderer.py` | OpenCV BGR canvas rendering |
| `drawing/canvas_engine.py` | Stroke management, undo/redo, export, vision hooks |
| `drawing/__init__.py` | Public API exports |

---

## Module Details

### `drawing/stroke.py`

| Type | Description |
|------|-------------|
| `Point` | Canvas pixel coordinate (`x`, `y`) with int tuple conversion |
| `Stroke` | Committed stroke with `float32` NumPy buffer `(N, 2)` |
| `ActiveStroke` | Mutable in-progress stroke accumulator |

**Storage:** Points stored as contiguous `np.float32` arrays for efficient append and export.

### `drawing/renderer.py`

| Feature | Implementation |
|---------|----------------|
| Output format | BGR `uint8` ndarray `(height, width, 3)` — OpenCV compatible |
| Background | `DrawingSettings.background_color` (default white) |
| Stroke color | RGB settings converted to BGR for `cv2` |
| Drawing | `cv2.polylines`, `cv2.line` (LINE_AA), `cv2.circle` |
| Full redraw | `render_all(strokes, active_stroke)` |
| Incremental | `draw_interpolated_segment`, `draw_point`, `render_stroke_segment` |

### `drawing/canvas_engine.py`

| Feature | Implementation |
|---------|----------------|
| Stroke lifecycle | `begin_stroke()` → `add_*_point()` → `end_stroke()` |
| Interpolation | Linear interpolation when gap > `stroke_gap_interpolation_px` |
| Camera mapping | Scale camera pixels to canvas dimensions |
| Undo | `undo()` — pop last committed stroke |
| Redo | `redo()` — restore from redo stack |
| Clear | `clear()` — wipe strokes, redo stack, renderer buffer |
| Export | `export_image()` — BGR copy for OCR pipeline |
| Clamp | Points clamped to canvas bounds |

**Vision integration hooks (no runtime vision import):**

```python
# SmoothedPoint-compatible (camera pixel space)
engine.add_camera_smoothed_point(smoothed_point, camera_width=640, camera_height=480)

# Raw camera pixels
engine.add_camera_point(x, y, camera_width=640, camera_height=480)

# Normalized gesture cursor [0, 1]
engine.add_normalized_point(gesture.cursor_normalized_x, gesture.cursor_normalized_y)
```

`CameraPointSource` Protocol documents compatibility with `vision.smoother.SmoothedPoint`.

---

## Configuration Integration

| Setting | Used by |
|---------|---------|
| `DrawingSettings.canvas_width/height` | Canvas size |
| `DrawingSettings.stroke_color` | Stroke RGB color |
| `DrawingSettings.stroke_width` | Line thickness |
| `DrawingSettings.background_color` | Canvas fill |
| `SmoothingSettings.stroke_gap_interpolation_px` | Point interpolation threshold |

---

## Validation Results

| Test | Result |
|------|--------|
| `py_compile` all drawing modules | Pass |
| `import drawing` | Pass |
| Existing `main`, `config`, `core`, `vision` imports | Pass |
| Basic stroke draw + commit | Pass |
| `add_camera_smoothed_point` (vision hook) | Pass |
| `add_normalized_point` (gesture hook) | Pass |
| Undo / redo | Pass |
| `export_image()` shape `(H, W, 3)` dtype `uint8` | Pass |
| `clear()` empties canvas | Pass |
| Gap interpolation (>25px) produces extra points | Pass |
| Linter diagnostics | No errors |
| Circular dependencies | None |

---

## Intended Integration Flow (future phase)

```
GestureFrame.is_pinching == True  →  CanvasEngine.begin_stroke()
SmoothedPoint each frame          →  CanvasEngine.add_camera_smoothed_point()
Pinch released                    →  CanvasEngine.end_stroke()
                                  →  AppController.complete_stroke(point_count)
Evaluate button                   →  CanvasEngine.export_image()
                                  →  AppController.request_evaluation(image)
```

---

## Assumptions

| Item | Detail |
|------|--------|
| Color space | Internal settings use RGB; renderer converts to BGR for OpenCV |
| OCR input | White background + black strokes (configured via `DrawingSettings`) |
| Coordinate mapping | Uniform scale from camera resolution to canvas resolution |
| No Qt dependency | Drawing package is UI-agnostic |
| Thread safety | Not thread-safe; intended for camera worker thread or main thread with lock |

---

## Files Not Modified

- `main.py`, `config/`, `core/`, `vision/`
- `ocr/`, `math/`, `history/`, `ui/`

---

## Recommended Next Phase

**OCR package** (`ocr/`) — Tesseract primary engine, optional EasyOCR fallback, preprocessor, and router to consume `CanvasEngine.export_image()` output.
