"""Centralized logging configuration."""
from __future__ import annotations

import logging
from logging import Logger
from pathlib import Path
from typing import Optional

from .config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _build_file_handler(path: Path, level: int) -> logging.Handler:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    return handler


def configure_logging(extra_handlers: Optional[list[logging.Handler]] = None) -> None:
    """Configure console and file loggers."""

    settings = get_settings()
    log_dir = Path(settings.logging.directory)
    log_dir.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.logging.level)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    app_file_handler = _build_file_handler(
        log_dir / settings.logging.app_log_filename,
        getattr(logging, settings.logging.level.upper(), logging.INFO),
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.logging.level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_file_handler)

    alerts_handler = _build_file_handler(
        log_dir / settings.logging.alerts_log_filename,
        logging.INFO,
    )
    alerts_logger = logging.getLogger("alerts")
    alerts_logger.setLevel(logging.INFO)
    alerts_logger.handlers.clear()
    alerts_logger.addHandler(alerts_handler)
    alerts_logger.propagate = False

    if extra_handlers:
        for handler in extra_handlers:
            root_logger.addHandler(handler)
