"""Canvas stroke management, coordinate mapping, and export."""

from __future__ import annotations

import logging
import math
from typing import Protocol, Sequence, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from config import DrawingSettings, SmoothingSettings
from drawing.renderer import CanvasRenderer
from drawing.stroke import ActiveStroke, Point, Stroke

logger = logging.getLogger(__name__)


@runtime_checkable
class CameraPointSource(Protocol):
    """Duck-typed point source compatible with :class:`vision.smoother.SmoothedPoint`."""

    x: float
    y: float


class CanvasEngine:
    """
    Manage stroke storage, undo/redo, and canvas rendering.

    The engine maps camera-space coordinates from the vision pipeline into
    canvas pixel coordinates and interpolates gaps between successive points
    for smooth stroke rendering.
    """

    def __init__(
        self,
        drawing_settings: DrawingSettings,
        smoothing_settings: SmoothingSettings,
    ) -> None:
        self._drawing_settings = drawing_settings
        self._interpolation_gap_px = float(smoothing_settings.stroke_gap_interpolation_px)
        self._renderer = CanvasRenderer(drawing_settings)
        self._strokes: list[Stroke] = []
        self._redo_stack: list[Stroke] = []
        self._active: ActiveStroke | None = None
        self._render_dirty = True

    @property
    def width(self) -> int:
        """Return the canvas width in pixels."""
        return self._drawing_settings.canvas_width

    @property
    def height(self) -> int:
        """Return the canvas height in pixels."""
        return self._drawing_settings.canvas_height

    @property
    def strokes(self) -> tuple[Stroke, ...]:
        """Return an immutable view of committed strokes."""
        return tuple(self._strokes)

    @property
    def stroke_count(self) -> int:
        """Return the number of committed strokes."""
        return len(self._strokes)

    @property
    def is_drawing(self) -> bool:
        """Return whether a stroke is currently being recorded."""
        return self._active is not None

    @property
    def is_empty(self) -> bool:
        """Return whether the canvas has no committed or active ink."""
        if self._strokes:
            return False
        return self._active is None or self._active.point_count == 0

    @property
    def can_undo(self) -> bool:
        """Return whether an undo operation is available."""
        return bool(self._strokes)

    @property
    def can_redo(self) -> bool:
        """Return whether a redo operation is available."""
        return bool(self._redo_stack)

    def begin_stroke(self) -> None:
        """Start recording a new active stroke."""
        if self._active is not None:
            logger.debug("Finalizing previous active stroke before starting a new one.")
            self.end_stroke()

        self._active = ActiveStroke.begin(
            color=self._drawing_settings.stroke_color,
            width=self._drawing_settings.stroke_width,
        )
        self._redo_stack.clear()
        logger.debug("Active stroke begun.")

    def end_stroke(self) -> Stroke | None:
        """
        Commit the active stroke to the canvas.

        Returns:
            The committed stroke, or ``None`` if no active stroke existed or
            the stroke contained no points.
        """
        if self._active is None:
            return None

        if self._active.point_count == 0:
            self._active = None
            return None

        committed = self._active.finalize()
        self._strokes.append(committed)
        self._active = None
        self._render_dirty = True
        logger.debug(
            "Stroke committed (%s, %d points).",
            committed.stroke_id,
            committed.point_count,
        )
        return committed

    def cancel_stroke(self) -> None:
        """Discard the active stroke without committing it."""
        self._active = None
        self._render_dirty = True
        logger.debug("Active stroke cancelled.")

    def add_canvas_point(self, x: float, y: float) -> bool:
        """
        Append a point that is already expressed in canvas pixel coordinates.

        Returns:
            ``True`` if the point was recorded, ``False`` if no active stroke.
        """
        if self._active is None:
            return False

        clamped = self._clamp_to_canvas(x, y)
        self._append_point_with_interpolation(clamped)
        return True

    def add_camera_point(
        self,
        x: float,
        y: float,
        *,
        camera_width: int,
        camera_height: int,
    ) -> bool:
        """
        Map a camera-space pixel coordinate into canvas space and record it.

        This method is the primary integration hook for the vision pipeline.

        Args:
            x: Horizontal coordinate in camera pixel space.
            y: Vertical coordinate in camera pixel space.
            camera_width: Width of the source camera frame.
            camera_height: Height of the source camera frame.

        Returns:
            ``True`` if the point was recorded, ``False`` if no active stroke.
        """
        mapped = self.map_camera_to_canvas(
            x,
            y,
            camera_width=camera_width,
            camera_height=camera_height,
        )
        return self.add_canvas_point(mapped.x, mapped.y)

    def add_camera_smoothed_point(
        self,
        point: CameraPointSource,
        *,
        camera_width: int,
        camera_height: int,
    ) -> bool:
        """
        Record a vision smoothed point without importing the vision package.

        Compatible with :class:`vision.smoother.SmoothedPoint`.
        """
        return self.add_camera_point(
            point.x,
            point.y,
            camera_width=camera_width,
            camera_height=camera_height,
        )

    def add_normalized_point(
        self,
        normalized_x: float,
        normalized_y: float,
    ) -> bool:
        """
        Append a point using normalized ``[0, 1]`` canvas coordinates.

        Compatible with gesture cursor output from :class:`vision.gesture_detector.GestureFrame`.
        """
        if self._active is None:
            return False

        x = normalized_x * self.width
        y = normalized_y * self.height
        return self.add_canvas_point(x, y)

    def map_camera_to_canvas(
        self,
        x: float,
        y: float,
        *,
        camera_width: int,
        camera_height: int,
    ) -> Point:
        """Convert camera pixel coordinates into canvas pixel coordinates."""
        if camera_width <= 0 or camera_height <= 0:
            raise ValueError("camera dimensions must be positive")

        scale_x = self.width / float(camera_width)
        scale_y = self.height / float(camera_height)
        return Point(x=x * scale_x, y=y * scale_y)

    def clear(self) -> None:
        """Remove all strokes, undo history, and reset the canvas."""
        self._strokes.clear()
        self._redo_stack.clear()
        self._active = None
        self._renderer.clear()
        self._render_dirty = False
        logger.info("Canvas cleared.")

    def undo(self) -> Stroke | None:
        """
        Undo the most recent committed stroke.

        Returns:
            The removed stroke, or ``None`` if the canvas is empty.
        """
        if not self._strokes:
            return None

        removed = self._strokes.pop()
        self._redo_stack.append(removed)
        self._render_dirty = True
        logger.debug("Undo stroke %s.", removed.stroke_id)
        return removed

    def redo(self) -> Stroke | None:
        """
        Redo the most recently undone stroke.

        Returns:
            The restored stroke, or ``None`` if the redo stack is empty.
        """
        if not self._redo_stack:
            return None

        restored = self._redo_stack.pop()
        self._strokes.append(restored)
        self._render_dirty = True
        logger.debug("Redo stroke %s.", restored.stroke_id)
        return restored

    def render(self, *, force_full: bool = False) -> NDArray[np.uint8]:
        """
        Render the current canvas state to an OpenCV-compatible BGR image.

        Args:
            force_full: When ``True``, redraw every stroke from scratch.

        Returns:
            BGR ``uint8`` image with shape ``(height, width, 3)``.
        """
        if force_full or self._render_dirty:
            active = self._active.stroke if self._active is not None else None
            self._renderer.render_all(self._strokes, active_stroke=active)
            self._render_dirty = False
        return self._renderer.image

    def export_image(self, *, force_full: bool = True) -> NDArray[np.uint8]:
        """
        Export the canvas as an OpenCV-compatible BGR image for OCR or saving.

        Args:
            force_full: Ensure a full redraw before export.

        Returns:
            A copy of the rendered BGR canvas image.
        """
        image = self.render(force_full=force_full)
        logger.debug("Canvas exported (%dx%d).", image.shape[1], image.shape[0])
        return image.copy()

    def _append_point_with_interpolation(self, point: Point) -> None:
        if self._active is None:
            return

        stroke = self._active.stroke
        previous = self._active.last_point

        if previous is None:
            stroke.append_point(point.x, point.y)
            self._active.last_point = point
            self._renderer.draw_point(
                point,
                color=stroke.color,
                width=stroke.width,
            )
            return

        gap = math.hypot(point.x - previous.x, point.y - previous.y)
        if gap <= self._interpolation_gap_px:
            stroke.append_point(point.x, point.y)
            self._renderer.draw_interpolated_segment(
                previous,
                point,
                color=stroke.color,
                width=stroke.width,
            )
        else:
            interpolated = self._interpolate_points(previous, point, gap)
            stroke.append_points(interpolated)
            for index in range(1, interpolated.shape[0]):
                start = Point(float(interpolated[index - 1, 0]), float(interpolated[index - 1, 1]))
                end = Point(float(interpolated[index, 0]), float(interpolated[index, 1]))
                self._renderer.draw_interpolated_segment(
                    start,
                    end,
                    color=stroke.color,
                    width=stroke.width,
                )

        self._active.last_point = point

    def _interpolate_points(
        self,
        start: Point,
        end: Point,
        gap: float,
    ) -> NDArray[np.float32]:
        steps = max(2, int(math.ceil(gap / self._interpolation_gap_px)) + 1)
        xs = np.linspace(start.x, end.x, steps, dtype=np.float32)
        ys = np.linspace(start.y, end.y, steps, dtype=np.float32)
        return np.column_stack((xs, ys))

    def _clamp_to_canvas(self, x: float, y: float) -> Point:
        clamped_x = min(max(x, 0.0), float(self.width - 1))
        clamped_y = min(max(y, 0.0), float(self.height - 1))
        return Point(x=clamped_x, y=clamped_y)

    def replace_strokes(self, strokes: Sequence[Stroke]) -> None:
        """Replace all committed strokes and mark the canvas dirty."""
        self._strokes = [stroke.copy() for stroke in strokes]
        self._redo_stack.clear()
        self._active = None
        self._render_dirty = True
