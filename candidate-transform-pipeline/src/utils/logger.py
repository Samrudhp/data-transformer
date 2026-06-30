"""
Reusable logging utility for the candidate transformation pipeline.

Provides a centralized logger factory used across all pipeline stages.
Supports dual logging mode: silent console (default) vs verbose console.
Always logs to logs/pipeline.log.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

_initialized = False
_verbose_mode = False


def configure_logging(verbose: bool = False) -> None:
    """
    Configure root logging: always write to logs/pipeline.log.
    If verbose=True, also output to stdout.
    """
    global _initialized, _verbose_mode
    _verbose_mode = verbose

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)

    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root.addHandler(file_handler)
    except Exception:
        # Fallback if file handler cannot be created
        pass

    # Console Handler (only if verbose)
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root.addHandler(console_handler)

    _initialized = True


def get_logger(name: str, level: Optional[int] = logging.INFO) -> logging.Logger:
    """
    Create and return a named logger.
    If configure_logging has not been called, auto-initializes in default mode.
    """
    global _initialized
    if not _initialized:
        configure_logging(verbose=False)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = True
    return logger
