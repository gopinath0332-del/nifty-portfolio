"""
src/logger.py
=============
Production logging framework engineered for Raspberry Pi & Linux servers.

Features:
  1. Multi-target logging:
     - Console / Standard Out (systemd journalctl compatible).
     - logs/daily_scan.log: Rotating file handler (10 MB, 5 backups) for full execution audit.
     - logs/errors.log: Dedicated error log for WARNING, ERROR, CRITICAL with stack traces (5 MB, 5 backups).
  2. Global Unhandled Exception Hook (sys.excepthook):
     - Automatically intercepts any uncaught exception.
     - Logs full traceback to logs/errors.log.
     - Dispatches Discord critical alert if a notifier is registered.
  3. MicroSD Card Safety:
     - Enforces strict file size limits and automatic file rotation to avoid filling disk space on the Pi.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = BASE_DIR / "logs"

# Global reference to optional Discord error dispatcher
_ERROR_NOTIFIER_CALLBACK: Optional[Callable[[str, str, str], Any]] = None
_LOGGING_INITIALIZED: bool = False


def _unhandled_exception_handler(exc_type, exc_value, exc_traceback) -> None:
    """Global sys.excepthook to capture and log any unhandled crash."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_str = "".join(tb_lines)

    root_logger = logging.getLogger()
    root_logger.critical(
        "🚨 UNHANDLED FATAL EXCEPTION CAUGHT BY GLOBAL EXCEPTHOOK:\n%s",
        tb_str,
    )

    # Dispatch to Discord if callback registered
    if _ERROR_NOTIFIER_CALLBACK:
        try:
            err_msg = f"{exc_type.__name__}: {exc_value}"
            _ERROR_NOTIFIER_CALLBACK(err_msg, "Global Unhandled Exception", tb_str)
        except Exception as cb_err:
            root_logger.error("Failed to dispatch unhandled exception to Discord: %s", cb_err)


def register_error_notifier(callback: Callable[[str, str, str], Any]) -> None:
    """Register a callback (e.g. notifier.notify_error) to receive critical unhandled exceptions."""
    global _ERROR_NOTIFIER_CALLBACK
    _ERROR_NOTIFIER_CALLBACK = callback


def setup_logger(
    name: str = "daily_scan",
    log_dir: str | Path = DEFAULT_LOG_DIR,
    log_level: str | int = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    enable_console: bool = True,
    install_excepthook: bool = True,
) -> logging.Logger:
    """
    Configures an institutional-grade, multi-target logging hierarchy.
    Sets up:
      1. Console StreamHandler (stdout)
      2. RotatingFileHandler for all levels (logs/daily_scan.log)
      3. RotatingFileHandler strictly for WARNING, ERROR, CRITICAL (logs/errors.log)
    """
    global _LOGGING_INITIALIZED

    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Resolve log level
    if isinstance(log_level, str):
        level_str = os.getenv("LOG_LEVEL", log_level).upper().strip()
        numeric_level = getattr(logging, level_str, logging.INFO)
    else:
        numeric_level = log_level

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Detailed format for file logs (includes module, function name, and line number)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Concise format for console logs
    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Remove any existing handlers if already initialized to avoid duplication
    if _LOGGING_INITIALIZED:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    # 1. Console Handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 2. General Rotating File Handler (logs/daily_scan.log)
    scan_log_file = target_dir / "daily_scan.log"
    scan_file_handler = RotatingFileHandler(
        scan_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    scan_file_handler.setLevel(numeric_level)
    scan_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(scan_file_handler)

    # 3. Dedicated Error Rotating File Handler (logs/errors.log)
    error_log_file = target_dir / "errors.log"
    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.WARNING)  # Captures WARNING, ERROR, CRITICAL
    error_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_file_handler)

    # 4. Install global exception hook
    if install_excepthook:
        sys.excepthook = _unhandled_exception_handler

    _LOGGING_INITIALIZED = True
    return logging.getLogger(name)
