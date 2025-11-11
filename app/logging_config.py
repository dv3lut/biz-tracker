"""Centralized logging configuration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import get_settings
from .logging_handlers import ElasticsearchLogHandler

_LOGGER = logging.getLogger(__name__)

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

    configured_handlers: list[logging.Handler] = []
    if extra_handlers:
        configured_handlers.extend(extra_handlers)

    es_settings = getattr(settings.logging, "elasticsearch", None)
    if es_settings and getattr(es_settings, "enabled", False):
        try:
            es_handler = ElasticsearchLogHandler(
                hosts=es_settings.hosts,
                index_prefix=es_settings.index_prefix,
                environment=es_settings.environment,
                verify_certs=es_settings.verify_certs,
                username=es_settings.username,
                password=es_settings.password,
                timeout_seconds=es_settings.timeout_seconds,
            )
            configured_handlers.append(es_handler)
            
            # Silence Elasticsearch client internal transport logs
            logging.getLogger("elastic_transport").setLevel(logging.WARNING)
        except Exception:  # pragma: no cover - fallback if Elasticsearch is unavailable
            _LOGGER.exception("Initialisation du handler Elasticsearch impossible, journalisation locale uniquement.")

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

    for handler in configured_handlers:
        root_logger.addHandler(handler)
