"""
tests/test_logger.py
====================
Unit tests for production logging system and error dispatching.
"""

import logging
import sys
from pathlib import Path

import pytest

from src.logger import (
    _unhandled_exception_handler,
    register_error_notifier,
    setup_logger,
)


def test_setup_logger_creates_files(tmp_path: Path):
    test_log_dir = tmp_path / "logs"
    logger = setup_logger(
        name="test_scanner",
        log_dir=test_log_dir,
        log_level="DEBUG",
        enable_console=False,
        install_excepthook=False,
    )

    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Flush handlers
    for h in logging.getLogger().handlers:
        h.flush()

    scan_log = test_log_dir / "daily_scan.log"
    error_log = test_log_dir / "errors.log"

    assert scan_log.exists(), "daily_scan.log must be created"
    assert error_log.exists(), "errors.log must be created"

    scan_content = scan_log.read_text(encoding="utf-8")
    error_content = error_log.read_text(encoding="utf-8")

    # daily_scan.log contains all logs
    assert "This is an info message" in scan_content
    assert "This is a warning message" in scan_content
    assert "This is an error message" in scan_content

    # errors.log must NOT contain INFO messages
    assert "This is an info message" not in error_content
    # errors.log must contain WARNING and ERROR
    assert "This is a warning message" in error_content
    assert "This is an error message" in error_content


def test_logger_formatting_structure(tmp_path: Path):
    test_log_dir = tmp_path / "logs_fmt"
    logger = setup_logger(
        name="format_test",
        log_dir=test_log_dir,
        log_level="INFO",
        enable_console=False,
        install_excepthook=False,
    )

    logger.warning("Sample warning payload")

    for h in logging.getLogger().handlers:
        h.flush()

    error_log = test_log_dir / "errors.log"
    content = error_log.read_text(encoding="utf-8")

    assert "[WARNING]" in content
    assert "[format_test:" in content
    assert "Sample warning payload" in content


def test_unhandled_exception_handler(tmp_path: Path):
    dispatched = []

    def mock_callback(msg: str, ctx: str, tb: str):
        dispatched.append((msg, ctx, tb))

    register_error_notifier(mock_callback)

    try:
        raise ValueError("Simulated unexpected crash")
    except ValueError as e:
        exc_type, exc_val, exc_tb = sys.exc_info()
        _unhandled_exception_handler(exc_type, exc_val, exc_tb)

    assert len(dispatched) == 1
    msg, ctx, tb = dispatched[0]
    assert "ValueError: Simulated unexpected crash" in msg
    assert "Global Unhandled Exception" in ctx
    assert "test_unhandled_exception_handler" in tb
