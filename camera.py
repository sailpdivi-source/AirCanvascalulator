"""OpenCV webcam capture with automatic reconnect handling."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from config import CameraSettings

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_FAILURES: Final[int] = 5
_RECONNECT_DELAY_SECONDS: Final[float] = 0.5
_MAX_RECONNECT_ATTEMPTS: Final[int] = 5


class CameraState(Enum):
    """Lifecycle state of the camera device."""

    CLOSED = auto()
    OPEN = auto()
    RECONNECTING = auto()


class CameraError(Exception):
    """Base exception for camera failures."""


class CameraOpenError(CameraError):
    """Raised when the camera cannot be opened."""


class CameraReadError(CameraError):
    """Raised when frame capture fails persistently."""


@dataclass(frozen=True, slots=True)
class CameraFrame:
    """A single captured camera frame with timing metadata."""

    image: NDArray[np.uint8]
    timestamp_ms: int
    frame_number: int
    mirrored: bool


class CameraCapture:
    """
    Capture frames from a webcam using OpenCV.

    The capture automatically attempts to reconnect when consecutive read
    failures occur, which commonly happens when the device is unplugged or
    locked by another process.
    """

    def __init__(self, settings: CameraSettings) -> None:
        self._settings = settings
        self._capture: cv2.VideoCapture | None = None
        self._state = CameraState.CLOSED
        self._frame_number = 0
        self._start_monotonic_ms = int(time.monotonic() * 1000)
        self._consecutive_failures = 0

    @property
    def state(self) -> CameraState:
        """Return the current camera lifecycle state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Return whether the underlying capture device is open."""
        return self._capture is not None and self._capture.isOpened()

    @property
    def frame_number(self) -> int:
        """Return the total number of successfully captured frames."""
        return self._frame_number

    def open(self) -> None:
        """Open the configured camera device."""
        if self.is_open:
            return
        self._open_capture()
        self._state = CameraState.OPEN
        logger.info(
            "Camera opened (index=%d, %dx%d @ %dfps).",
            self._settings.index,
            self._settings.width,
            self._settings.height,
            self._settings.fps,
        )

    def close(self) -> None:
        """Release the camera device."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._state = CameraState.CLOSED
        self._consecutive_failures = 0
        logger.info("Camera closed.")

    def read(self) -> CameraFrame:
        """
        Read the next frame from the camera.

        Returns:
            A :class:`CameraFrame` containing a BGR image.

        Raises:
            CameraOpenError: If the camera is not open.
            CameraReadError: If frame capture fails after reconnect attempts.
        """
        if not self.is_open:
            raise CameraOpenError("Camera is not open. Call open() first.")

        success, frame = self._capture.read()  # type: ignore[union-attr]
        if not success or frame is None:
            self._consecutive_failures += 1
            logger.warning(
                "Camera read failed (%d consecutive failure(s)).",
                self._consecutive_failures,
            )
            if self._consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                self._attempt_reconnect()
                success, frame = self._capture.read()  # type: ignore[union-attr]
                if not success or frame is None:
                    raise CameraReadError(
                        "Unable to read a frame from the camera after reconnect."
                    )
            else:
                raise CameraReadError("Unable to read a frame from the camera.")

        self._consecutive_failures = 0
        self._frame_number += 1

        output = frame
        mirrored = False
        if self._settings.mirror:
            output = cv2.flip(frame, 1)
            mirrored = True

        timestamp_ms = int(time.monotonic() * 1000) - self._start_monotonic_ms
        return CameraFrame(
            image=output,
            timestamp_ms=timestamp_ms,
            frame_number=self._frame_number,
            mirrored=mirrored,
        )

    def _open_capture(self) -> None:
        if sys.platform.startswith("win"):
            self._capture = cv2.VideoCapture(self._settings.index, cv2.CAP_DSHOW)
        else:
            self._capture = cv2.VideoCapture(self._settings.index)

        if not self._capture.isOpened():
            self._capture.release()
            self._capture = cv2.VideoCapture(self._settings.index)
        if not self._capture.isOpened():
            raise CameraOpenError(
                f"Failed to open camera at index {self._settings.index}."
            )

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._settings.width))
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._settings.height))
        self._capture.set(cv2.CAP_PROP_FPS, float(self._settings.fps))
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, float(self._settings.buffer_size))

    def _attempt_reconnect(self) -> None:
        self._state = CameraState.RECONNECTING
        logger.warning("Attempting camera reconnect.")

        if self._capture is not None:
            self._capture.release()
            self._capture = None

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            time.sleep(_RECONNECT_DELAY_SECONDS)
            try:
                self._open_capture()
                self._state = CameraState.OPEN
                self._consecutive_failures = 0
                logger.info("Camera reconnect succeeded on attempt %d.", attempt)
                return
            except CameraOpenError as exc:
                last_error = exc
                logger.error(
                    "Camera reconnect attempt %d failed: %s",
                    attempt,
                    exc,
                )

        self._state = CameraState.CLOSED
        message = "Camera reconnect failed after maximum attempts."
        if last_error is not None:
            raise CameraOpenError(f"{message} Last error: {last_error}") from last_error
        raise CameraOpenError(message)

    def __enter__(self) -> CameraCapture:
        self.open()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
