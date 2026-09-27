"""Logging: one console handler + one file handler per run.

The log file is part of the evidence package (``output/pipeline.log``) so an
evaluator can see *what the pipeline decided and why* without re-running it.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER_NAME = "flasheats"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def configure_logging(log_file: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    # reset handlers so repeated runs in one interpreter (tests, notebooks) do not duplicate output
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:  # pragma: no cover
            pass
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
