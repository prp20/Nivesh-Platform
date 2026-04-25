import logging
import pytest
from pathlib import Path
from app.logging_config import setup_logging


def test_setup_logging_creates_log_directory(tmp_path):
    log_dir = tmp_path / "logs"
    assert not log_dir.exists()
    setup_logging(log_dir)
    assert log_dir.exists()


def test_setup_logging_adds_file_handler(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    handlers = logging.root.handlers
    handler_types = [type(h).__name__ for h in handlers]
    assert "TimedRotatingFileHandler" in handler_types


def test_setup_logging_adds_stream_handler(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    handlers = logging.root.handlers
    handler_types = [type(h).__name__ for h in handlers]
    assert "StreamHandler" in handler_types


def test_setup_logging_idempotent(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    handler_count = len(logging.root.handlers)
    setup_logging(log_dir)
    assert len(logging.root.handlers) == handler_count


def test_setup_logging_root_level_is_info(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    assert logging.root.level == logging.INFO


def test_setup_logging_noisy_loggers_clamped(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    for name in ("sqlalchemy.engine", "httpx", "httpcore", "apscheduler", "urllib3", "asyncio", "uvicorn.access"):
        assert logging.getLogger(name).level == logging.WARNING


@pytest.fixture(autouse=True)
def reset_root_logger():
    """Remove handlers added by setup_logging after each test to prevent bleed-through."""
    yield
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)
    for name in ("sqlalchemy.engine", "httpx", "httpcore", "apscheduler", "urllib3", "asyncio", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.NOTSET)
