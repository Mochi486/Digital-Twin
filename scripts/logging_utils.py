import logging
import sys

from config import LOG_DATE_FORMAT, LOG_FORMAT, LOG_LEVEL


_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        _configure_root_logging()
        _configured = True
    return logging.getLogger(name)


def _configure_root_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


def set_log_level(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
