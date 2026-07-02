"""Logger terpusat, tulis ke file dan stdout (PRD bagian 8)."""
from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(log_file_path: Path, level: str = "INFO") -> logging.Logger:
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("idx_alert")
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger
