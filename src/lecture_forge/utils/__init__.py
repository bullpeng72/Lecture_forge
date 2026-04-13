"""
Utility functions for LectureForge.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler

from lecture_forge.config import Config


def setup_logging(level: str = None, console: Optional[Console] = None) -> logging.Logger:
    """
    Set up logging with Rich handler.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Optional shared Rich Console instance. When provided, the
                 RichHandler uses the same console as Progress bars so that
                 log messages are rendered inside the live display without
                 causing the progress bar to re-draw (double-render).

    Returns:
        Logger instance
    """
    level = level or Config.LOG_LEVEL

    handler_kwargs: dict = {"rich_tracebacks": True, "show_path": False}
    if console is not None:
        handler_kwargs["console"] = console

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(**handler_kwargs)],
    )

    return logging.getLogger("lecture_forge")


def reconfigure_logging_console(console: Console) -> None:
    """
    Replace the lecture_forge logger's RichHandler with one that uses
    the given console.  Call this once (e.g. at CLI start-up) so that
    Progress bars and log output share the same live display context.

    Args:
        console: The Rich Console instance used by Progress / CLI output.
    """
    lf_logger = logging.getLogger("lecture_forge")
    for handler in lf_logger.handlers[:]:
        if isinstance(handler, RichHandler):
            level = handler.level
            lf_logger.removeHandler(handler)
            new_handler = RichHandler(
                rich_tracebacks=True,
                show_path=False,
                console=console,
            )
            new_handler.setLevel(level)
            lf_logger.addHandler(new_handler)
            return
    # If no RichHandler found on the named logger, check root
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, RichHandler):
            level = handler.level
            root.removeHandler(handler)
            new_handler = RichHandler(
                rich_tracebacks=True,
                show_path=False,
                console=console,
            )
            new_handler.setLevel(level)
            root.addHandler(new_handler)
            return


def timestamp() -> str:
    """Generate timestamp string for file/folder naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename


def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string (e.g., "2h 30m")
    """
    hours = minutes // 60
    mins = minutes % 60

    if hours > 0:
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    else:
        return f"{mins}m"


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


logger = setup_logging()

# Import language utilities for multilingual support
from lecture_forge.utils.language_utils import (
    detect_language,
    get_language_name,
    is_english,
    is_korean,
    translate_text,
    translate_to_english,
    translate_to_korean,
)

__all__ = [
    "setup_logging",
    "reconfigure_logging_console",
    "timestamp",
    "sanitize_filename",
    "format_duration",
    "count_words",
    "format_file_size",
    "merge_dicts",
    "logger",
    # Language utilities
    "detect_language",
    "get_language_name",
    "is_english",
    "is_korean",
    "translate_text",
    "translate_to_english",
    "translate_to_korean",
]
