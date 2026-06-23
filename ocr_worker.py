"""Background OCR and calculation worker running on a dedicated Qt thread."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from config import Settings
from core.events import (
    CalculationCompleted,
    OCRCompleted,
    OCRRequested,
    PipelineFailed,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class PipelineExecutionError(Exception):
    """Raised when OCR or calculation cannot be completed."""

    def __init__(self, request_id: str, message: str) -> None:
        self.request_id = request_id
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Successful OCR and calculation output from the worker pipeline."""

    ocr: OCRCompleted
    calculation: CalculationCompleted


class OCRWorker(QObject):
    """
    Run OCR and math evaluation off the GUI thread.

    The worker listens for :class:`OCRRequested` payloads and emits typed
    completion or failure events. Downstream OCR and math packages are loaded
    lazily at processing time so the core layer does not hard-depend on them
    at import time.
    """

    processing_started = pyqtSignal(str)
    ocr_completed = pyqtSignal(object)
    calculation_completed = pyqtSignal(object)
    pipeline_failed = pyqtSignal(object)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-pipeline")

    def shutdown(self) -> None:
        """Release background executor resources."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    @pyqtSlot(object)
    def process_request(self, request: OCRRequested) -> None:
        """
        Execute the OCR pipeline for ``request``.

        This slot is intended to run on the worker's dedicated ``QThread`` via
        a queued Qt connection.
        """
        self.processing_started.emit(request.request_id)
        logger.info("OCR processing started for request %s", request.request_id)

        try:
            self._validate_canvas(request.request_id, request.canvas_image)
            result = self._execute_with_timeout(request)
        except PipelineExecutionError as exc:
            logger.error("Pipeline failed for request %s: %s", exc.request_id, exc.message)
            failure = PipelineFailed(
                request_id=exc.request_id,
                error_message=exc.message,
            )
            self.pipeline_failed.emit(failure)
            return
        except Exception as exc:
            logger.exception("Unexpected pipeline failure for request %s", request.request_id)
            failure = PipelineFailed(
                request_id=request.request_id,
                error_message=f"Unexpected processing error: {exc}",
            )
            self.pipeline_failed.emit(failure)
            return

        self.ocr_completed.emit(result.ocr)
        self.calculation_completed.emit(result.calculation)
        logger.info(
            "OCR processing completed for request %s (engine=%s, success=%s)",
            request.request_id,
            result.ocr.engine_name,
            result.calculation.success,
        )

    def _execute_with_timeout(self, request: OCRRequested) -> PipelineResult:
        timeout = self._settings.ocr.timeout_seconds
        future = self._executor.submit(self._run_pipeline, request)
        try:
            outcome = future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise PipelineExecutionError(
                request.request_id,
                f"OCR processing exceeded the {timeout:.1f}s timeout.",
            ) from exc
        return outcome

    @staticmethod
    def _validate_canvas(request_id: str, canvas_image: NDArray[np.uint8]) -> None:
        if not isinstance(canvas_image, np.ndarray):
            raise PipelineExecutionError(request_id, "Canvas image must be a NumPy array.")
        if canvas_image.size == 0:
            raise PipelineExecutionError(request_id, "Canvas image is empty.")
        if canvas_image.ndim not in {2, 3}:
            raise PipelineExecutionError(request_id, "Canvas image must be 2D or 3D.")

    def _run_pipeline(self, request: OCRRequested) -> PipelineResult:
        request_id = request.request_id
        image = np.ascontiguousarray(request.canvas_image)

        ocr_outcome = self._run_ocr(request_id, image)
        calculation_outcome = self._run_calculation(request_id, ocr_outcome.recognized_text)

        return PipelineResult(ocr=ocr_outcome, calculation=calculation_outcome)

    def _run_ocr(self, request_id: str, image: NDArray[np.uint8]) -> OCRCompleted:
        try:
            from ocr.ocr_router import OCRRouter
        except ImportError as exc:
            raise PipelineExecutionError(
                request_id,
                "OCR module is not available. Implement the ocr package to enable evaluation.",
            ) from exc

        router = OCRRouter(self._settings)
        try:
            ocr_result = router.recognize(image)
        except Exception as exc:
            raise PipelineExecutionError(
                request_id,
                f"OCR recognition failed: {exc}",
            ) from exc

        recognized_text = str(getattr(ocr_result, "text", "")).strip()
        if not recognized_text:
            raise PipelineExecutionError(request_id, "OCR did not recognize any text.")

        return OCRCompleted(
            request_id=request_id,
            recognized_text=recognized_text,
            confidence=float(getattr(ocr_result, "confidence", 0.0)),
            engine_name=str(getattr(ocr_result, "engine_name", "unknown")),
            is_fallback=bool(getattr(ocr_result, "is_fallback", False)),
            fallback_attempted=bool(getattr(ocr_result, "fallback_attempted", False)),
            fallback_available=bool(getattr(ocr_result, "fallback_available", True)),
        )

    def _run_calculation(self, request_id: str, recognized_text: str) -> CalculationCompleted:
        try:
            from math.math_parser import MathParser
            from math.expression_evaluator import ExpressionEvaluator
        except ImportError as exc:
            return CalculationCompleted(
                request_id=request_id,
                expression=recognized_text,
                result=None,
                success=False,
                error_message=(
                    "Math module is not available. Implement the math package to enable calculation."
                ),
            )

        parser = MathParser()
        evaluator = ExpressionEvaluator()

        try:
            expression = parser.parse(recognized_text)
        except Exception as exc:
            return CalculationCompleted(
                request_id=request_id,
                expression=recognized_text,
                result=None,
                success=False,
                error_message=f"Expression parsing failed: {exc}",
            )

        try:
            raw_result = evaluator.evaluate(expression)
        except Exception as exc:
            return CalculationCompleted(
                request_id=request_id,
                expression=expression,
                result=None,
                success=False,
                error_message=f"Expression evaluation failed: {exc}",
            )

        return CalculationCompleted(
            request_id=request_id,
            expression=expression,
            result=self._format_result(raw_result),
            success=True,
            error_message=None,
        )

    @staticmethod
    def _format_result(value: Any) -> str:
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return f"{value:.6g}"
        return str(value)
