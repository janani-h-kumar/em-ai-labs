# tests/unit/test_logging_utils.py

import json
import logging

from src.utils.logging_utils import (
    StructuredFormatter,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


def test_set_correlation_id_accepts_custom():
    assert get_correlation_id() == "my-request-123"
    reset_correlation_id()


def test_reset_clears_id():
    set_correlation_id("test")
    reset_correlation_id()
    assert (
        get_correlation_id() is None
    )  # requires get_correlation_id() returns None, not auto-generate


def test_structured_formatter_valid_json():
    formatter = StructuredFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "Test", (), None)
    data = json.loads(formatter.format(record))
    assert data["level"] == "INFO"
    assert "timestamp" in data and "correlation_id" in data


def test_structured_formatter_includes_correlation_id():
    set_correlation_id("trace-abc")
    formatter = StructuredFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    data = json.loads(formatter.format(record))
    assert data["correlation_id"] == "trace-abc"
    reset_correlation_id()
