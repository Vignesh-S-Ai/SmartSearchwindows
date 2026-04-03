# config/logger.py
# Phase 1: Project Structure & Configuration
# This module provides a centralized logging function for the application.
# It creates loggers with both console and file handlers, with rotation support.

import logging
import logging.handlers
from config.config import LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Create and configure a logger with the specified name.

    This function creates a logger that outputs to both stdout and a rotating file.
    If the logger already has handlers, it returns the existing logger to avoid
    duplicate handlers (important when modules are imported multiple times).

    Args:
        name: The name of the logger (typically __name__ of the calling module)

    Returns:
        A configured logging.Logger instance
    """
    # Get or create the logger by name
    # If handlers already exist, return the logger immediately to avoid duplicates
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Set the logging level from configuration (e.g., DEBUG, INFO, WARNING, ERROR)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Create the log message format with timestamp, level, module name, and message
    # Example: "2024-01-15 10:30:45 | INFO     | module_name | Log message here"
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add console handler (StreamHandler) to output logs to stdout
    # This allows seeing logs in the terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler with rotation to prevent excessive log file growth
    # maxBytes=5*1024*1024 means each log file can grow up to 5MB
    # backupCount=3 means keep up to 3 backup files (app.log.1, app.log.2, app.log.3)
    # encoding="utf-8" ensures proper character encoding for non-ASCII text
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5MB in bytes
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If log directory is not writable (e.g., permission denied),
        # still return logger with console handler only
        logger.warning(f"Could not create log file handler: {e}")

    return logger
