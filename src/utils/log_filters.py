"""
Log filters that redact PII before records reach file handlers.

Patterns redacted:
- Email addresses         → [EMAIL REDACTED]
- API keys (40-char hex)  → [API KEY REDACTED]
- Bearer tokens           → [TOKEN REDACTED]
"""

import logging
import re

_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL REDACTED]"),
    (re.compile(r"\b[0-9a-fA-F]{32,45}\b"), "[API KEY REDACTED]"),
    (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [TOKEN REDACTED]"),
]


class PIIRedactionFilter(logging.Filter):
    """
    Logging filter that redacts PII patterns from log messages.

    Apply to file handlers only — console output in dev is fine unredacted.

    Usage:
        file_handler.addFilter(PIIRedactionFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(self._redact(str(a)) for a in record.args)
        return True

    @staticmethod
    def _redact(text: str) -> str:
        for pattern, replacement in _PATTERNS:
            text = pattern.sub(replacement, text)
        return text
