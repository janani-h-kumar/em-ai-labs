"""Unit tests for PII redaction filter."""

import logging

import pytest

from src.utils.log_filters import PIIRedactionFilter


@pytest.fixture
def pii_filter():
    return PIIRedactionFilter()


def make_record(msg: str, args=()) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_email_is_redacted(pii_filter):
    record = make_record("User email is janani@example.com today")
    pii_filter.filter(record)
    assert "janani@example.com" not in record.msg
    assert "[EMAIL REDACTED]" in record.msg


def test_api_key_is_redacted(pii_filter):
    record = make_record("Using key abc123def456abc123def456abc123def456abc1")
    pii_filter.filter(record)
    assert "abc123def456" not in record.msg
    assert "[API KEY REDACTED]" in record.msg


def test_bearer_token_is_redacted(pii_filter):
    record = make_record("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload")
    pii_filter.filter(record)
    assert "eyJhbGciOiJIUzI1NiJ9" not in record.msg
    assert "[TOKEN REDACTED]" in record.msg


def test_clean_message_unchanged(pii_filter):
    msg = "Weather in Seattle is 52F today"
    record = make_record(msg)
    pii_filter.filter(record)
    assert record.msg == msg


def test_args_tuple_is_redacted(pii_filter):
    record = make_record("User %s logged in", args=("janani@example.com",))
    pii_filter.filter(record)
    assert "[EMAIL REDACTED]" in str(record.args)
