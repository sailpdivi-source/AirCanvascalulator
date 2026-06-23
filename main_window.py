"""Primary application window."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config import Settings
from core.app_controller import AppController
from core.state import AppState

logger = logging.getLogger(__name__)

_STATE_LABELS: dict[AppState, str] = {
    AppState.IDLE: "Ready",
    AppState.DRAWING: "Drawing",
    AppState.PROCESSING: "Processing",
    AppState.ERROR: "Error",
}


class MainWindow(QMainWindow):
    """
    Main application shell for AirCanvas Calculator.

    Provides the central workspace, menu bar, and status bar. Vision, drawing,
    and OCR widgets will be integrated into this window in later phases.
    """

    def __init__(self, controller: AppController, settings: Settings) -> None:
        super().__init__()
        self._controller = controller
        self._settings = settings

        self._state_label = QLabel()
        self._message_label = QLabel()
        self._status_state_label = QLabel()
        self._status_message_label = QLabel()

        self._configure_window()
        self._build_menu_bar()
        self._build_central_widget()
        self._build_status_bar()
        self._connect_controller_signals()
        self._update_state_display(self._controller.state)

        logger.info("Main window initialized.")

    @property
    def controller(self) -> AppController:
        """Return the application controller bound to this window."""
        return self._controller

    @property
    def settings(self) -> Settings:
        """Return the application settings snapshot."""
        return self._settings

    def _configure_window(self) -> None:
        title = f"{self._settings.app_name} v{self._settings.app_version}"
        self.setWindowTitle(title)
        self.resize(self._settings.ui.window_width, self._settings.ui.window_height)
        self.setMinimumSize(960, 600)

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Close the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = self.menuBar().addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("Show application information")
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _build_central_widget(self) -> None:
        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        title_label = QLabel(self._settings.app_name)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_label = QLabel("Gesture-controlled air canvas calculator")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #64748b;")

        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_font = QFont()
        state_font.setPointSize(14)
        state_font.setBold(True)
        self._state_label.setFont(state_font)

        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setText(
            "Camera, canvas, and evaluation panels will appear here in the next UI phase. "
            "The application core is running and ready for integration."
        )
        self._message_label.setStyleSheet("color: #334155;")

        root_layout.addStretch(1)
        root_layout.addWidget(title_label)
        root_layout.addWidget(subtitle_label)
        root_layout.addSpacing(12)
        root_layout.addWidget(self._state_label)
        root_layout.addWidget(self._message_label)
        root_layout.addStretch(2)

        central.setLayout(root_layout)
        self.setCentralWidget(central)

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.setSizeGripEnabled(True)
        self.setStatusBar(status_bar)

        self._status_state_label.setObjectName("statusStateLabel")
        self._status_message_label.setObjectName("statusMessageLabel")
        self._status_message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        status_bar.addWidget(self._status_state_label, stretch=0)
        status_bar.addWidget(self._create_status_separator(), stretch=0)
        status_bar.addWidget(self._status_message_label, stretch=1)

        self._status_message_label.setText("Application started")

    @staticmethod
    def _create_status_separator() -> QLabel:
        separator = QLabel("|")
        separator.setStyleSheet("color: #94a3b8; padding: 0 6px;")
        return separator

    def _connect_controller_signals(self) -> None:
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.error_occurred.connect(self._on_error_occurred)

    def _on_state_changed(self, previous: AppState, current: AppState) -> None:
        logger.debug("UI observed state change: %s -> %s", previous.name, current.name)
        self._update_state_display(current)

        if current is AppState.PROCESSING:
            self._set_status_message("Running OCR evaluation...")
        elif current is AppState.IDLE:
            self._set_status_message("Ready")
        elif current is AppState.DRAWING:
            self._set_status_message("Drawing in progress")
        elif current is AppState.ERROR:
            self._set_status_message("An error occurred")

    def _on_error_occurred(self, message: str) -> None:
        logger.error("UI received error: %s", message)
        self._set_status_message(message)
        self._message_label.setText(message)
        self._message_label.setStyleSheet("color: #dc2626;")

    def _update_state_display(self, state: AppState) -> None:
        label = _STATE_LABELS.get(state, state.name.title())
        self._state_label.setText(f"State: {label}")
        self._status_state_label.setText(f"State: {label}")

        if state is AppState.ERROR:
            self._state_label.setStyleSheet("color: #dc2626;")
        elif state is AppState.PROCESSING:
            self._state_label.setStyleSheet("color: #d97706;")
        elif state is AppState.DRAWING:
            self._state_label.setStyleSheet("color: #2563eb;")
        else:
            self._state_label.setStyleSheet("color: #16a34a;")

    def _set_status_message(self, message: str) -> None:
        self._status_message_label.setText(message)

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            f"About {self._settings.app_name}",
            (
                f"<h3>{self._settings.app_name}</h3>"
                f"<p>Version {self._settings.app_version}</p>"
                "<p>Draw mathematical expressions in the air and evaluate them "
                "with OCR-powered recognition.</p>"
            ),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("Main window closing; stopping application controller.")
        self._controller.stop()
        super().closeEvent(event)
