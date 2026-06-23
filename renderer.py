"""OpenCV-based canvas rendering for stroke visualization and export."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from config import DrawingSettings
from drawing.stroke import Point, Stroke

logger = logging.getLogger(__name__)


def _rgb_to_bgr(color: tuple[int, int, int]) -> tuple[int, int, int]:
    red, green, blue = color
    return (blue, green, red)


class CanvasRenderer:
    """
    Render strokes onto an OpenCV-compatible BGR image buffer.

    The renderer maintains an internal canvas that can be fully redrawn or
    updated incrementally when new segments are added.
    """

    def __init__(self, settings: DrawingSettings) -> None:
        self._settings = settings
        self._canvas = self._create_blank_canvas()

    @property
    def width(self) -> int:
        """Return the canvas width in pixels."""
        return self._settings.canvas_width

    @property
    def height(self) -> int:
        """Return the canvas height in pixels."""
        return self._settings.canvas_height

    @property
    def image(self) -> NDArray[np.uint8]:
        """Return a copy of the current rendered BGR image."""
        return self._canvas.copy()

    def clear(self) -> None:
        """Reset the canvas to the configured background color."""
        self._canvas = self._create_blank_canvas()
        logger.debug("Canvas renderer cleared.")

    def render_all(
        self,
        strokes: Sequence[Stroke],
        active_stroke: Stroke | None = None,
    ) -> NDArray[np.uint8]:
        """
        Fully redraw every committed and active stroke.

        Returns:
            The rendered BGR image buffer.
        """
        self.clear()
        for stroke in strokes:
            self._draw_stroke(stroke, self._canvas)
        if active_stroke is not None and active_stroke.point_count > 0:
            self._draw_stroke(active_stroke, self._canvas)
        return self.image

    def render_stroke_segment(
        self,
        stroke: Stroke,
        start_index: int,
    ) -> None:
        """
        Incrementally draw new segments of ``stroke`` from ``start_index``.

        Args:
            stroke: Stroke being extended.
            start_index: Index of the first new point to draw.
        """
        if stroke.point_count < 2:
            return
        if start_index < 1:
            start_index = 1

        color = _rgb_to_bgr(stroke.color)
        thickness = max(1, stroke.width)
        points = stroke.points

        for index in range(start_index, stroke.point_count):
            start = points[index - 1]
            end = points[index]
            cv2.line(
                self._canvas,
                (int(round(start[0])), int(round(start[1]))),
                (int(round(end[0])), int(round(end[1]))),
                color,
                thickness,
                lineType=cv2.LINE_AA,
            )

    def draw_point(
        self,
        point: Point,
        *,
        color: tuple[int, int, int],
        width: int,
    ) -> None:
        """Draw a single point as a filled circle."""
        radius = max(1, width // 2)
        cv2.circle(
            self._canvas,
            point.as_int_tuple(),
            radius,
            _rgb_to_bgr(color),
            thickness=-1,
            lineType=cv2.LINE_AA,
        )

    def draw_interpolated_segment(
        self,
        start: Point,
        end: Point,
        *,
        color: tuple[int, int, int],
        width: int,
    ) -> None:
        """Draw a single anti-aliased segment between two canvas points."""
        cv2.line(
            self._canvas,
            start.as_int_tuple(),
            end.as_int_tuple(),
            _rgb_to_bgr(color),
            max(1, width),
            lineType=cv2.LINE_AA,
        )

    def draw_polyline(
        self,
        points: Iterable[Point],
        *,
        color: tuple[int, int, int],
        width: int,
    ) -> None:
        """Draw a connected polyline through the provided canvas points."""
        coordinates = np.asarray([point.as_tuple() for point in points], dtype=np.float32)
        if coordinates.shape[0] < 2:
            return
        cv2.polylines(
            self._canvas,
            [coordinates.astype(np.int32)],
            isClosed=False,
            color=_rgb_to_bgr(color),
            thickness=max(1, width),
            lineType=cv2.LINE_AA,
        )

    def _create_blank_canvas(self) -> NDArray[np.uint8]:
        height = self._settings.canvas_height
        width = self._settings.canvas_width
        background = _rgb_to_bgr(self._settings.background_color)
        canvas = np.empty((height, width, 3), dtype=np.uint8)
        canvas[:] = background
        return canvas

    def _draw_stroke(self, stroke: Stroke, target: NDArray[np.uint8]) -> None:
        if stroke.point_count == 0:
            return

        color = _rgb_to_bgr(stroke.color)
        thickness = max(1, stroke.width)
        points = stroke.points.astype(np.int32)

        if stroke.point_count == 1:
            center = (int(points[0, 0]), int(points[0, 1]))
            cv2.circle(target, center, max(1, thickness // 2), color, thickness=-1, lineType=cv2.LINE_AA)
            return

        cv2.polylines(
            target,
            [points],
            isClosed=False,
            color=color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
