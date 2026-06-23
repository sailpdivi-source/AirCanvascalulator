"""Gesture detection from tracked hand landmarks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from config import VisionSettings
from config.constants import (
    INDEX_FINGER_MCP,
    INDEX_FINGER_TIP,
    MIDDLE_FINGER_MCP,
    MIDDLE_FINGER_TIP,
    PALM_CLEAR_HOLD_MS,
    PINKY_MCP,
    PINKY_TIP,
    RING_FINGER_MCP,
    RING_FINGER_TIP,
)
from vision.hand_tracker import HandTrackingResult, LandmarkPoint, TrackedHand

logger = logging.getLogger(__name__)


class GestureKind(Enum):
    """High-level gesture classification for a frame."""

    NONE = auto()
    HOVER = auto()
    PINCH_DRAW = auto()
    OPEN_PALM_CLEAR = auto()


@dataclass(frozen=True, slots=True)
class GestureFrame:
    """Gesture interpretation for a single processed frame."""

    kind: GestureKind
    hand_detected: bool
    is_drawing: bool
    is_pinching: bool
    clear_palm_hold_active: bool
    cursor_normalized_x: float
    cursor_normalized_y: float
    pinch_distance: float
    handedness: str | None


class GestureDetector:
    """
    Detect pinch-to-draw and open-palm clear gestures from hand landmarks.

    Pinch detection uses hysteresis thresholds and frame debouncing configured
    via :class:`VisionSettings`. Open-palm clear requires all four fingers to
    be extended and held for the configured duration.
    """

    def __init__(self, settings: VisionSettings) -> None:
        self._settings = settings
        self._pinch_active = False
        self._pinch_on_counter = 0
        self._pinch_off_counter = 0
        self._clear_hold_started_ms: int | None = None
        self._last_hand_seen_ms: int | None = None

    def reset(self) -> None:
        """Reset internal gesture tracking state."""
        self._pinch_active = False
        self._pinch_on_counter = 0
        self._pinch_off_counter = 0
        self._clear_hold_started_ms = None
        self._last_hand_seen_ms = None
        logger.debug("Gesture detector state reset.")

    def process(
        self,
        tracking: HandTrackingResult,
        *,
        monotonic_ms: int | None = None,
    ) -> GestureFrame:
        """
        Classify the gesture present in ``tracking``.

        Args:
            tracking: Hand tracking output for the current frame.
            monotonic_ms: Optional monotonic timestamp in milliseconds used for
                hand-loss and palm-hold timing. Defaults to ``time.monotonic()``.

        Returns:
            A :class:`GestureFrame` describing the classified gesture.
        """
        now_ms = (
            monotonic_ms
            if monotonic_ms is not None
            else int(time.monotonic() * 1000)
        )

        hand = tracking.primary_hand
        if hand is None:
            return self._handle_hand_lost(now_ms)

        self._last_hand_seen_ms = now_ms
        pinch_distance = self._compute_pinch_distance(hand)
        self._update_pinch_state(pinch_distance)

        open_palm = self._is_open_palm(hand)
        clear_hold_active = self._update_clear_hold(open_palm, now_ms)

        if clear_hold_active:
            kind = GestureKind.OPEN_PALM_CLEAR
        elif self._pinch_active:
            kind = GestureKind.PINCH_DRAW
        else:
            kind = GestureKind.HOVER

        cursor = hand.cursor_landmark
        return GestureFrame(
            kind=kind,
            hand_detected=True,
            is_drawing=self._pinch_active,
            is_pinching=self._pinch_active,
            clear_palm_hold_active=clear_hold_active,
            cursor_normalized_x=cursor.x,
            cursor_normalized_y=cursor.y,
            pinch_distance=pinch_distance,
            handedness=hand.handedness,
        )

    def _handle_hand_lost(self, now_ms: int) -> GestureFrame:
        if self._last_hand_seen_ms is not None:
            elapsed = now_ms - self._last_hand_seen_ms
            if elapsed > self._settings.hand_lost_timeout_ms:
                self._pinch_active = False
                self._pinch_on_counter = 0
                self._pinch_off_counter = 0
                self._clear_hold_started_ms = None

        return GestureFrame(
            kind=GestureKind.NONE,
            hand_detected=False,
            is_drawing=False,
            is_pinching=False,
            clear_palm_hold_active=False,
            cursor_normalized_x=0.0,
            cursor_normalized_y=0.0,
            pinch_distance=1.0,
            handedness=None,
        )

    def _compute_pinch_distance(self, hand: TrackedHand) -> float:
        thumb = hand.thumb_tip
        index = hand.index_tip
        return float(np.hypot(thumb.x - index.x, thumb.y - index.y))

    def _update_pinch_state(self, pinch_distance: float) -> None:
        debounce = self._settings.gesture_debounce_frames

        if not self._pinch_active:
            if pinch_distance <= self._settings.pinch_threshold:
                self._pinch_on_counter += 1
                self._pinch_off_counter = 0
                if self._pinch_on_counter >= debounce:
                    self._pinch_active = True
                    self._pinch_on_counter = 0
                    logger.debug("Pinch draw gesture activated.")
            else:
                self._pinch_on_counter = 0
            return

        if pinch_distance >= self._settings.pinch_release_threshold:
            self._pinch_off_counter += 1
            self._pinch_on_counter = 0
            if self._pinch_off_counter >= debounce:
                self._pinch_active = False
                self._pinch_off_counter = 0
                logger.debug("Pinch draw gesture released.")
        else:
            self._pinch_off_counter = 0

    def _update_clear_hold(self, open_palm: bool, now_ms: int) -> bool:
        if not open_palm:
            self._clear_hold_started_ms = None
            return False

        if self._clear_hold_started_ms is None:
            self._clear_hold_started_ms = now_ms
            return False

        elapsed = now_ms - self._clear_hold_started_ms
        return elapsed >= PALM_CLEAR_HOLD_MS

    @staticmethod
    def _is_finger_extended(
        landmarks: tuple[LandmarkPoint, ...],
        tip_index: int,
        mcp_index: int,
    ) -> bool:
        tip = landmarks[tip_index]
        mcp = landmarks[mcp_index]
        return tip.y < mcp.y and float(np.hypot(tip.x - mcp.x, tip.y - mcp.y)) > 0.06

    def _is_open_palm(self, hand: TrackedHand) -> bool:
        landmarks = hand.landmarks
        index_extended = self._is_finger_extended(
            landmarks, INDEX_FINGER_TIP, INDEX_FINGER_MCP
        )
        middle_extended = self._is_finger_extended(
            landmarks, MIDDLE_FINGER_TIP, MIDDLE_FINGER_MCP
        )
        ring_extended = self._is_finger_extended(
            landmarks, RING_FINGER_TIP, RING_FINGER_MCP
        )
        pinky_extended = self._is_finger_extended(
            landmarks, PINKY_TIP, PINKY_MCP
        )
        return index_extended and middle_extended and ring_extended and pinky_extended
