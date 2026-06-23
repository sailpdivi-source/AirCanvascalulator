"""MediaPipe hand landmark tracking using the Tasks API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

import numpy as np
from mediapipe.tasks.python.core import base_options as mp_base_options
from mediapipe.tasks.python.vision import hand_landmarker as mp_hand_landmarker
from mediapipe.tasks.python.vision.core import image as mp_image
from mediapipe.tasks.python.vision.core import vision_task_running_mode as mp_running_mode
from numpy.typing import NDArray

from config import (
    DRAW_CURSOR_LANDMARK,
    PINCH_LANDMARK_A,
    PINCH_LANDMARK_B,
    VisionSettings,
)

logger = logging.getLogger(__name__)

_NUM_LANDMARKS: Final[int] = 21


class HandTrackerError(Exception):
    """Raised when hand tracking cannot be initialized or executed."""


@dataclass(frozen=True, slots=True)
class LandmarkPoint:
    """A single hand landmark in normalized image coordinates."""

    x: float
    y: float
    z: float
    visibility: float


@dataclass(frozen=True, slots=True)
class TrackedHand:
    """Tracked hand landmarks and derived fingertip positions."""

    landmarks: tuple[LandmarkPoint, ...]
    handedness: str
    index_tip: LandmarkPoint
    thumb_tip: LandmarkPoint

    @property
    def cursor_landmark(self) -> LandmarkPoint:
        """Return the drawing cursor landmark (index fingertip)."""
        return self.index_tip


@dataclass(frozen=True, slots=True)
class HandTrackingResult:
    """Result of hand landmark detection for a single video frame."""

    hands: tuple[TrackedHand, ...]
    timestamp_ms: int

    @property
    def detected(self) -> bool:
        """Return whether at least one hand was detected."""
        return len(self.hands) > 0

    @property
    def primary_hand(self) -> TrackedHand | None:
        """Return the first detected hand, if any."""
        if not self.hands:
            return None
        return self.hands[0]


class HandTracker:
    """
    Track hand landmarks using the MediaPipe Hand Landmarker Tasks API.

    The tracker operates in ``VIDEO`` running mode and expects monotonically
    increasing frame timestamps in milliseconds.
    """

    def __init__(self, settings: VisionSettings) -> None:
        self._settings = settings
        self._model_path = Path(settings.hand_model_path)
        self._landmarker: mp_hand_landmarker.HandLandmarker | None = None
        self._last_timestamp_ms = -1

    @property
    def model_path(self) -> Path:
        """Return the configured hand landmarker model path."""
        return self._model_path

    def initialize(self) -> None:
        """Create the MediaPipe hand landmarker from the configured model."""
        if self._landmarker is not None:
            return

        if not self._model_path.is_file():
            raise HandTrackerError(
                f"Hand landmarker model not found at '{self._model_path}'."
            )

        options = mp_hand_landmarker.HandLandmarkerOptions(
            base_options=mp_base_options.BaseOptions(
                model_asset_path=str(self._model_path),
            ),
            running_mode=mp_running_mode.VisionTaskRunningMode.VIDEO,
            num_hands=self._settings.num_hands,
            min_hand_detection_confidence=self._settings.min_hand_detection_confidence,
            min_hand_presence_confidence=self._settings.min_hand_presence_confidence,
            min_tracking_confidence=self._settings.min_tracking_confidence,
        )

        try:
            self._landmarker = mp_hand_landmarker.HandLandmarker.create_from_options(
                options
            )
        except Exception as exc:
            raise HandTrackerError(
                f"Failed to initialize HandLandmarker: {exc}"
            ) from exc

        logger.info("Hand landmarker initialized from '%s'.", self._model_path)

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self._last_timestamp_ms = -1
        logger.info("Hand landmarker closed.")

    def reset(self) -> None:
        """Reset timestamp tracking for a new video stream."""
        self._last_timestamp_ms = -1
        logger.debug("Hand tracker timestamp state reset.")

    def process_frame(
        self,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> HandTrackingResult:
        """
        Detect hand landmarks in a BGR video frame.

        Args:
            frame_bgr: OpenCV BGR image array.
            timestamp_ms: Monotonically increasing timestamp in milliseconds.

        Returns:
            Parsed :class:`HandTrackingResult`.

        Raises:
            HandTrackerError: If the tracker is not initialized or processing fails.
        """
        if self._landmarker is None:
            raise HandTrackerError("Hand tracker is not initialized. Call initialize().")

        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        rgb_frame = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        mp_frame = mp_image.Image(
            image_format=mp_image.ImageFormat.SRGB,
            data=rgb_frame,
        )

        try:
            detection = self._landmarker.detect_for_video(mp_frame, timestamp_ms)
        except Exception as exc:
            raise HandTrackerError(f"Hand landmark detection failed: {exc}") from exc

        hands = self._parse_hands(detection)
        return HandTrackingResult(hands=hands, timestamp_ms=timestamp_ms)

    def _parse_hands(
        self,
        detection: mp_hand_landmarker.HandLandmarkerResult,
    ) -> tuple[TrackedHand, ...]:
        if not detection.hand_landmarks:
            return ()

        tracked: list[TrackedHand] = []
        handedness_labels = self._extract_handedness(detection)

        for index, landmark_list in enumerate(detection.hand_landmarks):
            points = self._to_landmark_points(landmark_list)
            if len(points) < _NUM_LANDMARKS:
                logger.debug("Skipping hand with insufficient landmarks.")
                continue

            label = handedness_labels[index] if index < len(handedness_labels) else "Unknown"
            tracked.append(
                TrackedHand(
                    landmarks=points,
                    handedness=label,
                    index_tip=points[DRAW_CURSOR_LANDMARK],
                    thumb_tip=points[PINCH_LANDMARK_A],
                )
            )

        return tuple(tracked)

    @staticmethod
    def _extract_handedness(
        detection: mp_hand_landmarker.HandLandmarkerResult,
    ) -> list[str]:
        labels: list[str] = []
        if not detection.handedness:
            return labels
        for categories in detection.handedness:
            if categories and categories[0].category_name:
                labels.append(categories[0].category_name)
            else:
                labels.append("Unknown")
        return labels

    @staticmethod
    def _to_landmark_points(
        landmark_list: Sequence[object],
    ) -> tuple[LandmarkPoint, ...]:
        points: list[LandmarkPoint] = []
        for item in landmark_list:
            visibility = float(getattr(item, "visibility", 1.0) or 1.0)
            points.append(
                LandmarkPoint(
                    x=float(item.x),
                    y=float(item.y),
                    z=float(item.z),
                    visibility=visibility,
                )
            )
        return tuple(points)

    def pinch_distance(self, hand: TrackedHand) -> float:
        """
        Compute normalized Euclidean distance between pinch landmarks.

        Uses the thumb tip and index fingertip defined in configuration constants.
        """
        thumb = hand.landmarks[PINCH_LANDMARK_A]
        index = hand.landmarks[PINCH_LANDMARK_B]
        return float(
            np.hypot(thumb.x - index.x, thumb.y - index.y)
        )

    def __enter__(self) -> HandTracker:
        self.initialize()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
