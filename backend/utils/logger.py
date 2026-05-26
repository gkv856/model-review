"""
Centralized logger factory.

All modules call get_logger(__name__) instead of logging.getLogger(__name__).
This ensures every logger automatically gets both a rotating file handler
(logs/app.log, 10 MB × 5 backups) and a console handler.

Log format:
  File:    2025-01-01 12:00:00 | INFO     | core.risk_scorer | [risk_scorer] ...
  Console: 12:00:00 | INFO     | [risk_scorer] ...
"""

import logging
import logging.handlers
import os
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent.parent
_LOG_DIR  = _BACKEND_ROOT / "outputs" / "logs"
_LOG_FILE = _LOG_DIR / "app.log"
_FMT_FILE = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_FMT_CON  = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FILE = "%Y-%m-%d %H:%M:%S"
_DATE_CON  = "%H:%M:%S"

_root_configured = False


def _configure_root() -> None:
    global _root_configured
    if _root_configured:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Rotating file handler — 10 MB per file, keep 5 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter(_FMT_FILE, datefmt=_DATE_FILE))
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(_FMT_CON, datefmt=_DATE_CON))
    ch.setLevel(logging.INFO)
    root.addHandler(ch)

    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to both console and outputs/logs/app.log."""
    _configure_root()
    return logging.getLogger(name)
