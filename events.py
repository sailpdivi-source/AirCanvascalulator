"""Typed application events and a Qt-based event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class StrokeCompleted:
    """Emitted when a drawing stroke has been committed to the canvas."""

    stroke_id: str
    point_count: int
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class OCRRequested:
    """Emitted when the user requests OCR evaluation of the current canvas."""

    request_id: str
    canvas_image: NDArray[np.uint8]
    timestamp: datetime = field(default_factory=_utc_now)

    @staticmethod
    def create(canvas_image: NDArray[np.uint8]) -> OCRRequested:
        """Build a new OCR request with a generated identifier."""
        return OCRRequested(
            request_id=str(uuid4()),
            canvas_image=canvas_image,
        )


@dataclass(frozen=True, slots=True)
class OCRCompleted:
    """Emitted when OCR recognition finishes for a request."""

    request_id: str
    recognized_text: str
    confidence: float
    engine_name: str
    is_fallback: bool
    fallback_attempted: bool
    fallback_available: bool
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class CalculationCompleted:
    """Emitted when expression parsing and evaluation finishes."""

    request_id: str
    expression: str
    result: str | None
    success: bool
    error_message: str | None
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class HistoryUpdated:
    """Emitted when a history entry has been recorded or refreshed."""

    entry_id: str
    recognized_text: str
    expression: str
    result: str | None
    ocr_engine: str
    ocr_confidence: float
    is_fallback: bool
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class PipelineFailed:
    """Emitted when the OCR or calculation pipeline fails irrecoverably."""

    request_id: str
    error_message: str
    timestamp: datetime = field(default_factory=_utc_now)


class EventBus(QObject):
    """
    Central publish/subscribe hub for application-level events.

    Signals carry immutable dataclass payloads. Receivers should treat each
    payload as read-only.
    """

    stroke_completed = pyqtSignal(object)
    ocr_requested = pyqtSignal(object)
    ocr_completed = pyqtSignal(object)
    calculation_completed = pyqtSignal(object)
    history_updated = pyqtSignal(object)
    pipeline_failed = pyqtSignal(object)

    def publish_stroke_completed(self, event: StrokeCompleted) -> None:
        """Publish a stroke-completed event."""
        self.stroke_completed.emit(event)

    def publish_ocr_requested(self, event: OCRRequested) -> None:
        """Publish an OCR-requested event."""
        self.ocr_requested.emit(event)

    def publish_ocr_completed(self, event: OCRCompleted) -> None:
        """Publish an OCR-completed event."""
        self.ocr_completed.emit(event)

    def publish_calculation_completed(self, event: CalculationCompleted) -> None:
        """Publish a calculation-completed event."""
        self.calculation_completed.emit(event)

    def publish_history_updated(self, event: HistoryUpdated) -> None:
        """Publish a history-updated event."""
        self.history_updated.emit(event)

    def publish_pipeline_failed(self, event: PipelineFailed) -> None:
        """Publish a pipeline-failed event."""
        self.pipeline_failed.emit(event)
