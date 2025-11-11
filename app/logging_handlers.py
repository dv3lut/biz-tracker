"""Custom logging handlers used by the application."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Sequence

try:  # pragma: no cover - optional dependency guard
    from elasticsearch import Elasticsearch
except ModuleNotFoundError:  # pragma: no cover - handled gracefully in runtime
    Elasticsearch = None  # type: ignore[assignment]


def _utc_timestamp() -> str:
    """Return a RFC3339 timestamp with millisecond precision."""

    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _ensure_sequence(value: str | Sequence[str]) -> Sequence[str]:
    if isinstance(value, str):
        return [value]
    return value


class ElasticsearchLogHandler(logging.Handler):
    """Push structured log records to an Elasticsearch cluster."""

    def __init__(
        self,
        *,
        hosts: str | Sequence[str],
        index_prefix: str,
        environment: str,
        verify_certs: bool = False,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: int = 10,
    ) -> None:
        super().__init__()
        if Elasticsearch is None:
            raise RuntimeError("Elasticsearch Python client is not installed.")

        connection_args: dict[str, Any] = {
            "hosts": _ensure_sequence(hosts),
            "verify_certs": verify_certs,
            "request_timeout": timeout_seconds,
        }
        if username and password:
            connection_args["basic_auth"] = (username, password)
        self._client = Elasticsearch(**connection_args)
        self._index_prefix = index_prefix.rstrip("-")
        self._environment = environment
        self._timeout = timeout_seconds

    def emit(self, record: logging.LogRecord) -> None:
        try:
            document = self._build_document(record)
            index_name = f"{self._index_prefix}-{datetime.utcnow():%Y.%m.%d}"
            self._client.index(index=index_name, document=document, request_timeout=self._timeout)
        except Exception:  # pragma: no cover - defensive path
            self.handleError(record)

    def _build_document(self, record: logging.LogRecord) -> dict[str, Any]:
        document = getattr(record, "elastic_doc", None)
        if not isinstance(document, dict):
            message = record.getMessage()
            document = self._safe_parse_message(message)

        document.setdefault("@timestamp", _utc_timestamp())
        document.setdefault("message", record.getMessage())
        log_data = document.setdefault("log", {})
        if "level" not in log_data:
            log_data["level"] = record.levelname
        if "logger" not in log_data:
            log_data["logger"] = record.name
        document.setdefault("environment", self._environment)
        service_name = getattr(record, "service_name", None)
        if service_name:
            document.setdefault("service", {"name": service_name})
        return document

    @staticmethod
    def _safe_parse_message(message: str) -> dict[str, Any]:
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"message": message}

    def close(self) -> None:
        try:
            self._client.close()
        finally:
            super().close()