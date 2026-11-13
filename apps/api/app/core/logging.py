"""Structured JSON logging configuration."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.ai.redaction import redact_dict_secrets, redact_secrets

STANDARD_LOG_RECORD_ATTRS: set[str] = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "id",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JSONFormatter(logging.Formatter):
    """Custom formatter producing single-line structured JSON output."""

    def format(self, record: logging.LogRecord) -> str:
        # Scrub secrets from message per Hard Rule 4
        clean_msg = redact_secrets(record.getMessage())
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": clean_msg,
        }

        if record.exc_info:
            log_payload["exception"] = redact_secrets(self.formatException(record.exc_info))

        if record.stack_info:
            log_payload["stack_info"] = redact_secrets(self.formatStack(record.stack_info))

        # Extract extra structured fields with recursive secret scrubbing
        extra_fields = {
            k: redact_dict_secrets(v)
            for k, v in record.__dict__.items()
            if k not in STANDARD_LOG_RECORD_ATTRS and not k.startswith("_")
        }
        if extra_fields:
            log_payload["extra"] = extra_fields

        return json.dumps(log_payload, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root and framework loggers with the structured JSON formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers.clear()
        named_logger.addHandler(handler)
        named_logger.propagate = False
        named_logger.setLevel(numeric_level)
