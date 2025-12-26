from __future__ import annotations

import logging

from app import logging_config


def test_elasticsearch_log_filter_allows_app_logs():
    log_filter = logging_config._ElasticsearchLogFilter()
    record = logging.LogRecord(
        name="app.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="ok",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(record) is True


def test_elasticsearch_log_filter_blocks_elasticsearch_clients():
    log_filter = logging_config._ElasticsearchLogFilter()
    blocked = [
        "elasticsearch",
        "elastic_transport.transport",
        "urllib3.connectionpool",
    ]

    for logger_name in blocked:
        record = logging.LogRecord(
            name=logger_name,
            level=logging.DEBUG,
            pathname=__file__,
            lineno=25,
            msg="blocked",
            args=(),
            exc_info=None,
        )
        assert log_filter.filter(record) is False
