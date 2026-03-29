"""Logging helpers for TeachWithMeAI backend."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure app-wide logging once."""
    level_name = os.getenv("TEACHWITHMEAI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger("teachwithmeai")
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    ))

    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"teachwithmeai.{name}")
