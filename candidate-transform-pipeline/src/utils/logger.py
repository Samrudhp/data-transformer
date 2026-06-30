"""
Reusable logging utility for the candidate transformation pipeline.

Provides a centralized logger factory used across all pipeline stages.
"""

import logging
from typing import Optional


def get_logger(name: str, level: Optional[int] = logging.INFO) -> logging.Logger:
    """
    Create and return a named logger with consistent formatting.

    Args:
        name: The logger name (typically __name__ of the calling module).
        level: The logging level. Defaults to INFO.

    Returns:
        A configured Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger
