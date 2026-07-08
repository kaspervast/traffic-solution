"""Logging setup with secret redaction.

Never let API keys (TomTom key= query param, Gemini API key, DB password,
JWT secret, SMTP password) reach log output. This filter scrubs common
secret patterns from every log record before it is emitted.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Iterable

# Patterns that redact "key=VALUE" / "key: VALUE" style secrets in URLs and
# structured messages. Keep this list conservative but broad.
_REDACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(key=)([A-Za-z0-9_\-\.]{6,})"),
    re.compile(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9_\-\.]{6,})"),
    re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)(bearer\s+[A-Za-z0-9_\-\.]+)"),
    re.compile(r"(?i)(:)([^:@/\s]{3,})(@)"),  # postgres://user:PASSWORD@host
    re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)([^\s\"',]{3,})"),
]

_REDACTED = "***REDACTED***"


def redact(message: str) -> str:
    out = message
    for pattern in _REDACT_PATTERNS:
        if pattern.groups == 3:
            out = pattern.sub(lambda m: f"{m.group(1)}{_REDACTED}{m.group(3)}", out)
        else:
            out = pattern.sub(lambda m: f"{m.group(1)}{_REDACTED}", out)
    return out


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(str(record.getMessage()))
            record.args = ()
        except Exception:  # pragma: no cover - never let logging crash the app
            pass
        return True


def configure_logging(level: int = logging.INFO, extra_loggers: Iterable[str] = ()) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    handler.addFilter(RedactionFilter())

    root.handlers.clear()
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpx", *extra_loggers):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
