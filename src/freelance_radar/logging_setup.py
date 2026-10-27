"""Structured logging without secrets."""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

_SECRET_PATTERNS = (
    re.compile(r"(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*\S+", re.I),
    re.compile(r"Bearer\s+\S+", re.I),
)


def _scrub(value: str) -> str:
    scrubbed = value
    for pattern in _SECRET_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def _scrub_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = _scrub(value)
        key_lower = str(key).lower()
        if any(s in key_lower for s in ("token", "password", "secret", "api_key", "apikey")):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _scrub_event,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
