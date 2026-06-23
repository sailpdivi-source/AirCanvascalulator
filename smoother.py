"""Exponential moving average coordinate smoothing for hand tracking."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from config import SmoothingSettings
from config.constants import DRAW_DEAD_ZONE_PX

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SmoothedPoint:
    """A smoothed two-dimensional point in pixel coordinates."""

    x: float
    y: float
    raw_x: float
    raw_y: float


class EMASmoother:
    """
    Apply exponential moving average smoothing to 2D tracking coordinates.

    The smoother rejects micro-movements below a dead-zone threshold and
    ignores outlier jumps that exceed the configured pixel distance.
    """

    def __init__(
        self,
        settings: SmoothingSettings,
        *,
        dead_zone_px: int = DRAW_DEAD_ZONE_PX,
    ) -> None:
        self._alpha = settings.ema_alpha
        self._dead_zone_px = float(dead_zone_px)
        self._outlier_threshold_px = float(settings.outlier_jump_threshold_px)
        self._previous: tuple[float, float] | None = None

    @property
    def alpha(self) -> float:
        """Return the EMA alpha coefficient."""
        return self._alpha

    def reset(self) -> None:
        """Clear internal smoothing state."""
        self._previous = None
        logger.debug("EMA smoother state reset.")

    def smooth(
        self,
        x: float,
        y: float,
        *,
        frame_width: int,
        frame_height: int,
    ) -> SmoothedPoint | None:
        """
        Smooth normalized coordinates into pixel space.

        Args:
            x: Normalized x coordinate in ``[0, 1]``.
            y: Normalized y coordinate in ``[0, 1]``.
            frame_width: Frame width used for pixel conversion.
            frame_height: Frame height used for pixel conversion.

        Returns:
            A :class:`SmoothedPoint` or ``None`` when the input is rejected by
            the dead-zone filter before any previous sample exists.
        """
        pixel_x = x * frame_width
        pixel_y = y * frame_height

        if self._previous is None:
            self._previous = (pixel_x, pixel_y)
            return SmoothedPoint(
                x=pixel_x,
                y=pixel_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        previous_x, previous_y = self._previous
        delta = math.hypot(pixel_x - previous_x, pixel_y - previous_y)

        if delta > self._outlier_threshold_px:
            logger.debug(
                "Rejected outlier point (delta=%.2f px, threshold=%.2f px).",
                delta,
                self._outlier_threshold_px,
            )
            return SmoothedPoint(
                x=previous_x,
                y=previous_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        if delta < self._dead_zone_px:
            return SmoothedPoint(
                x=previous_x,
                y=previous_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        smoothed_x = self._alpha * pixel_x + (1.0 - self._alpha) * previous_x
        smoothed_y = self._alpha * pixel_y + (1.0 - self._alpha) * previous_y
        self._previous = (smoothed_x, smoothed_y)

        return SmoothedPoint(
            x=smoothed_x,
            y=smoothed_y,
            raw_x=pixel_x,
            raw_y=pixel_y,
        )

    def smooth_pixels(self, pixel_x: float, pixel_y: float) -> SmoothedPoint:
        """
        Smooth coordinates that are already expressed in pixel space.

        Args:
            pixel_x: Horizontal pixel coordinate.
            pixel_y: Vertical pixel coordinate.

        Returns:
            The smoothed point in pixel coordinates.
        """
        if self._previous is None:
            self._previous = (pixel_x, pixel_y)
            return SmoothedPoint(
                x=pixel_x,
                y=pixel_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        previous_x, previous_y = self._previous
        delta = math.hypot(pixel_x - previous_x, pixel_y - previous_y)

        if delta > self._outlier_threshold_px:
            return SmoothedPoint(
                x=previous_x,
                y=previous_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        if delta < self._dead_zone_px:
            return SmoothedPoint(
                x=previous_x,
                y=previous_y,
                raw_x=pixel_x,
                raw_y=pixel_y,
            )

        smoothed_x = self._alpha * pixel_x + (1.0 - self._alpha) * previous_x
        smoothed_y = self._alpha * pixel_y + (1.0 - self._alpha) * previous_y
        self._previous = (smoothed_x, smoothed_y)
        return SmoothedPoint(
            x=smoothed_x,
            y=smoothed_y,
            raw_x=pixel_x,
            raw_y=pixel_y,
        )
