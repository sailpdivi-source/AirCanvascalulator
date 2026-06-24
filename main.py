"""AirCanvas Calculator application entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import (
    APP_NAME,
    APP_VERSION,
    ConfigurationError,
    Settings,
    apply_tesseract_to_pytesseract,
    configure_logging,
    dump_settings,
    load_settings,
    validate_environment,
)

logger = logging.getLogger(__name__)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aircanvas",
        description=f"{APP_NAME} — gesture-controlled air canvas calculator",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON configuration file path",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override logging level for this session",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate environment and configuration, then exit without launching the UI",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the effective configuration as JSON and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    return parser


def _apply_cli_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    if args.log_level is None:
        return settings

    from dataclasses import replace

    return replace(
        settings,
        logging=replace(settings.logging, level=args.log_level),
    )


def _report_validation_errors(errors: list[str]) -> int:
    for message in errors:
        logger.error(message)
    logger.error("Startup validation failed with %d error(s).", len(errors))
    return 1


def _launch_application(settings: Settings) -> int:
    """Create the Qt application and start the main controller."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:
        logger.critical("PyQt6 is required but could not be imported: %s", exc)
        return 1

    try:
        from core.app_controller import AppController
        from ui.main_window import MainWindow
    except ImportError as exc:
        logger.critical(
            "Application modules are not available yet: %s. "
            "Implement core.app_controller and ui.main_window to launch the UI.",
            exc,
        )
        return 1

   # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.app_version)
    app.setOrganizationName("AirCanvas")

    try:
        controller = AppController(settings)
        window = MainWindow(controller, settings)
        window.show()
        controller.start()
    except Exception:
        logger.exception("Fatal error while starting %s", settings.app_name)
        return 1

    logger.info("%s started successfully.", settings.app_name)
    exit_code = app.exec()
    logger.info("%s exited with code %d.", settings.app_name, exit_code)
    return int(exit_code)


def main(argv: list[str] | None = None) -> int:
    """Application bootstrap: parse CLI, load config, validate, and run."""
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings(config_path=args.config)
        settings = _apply_cli_overrides(settings, args)
        configure_logging(settings)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.debug("Project root: %s", settings.project_root)

    if args.print_config:
        dump_settings(settings)
        return 0

    validation_errors = validate_environment(settings)
    if validation_errors:
        return _report_validation_errors(validation_errors)

    tesseract_cmd = apply_tesseract_to_pytesseract(settings)
    if tesseract_cmd is not None:
        logger.info("Using Tesseract executable at '%s'", tesseract_cmd)
    else:
        logger.warning("Tesseract path could not be applied to pytesseract.")

    if args.validate_only:
        logger.info("Environment validation passed.")
        return 0

    return _launch_application(settings)


if __name__ == "__main__":
    sys.exit(main())
