"""
Structured logging setup — call configure_logging() once at app startup.

Features
--------
* Structured format:  LEVEL | timestamp | module | message
* File + console handlers
* Separate log level control via LOG_LEVEL env var
"""

import logging
import sys
from pathlib import Path


LOG_FORMAT = "%(levelname)-8s | %(asctime)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_DIR = Path("logs")


def configure_logging(level: str = "INFO") -> None:
    """Wire up root logger with console + rotating-file handlers."""
    LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicate handlers on reload (uvicorn hot-reload)
    if root.handlers:
        return

    # ── Console ──────────────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(console)

    # ── File (rotated daily) ─────────────────────────────────────────────
    try:
        from logging.handlers import TimedRotatingFileHandler
        fh = TimedRotatingFileHandler(
            LOG_DIR / "taxbuddy.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        fh.setLevel(numeric_level)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root.addHandler(fh)
    except Exception:
        pass  # non-fatal — file logging unavailable in some environments

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "httpx", "paddleocr", "ppdet", "PIL", "paddlex"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
