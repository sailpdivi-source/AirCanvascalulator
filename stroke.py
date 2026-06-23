"""Stroke and point data structures for the drawing canvas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class Point:
    """A two-dimensional canvas coordinate in pixel space."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """Return the coordinates as a plain tuple."""
        return (self.x, self.y)

    def as_int_tuple(self) -> tuple[int, int]:
        """Return the coordinates rounded to integer pixel positions."""
        return (int(round(self.x)), int(round(self.y)))


@dataclass(slots=True)
class Stroke:
    """
    A committed drawing stroke stored as an efficient NumPy point buffer.

    Points are stored in ``float32`` with shape ``(N, 2)`` where each row is
    ``[x, y]`` in canvas pixel coordinates.
    """

    stroke_id: str
    points: NDArray[np.float32]
    color: tuple[int, int, int]
    width: int

    @property
    def point_count(self) -> int:
        """Return the number of points in the stroke."""
        if self.points.size == 0:
            return 0
        return int(self.points.shape[0])

    @classmethod
    def create(
        cls,
        *,
        color: tuple[int, int, int],
        width: int,
        stroke_id: str | None = None,
    ) -> Self:
        """Create an empty stroke ready to receive points."""
        return cls(
            stroke_id=stroke_id or str(uuid4()),
            points=np.empty((0, 2), dtype=np.float32),
            color=color,
            width=width,
        )

    @classmethod
    def from_coordinates(
        cls,
        coordinates: NDArray[np.float32] | list[tuple[float, float]],
        *,
        color: tuple[int, int, int],
        width: int,
        stroke_id: str | None = None,
    ) -> Stroke:
        """Build a stroke from an explicit coordinate sequence."""
        if isinstance(coordinates, list):
            array = np.asarray(coordinates, dtype=np.float32)
        else:
            array = np.ascontiguousarray(coordinates, dtype=np.float32)

        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError("coordinates must have shape (N, 2)")

        return cls(
            stroke_id=stroke_id or str(uuid4()),
            points=array,
            color=color,
            width=width,
        )

    def append_point(self, x: float, y: float) -> None:
        """Append a single point to the stroke buffer."""
        new_point = np.asarray([[x, y]], dtype=np.float32)
        if self.points.size == 0:
            self.points = new_point
        else:
            self.points = np.vstack((self.points, new_point))

    def append_points(self, coordinates: NDArray[np.float32]) -> None:
        """Append multiple points with shape ``(N, 2)``."""
        if coordinates.size == 0:
            return
        if coordinates.ndim != 2 or coordinates.shape[1] != 2:
            raise ValueError("coordinates must have shape (N, 2)")

        normalized = np.ascontiguousarray(coordinates, dtype=np.float32)
        if self.points.size == 0:
            self.points = normalized
        else:
            self.points = np.vstack((self.points, normalized))

    def copy(self) -> Stroke:
        """Return a deep copy of the stroke."""
        return Stroke(
            stroke_id=self.stroke_id,
            points=self.points.copy(),
            color=self.color,
            width=self.width,
        )


@dataclass(slots=True)
class ActiveStroke:
    """Mutable stroke accumulator used while the user is drawing."""

    stroke: Stroke = field(default_factory=lambda: Stroke.create(color=(0, 0, 0), width=4))
    last_point: Point | None = None

    @classmethod
    def begin(
        cls,
        *,
        color: tuple[int, int, int],
        width: int,
    ) -> ActiveStroke:
        """Start a new active stroke."""
        return cls(stroke=Stroke.create(color=color, width=width))

    @property
    def point_count(self) -> int:
        """Return the number of recorded points."""
        return self.stroke.point_count

    def finalize(self) -> Stroke:
        """Return the committed stroke and reset the active accumulator."""
        committed = self.stroke.copy()
        self.stroke = Stroke.create(color=committed.color, width=committed.width)
        self.last_point = None
        return committed
