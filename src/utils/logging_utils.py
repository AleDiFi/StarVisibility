"""
Logging configuration for StarVisibility.

Sets up:
  - a rotating file handler writing to LOG_DIR/starvisibility.log
  - a stream handler for the console
  - a Qt-compatible signal emitter so the GUI log panel receives messages
    without polling or direct widget references.
"""

from __future__ import annotations

import logging
import logging.handlers
from typing import Callable, Optional

from src.config.settings import LOG_FILE

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Root logger name for the application
APP_LOGGER = "starvisibility"


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """
    Configure the application logger.  Safe to call multiple times;
    handlers are only added once.
    """
    logger = logging.getLogger(APP_LOGGER)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # --- file handler (rotating, 5 MB × 3 backups) ---
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # --- console handler ---
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the application root logger."""
    return logging.getLogger(f"{APP_LOGGER}.{name}")


# ---------------------------------------------------------------------------
# Callback handler – used by the GUI log panel
# ---------------------------------------------------------------------------


class CallbackHandler(logging.Handler):
    """
    A logging handler that calls a user-supplied callback for each record.
    The callback receives a single string (the formatted message).
    """

    def __init__(self, callback: Callable[[str], None], level: int = logging.INFO) -> None:
        super().__init__(level)
        self.callback = callback
        self.setFormatter(logging.Formatter("%(levelname)-8s  %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:  # noqa: BLE001  – never crash the app from a logger
            self.handleError(record)


def add_callback_handler(
    callback: Callable[[str], None],
    level: int = logging.INFO,
) -> CallbackHandler:
    """
    Attach a CallbackHandler to the application root logger and return it.
    The caller is responsible for removing it when no longer needed.
    """
    logger = logging.getLogger(APP_LOGGER)
    handler = CallbackHandler(callback, level)
    logger.addHandler(handler)
    return handler


def remove_handler(handler: logging.Handler) -> None:
    """Detach a handler from the application root logger."""
    logging.getLogger(APP_LOGGER).removeHandler(handler)
