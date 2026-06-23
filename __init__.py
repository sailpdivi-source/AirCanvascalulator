"""Computer vision pipeline for camera capture and hand tracking."""

from __future__ import annotations

from vision.camera import (
    CameraCapture,
    CameraError,
    CameraFrame,
    CameraOpenError,
    CameraReadError,
    CameraState,
)
from vision.gesture_detector import GestureDetector, GestureFrame, GestureKind
from vision.hand_tracker import (
    HandTracker,
    HandTrackerError,
    HandTrackingResult,
    LandmarkPoint,
    TrackedHand,
)
from vision.smoother import EMASmoother, SmoothedPoint

__all__ = [
    "CameraCapture",
    "CameraError",
    "CameraFrame",
    "CameraOpenError",
    "CameraReadError",
    "CameraState",
    "EMASmoother",
    "GestureDetector",
    "GestureFrame",
    "GestureKind",
    "HandTracker",
    "HandTrackerError",
    "HandTrackingResult",
    "LandmarkPoint",
    "SmoothedPoint",
    "TrackedHand",
]
