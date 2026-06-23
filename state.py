"""Application state definitions and transition management."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from typing import Final

TransitionCallback = Callable[["AppState", "AppState"], None]


class AppState(Enum):
    """High-level application states exposed to the UI and orchestration layer."""

    IDLE = auto()
    DRAWING = auto()
    PROCESSING = auto()
    ERROR = auto()


class InvalidStateTransition(Exception):
    """Raised when a state transition is not permitted by the state machine."""

    def __init__(self, current: AppState, target: AppState) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid state transition: {current.name} -> {target.name}"
        )


_ALLOWED_TRANSITIONS: Final[dict[AppState, frozenset[AppState]]] = {
    AppState.IDLE: frozenset({AppState.DRAWING, AppState.PROCESSING, AppState.ERROR}),
    AppState.DRAWING: frozenset({AppState.IDLE, AppState.ERROR}),
    AppState.PROCESSING: frozenset({AppState.IDLE, AppState.ERROR}),
    AppState.ERROR: frozenset({AppState.IDLE}),
}


class StateMachine:
    """
    Validates and records ``AppState`` transitions for the application core.

    The state machine is intentionally free of Qt dependencies so it can be
    tested independently of the GUI event loop.
    """

    def __init__(
        self,
        initial: AppState = AppState.IDLE,
        on_transition: TransitionCallback | None = None,
    ) -> None:
        self._state = initial
        self._on_transition = on_transition

    @property
    def state(self) -> AppState:
        """Return the current application state."""
        return self._state

    def can_transition(self, target: AppState) -> bool:
        """Return whether ``target`` is reachable from the current state."""
        return target in _ALLOWED_TRANSITIONS[self._state]

    def transition_to(self, target: AppState) -> AppState:
        """
        Transition to ``target`` if permitted.

        Returns:
            The previous state before the transition.

        Raises:
            InvalidStateTransition: If the transition is not allowed.
        """
        if not self.can_transition(target):
            raise InvalidStateTransition(self._state, target)

        previous = self._state
        self._state = target

        if self._on_transition is not None:
            self._on_transition(previous, target)

        return previous

    def reset_to_idle(self) -> AppState:
        """Force-return to ``IDLE`` from ``ERROR`` or after processing."""
        if self._state is AppState.ERROR:
            return self.transition_to(AppState.IDLE)
        if self._state is AppState.PROCESSING:
            return self.transition_to(AppState.IDLE)
        return self._state

    def is_idle(self) -> bool:
        """Return whether the application is in the idle state."""
        return self._state is AppState.IDLE

    def is_drawing(self) -> bool:
        """Return whether the application is in the drawing state."""
        return self._state is AppState.DRAWING

    def is_processing(self) -> bool:
        """Return whether OCR processing is in progress."""
        return self._state is AppState.PROCESSING

    def is_error(self) -> bool:
        """Return whether the application is in the error state."""
        return self._state is AppState.ERROR
