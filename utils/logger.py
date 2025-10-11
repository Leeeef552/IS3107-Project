import sys
import logging
from datetime import datetime, timedelta, timezone

# ----------------------------------------------------------------------
# ✅ CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
SGT = timezone(timedelta(hours=8))  # UTC+8

def sgt_time(*args):
    """Convert log timestamps to Singapore Time (SGT)."""
    return datetime.now(SGT).timetuple()

def get_logger(name: str, level=logging.INFO):
    """
    Create or return a logger instance with consistent settings.
    
    Args:
        name (str): Name of the logger (e.g., filename).
        level (int): Logging level (default: INFO).
    
    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        formatter.converter = sgt_time
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger
