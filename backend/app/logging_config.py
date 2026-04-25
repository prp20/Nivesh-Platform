import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_NOISY_LOGGERS = (
    "sqlalchemy.engine",
    "httpx",
    "httpcore",
    "apscheduler",
    "urllib3",
    "asyncio",
    "uvicorn.access",
)


def setup_logging(log_dir: Path) -> None:
    """Configure root logger with file + console handlers.

    Safe to call multiple times — guards against duplicate handler registration.
    log_dir is created automatically if it does not exist.
    Raises PermissionError if log_dir cannot be created or written to.
    """
    already_configured = any(
        isinstance(h, (TimedRotatingFileHandler, logging.StreamHandler))
        and not h.__class__.__name__ == "LogCaptureHandler"
        for h in logging.root.handlers
    )
    if already_configured:
        return

    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(stream_handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
