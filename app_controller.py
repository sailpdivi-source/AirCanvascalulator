"""Central application orchestrator for AirCanvas Calculator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from config import Settings
from core.events import (
    CalculationCompleted,
    EventBus,
    HistoryUpdated,
    OCRCompleted,
    OCRRequested,
    PipelineFailed,
    StrokeCompleted,
)
from core.ocr_worker import OCRWorker
from core.state import AppState, InvalidStateTransition, StateMachine

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class AppController(QObject):
    """
    Coordinate application state, events, and background OCR processing.

    The controller is the only module that should wire together the event bus,
    state machine, and OCR worker thread. UI and vision layers interact with the
    application exclusively through the public methods and Qt signals exposed
    here.
    """

    state_changed = pyqtSignal(AppState, AppState)
    error_occurred = pyqtSignal(str)

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._event_bus = EventBus(self)
        self._state_machine = StateMachine(
            initial=AppState.IDLE,
            on_transition=self._on_state_transition,
        )
        self._active_request_id: str | None = None
        self._pending_ocr: dict[str, OCRCompleted] = {}

        self._ocr_thread = QThread(self)
        self._ocr_thread.setObjectName("ocr-worker-thread")
        self._ocr_worker = OCRWorker(settings)
        self._ocr_worker.moveToThread(self._ocr_thread)

        self._connect_worker_signals()

    @property
    def settings(self) -> Settings:
        """Return the application settings snapshot."""
        return self._settings

    @property
    def event_bus(self) -> EventBus:
        """Return the shared application event bus."""
        return self._event_bus

    @property
    def state(self) -> AppState:
        """Return the current application state."""
        return self._state_machine.state

    def start(self) -> None:
        """Start background workers and enter the idle state."""
        if not self._ocr_thread.isRunning():
            self._ocr_thread.start()
            logger.info("OCR worker thread started.")

    def stop(self) -> None:
        """Stop background workers and release resources."""
        self._ocr_worker.shutdown()
        self._ocr_thread.quit()
        if not self._ocr_thread.wait(3000):
            logger.warning("OCR worker thread did not stop within the timeout.")
            self._ocr_thread.terminate()
            self._ocr_thread.wait(1000)
        logger.info("OCR worker thread stopped.")

    def begin_drawing(self) -> None:
        """
        Transition to the drawing state.

        Raises:
            InvalidStateTransition: If drawing cannot be started from the
                current state.
        """
        self._transition(AppState.DRAWING)
        logger.debug("Drawing started.")

    def complete_stroke(self, point_count: int) -> StrokeCompleted:
        """
        Finalize the active stroke and return to idle.

        Args:
            point_count: Number of points recorded in the completed stroke.

        Returns:
            The stroke-completed event published on the event bus.

        Raises:
            InvalidStateTransition: If not currently in the drawing state.
            ValueError: If ``point_count`` is not positive.
        """
        if point_count <= 0:
            raise ValueError("point_count must be greater than zero.")

        self._transition(AppState.IDLE)

        event = StrokeCompleted(
            stroke_id=str(uuid4()),
            point_count=point_count,
        )
        self._event_bus.publish_stroke_completed(event)
        logger.debug("Stroke completed with %d points.", point_count)
        return event

    def request_evaluation(self, canvas_image: NDArray[np.uint8]) -> str:
        """
        Request OCR evaluation of the current canvas snapshot.

        Args:
            canvas_image: Canvas raster as a height x width or height x width x 3
                array of unsigned 8-bit values.

        Returns:
            The generated OCR request identifier.

        Raises:
            InvalidStateTransition: If evaluation is not allowed in the current
                state.
            ValueError: If the canvas image is invalid.
        """
        if not isinstance(canvas_image, np.ndarray):
            raise ValueError("canvas_image must be a NumPy ndarray.")
        if canvas_image.size == 0:
            raise ValueError("canvas_image must not be empty.")

        self._transition(AppState.PROCESSING)

        request = OCRRequested.create(canvas_image=np.ascontiguousarray(canvas_image))
        self._active_request_id = request.request_id
        self._event_bus.publish_ocr_requested(request)
        logger.info("OCR evaluation requested (%s).", request.request_id)
        return request.request_id

    def clear_error(self) -> None:
        """Clear the error state and return to idle."""
        if self._state_machine.is_error():
            self._transition(AppState.IDLE)
            self._active_request_id = None
            self._pending_ocr.clear()
            logger.info("Error state cleared.")

    def can_evaluate(self) -> bool:
        """Return whether OCR evaluation is permitted in the current state."""
        return self._state_machine.can_transition(AppState.PROCESSING)

    def can_draw(self) -> bool:
        """Return whether drawing can be started in the current state."""
        return self._state_machine.can_transition(AppState.DRAWING)

    def _connect_worker_signals(self) -> None:
        self._event_bus.ocr_requested.connect(
            self._ocr_worker.process_request,
            Qt.ConnectionType.QueuedConnection,
        )
        self._ocr_worker.processing_started.connect(self._on_processing_started)
        self._ocr_worker.ocr_completed.connect(self._on_ocr_completed)
        self._ocr_worker.calculation_completed.connect(self._on_calculation_completed)
        self._ocr_worker.pipeline_failed.connect(self._on_pipeline_failed)

    def _on_state_transition(self, previous: AppState, current: AppState) -> None:
        logger.debug("State transition: %s -> %s", previous.name, current.name)
        self.state_changed.emit(previous, current)

    def _transition(self, target: AppState) -> None:
        try:
            self._state_machine.transition_to(target)
        except InvalidStateTransition:
            logger.exception(
                "Rejected transition to %s from %s.",
                target.name,
                self._state_machine.state.name,
            )
            raise

    def _on_processing_started(self, request_id: str) -> None:
        logger.debug("Processing started for request %s.", request_id)

    def _on_ocr_completed(self, event: OCRCompleted) -> None:
        self._pending_ocr[event.request_id] = event
        self._event_bus.publish_ocr_completed(event)

    def _on_calculation_completed(self, event: CalculationCompleted) -> None:
        self._event_bus.publish_calculation_completed(event)
        self._finalize_processing(event)

    def _on_pipeline_failed(self, event: PipelineFailed) -> None:
        self._event_bus.publish_pipeline_failed(event)
        self.error_occurred.emit(event.error_message)

        if self._state_machine.is_processing():
            self._transition(AppState.ERROR)
        elif self._state_machine.can_transition(AppState.ERROR):
            self._transition(AppState.ERROR)

        self._active_request_id = None
        self._pending_ocr.pop(event.request_id, None)
        logger.error(
            "Pipeline failed for request %s: %s",
            event.request_id,
            event.error_message,
        )

    def _finalize_processing(self, calculation: CalculationCompleted) -> None:
        if not self._state_machine.is_processing():
            logger.warning(
                "Received calculation completion while not processing (request %s).",
                calculation.request_id,
            )
            return

        ocr_event = self._pending_ocr.pop(calculation.request_id, None)
        if ocr_event is not None:
            history_event = self._record_history(ocr_event, calculation)
            if history_event is not None:
                self._event_bus.publish_history_updated(history_event)

        if calculation.success:
            self._transition(AppState.IDLE)
            self._active_request_id = None
            logger.info(
                "Calculation succeeded for request %s: %s = %s",
                calculation.request_id,
                calculation.expression,
                calculation.result,
            )
            return

        message = calculation.error_message or "Calculation failed."
        self.error_occurred.emit(message)
        self._transition(AppState.ERROR)
        self._active_request_id = None
        logger.error(
            "Calculation failed for request %s: %s",
            calculation.request_id,
            message,
        )

    def _record_history(
        self,
        ocr_event: OCRCompleted,
        calculation: CalculationCompleted,
    ) -> HistoryUpdated | None:
        history_event = HistoryUpdated(
            entry_id=str(uuid4()),
            recognized_text=ocr_event.recognized_text,
            expression=calculation.expression,
            result=calculation.result,
            ocr_engine=ocr_event.engine_name,
            ocr_confidence=ocr_event.confidence,
            is_fallback=ocr_event.is_fallback,
        )

        try:
            from history.history_manager import HistoryManager
        except ImportError:
            logger.warning(
                "History module unavailable; emitting in-memory history event only."
            )
            return history_event

        try:
            manager = HistoryManager(self._settings)
            stored = manager.add_from_pipeline(ocr_event, calculation)
            return HistoryUpdated(
                entry_id=stored.entry_id,
                recognized_text=stored.recognized_text,
                expression=stored.expression,
                result=stored.result,
                ocr_engine=stored.ocr_engine,
                ocr_confidence=stored.ocr_confidence,
                is_fallback=stored.is_fallback,
                timestamp=stored.timestamp,
            )
        except Exception as exc:
            logger.error("Failed to persist history entry: %s", exc)
            return history_event
