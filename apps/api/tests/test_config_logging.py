"""Tests for configuration and structured JSON logging."""

import json
import logging

from app.core.config import Settings, get_settings
from app.core.logging import JSONFormatter, setup_logging


def test_settings_default_values() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is True
    assert settings.API_PORT == 8000
    assert "postgresql+asyncpg://" in settings.DATABASE_URL


def test_json_formatter_outputs_valid_json() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Structured test log %s",
        args=("message",),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Structured test log message"
    assert "timestamp" in parsed


def test_setup_logging_configures_root_handler() -> None:
    setup_logging("DEBUG")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) >= 1
    assert isinstance(root_logger.handlers[0].formatter, JSONFormatter)
