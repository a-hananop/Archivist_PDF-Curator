"""
utils/logger.py
================
Centralized logging setup using loguru. Falls back to the stdlib `logging`
module transparently if loguru is not installed, so the rest of the codebase
never has to care which backend is active.
"""

from __future__ import annotations

import sys
from pathlib import Path

from config import CONFIG

_LOGGER = None


def _build_loguru_logger():
    from loguru import logger as _loguru_logger

    _loguru_logger.remove()  # drop default handler

    if CONFIG.log_to_console:
        _loguru_logger.add(
            sys.stderr,
            level=CONFIG.log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True,
        )

    log_file = Path(CONFIG.logs_dir) / "pdf_agent.log"
    _loguru_logger.add(
        str(log_file),
        level=CONFIG.log_level,
        rotation=CONFIG.log_file_rotation,
        retention=CONFIG.log_file_retention,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    return _loguru_logger


def _build_stdlib_logger():
    import logging

    logger = logging.getLogger("pdf_agent")
    logger.setLevel(CONFIG.log_level)
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
        )
        if CONFIG.log_to_console:
            sh = logging.StreamHandler(sys.stderr)
            sh.setFormatter(fmt)
            logger.addHandler(sh)

        log_file = Path(CONFIG.logs_dir) / "pdf_agent.log"
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def get_logger():
    """Return the process-wide logger instance (lazily initialised)."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    try:
        _LOGGER = _build_loguru_logger()
    except ImportError:
        _LOGGER = _build_stdlib_logger()

    return _LOGGER


logger = get_logger()
