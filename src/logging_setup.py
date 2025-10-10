# src/logging_setup.py
import logging
import os
from pathlib import Path
from src.config import settings


def setup_logging(name: str = "") -> logging.Logger:
    log_file = Path(settings.LOG_DIR) / "app.log"
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # базовая конфигурация
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logger = logging.getLogger(name or "app")
    logger.debug("Logging initialized (level=%s)", level_name)
    return logger
