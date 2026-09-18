"""Utility functions for file system operations, path validation, and logging."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def setup_logger(
    name: str = "pdf_scanner",
    log_file: Optional[Union[str, Path]] = "scanner.log",
    level: int = logging.INFO,
) -> logging.Logger:
    """Configures and returns a dual-destination logger (console and file).

    Args:
        name: Name of the logger instance.
        log_file: Path to the log file. If None, file logging is disabled.
        level: Logging level (e.g. logging.INFO, logging.DEBUG).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Console Handler with clean format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File Handler with detailed diagnostic format
    if log_file:
        try:
            log_path = Path(log_file).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning("Could not initialize file logger at '%s': %s", log_file, e)

    return logger


def natural_sort_key(s: Union[str, Path]) -> List[Union[int, str]]:
    """Generates a key for natural alphanumeric sorting (e.g. page_1 < page_2 < page_10).

    Args:
        s: String or Path object to key.

    Returns:
        List of alphanumeric tokens for ordering.
    """
    text = str(s)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", text)]


def get_image_files(
    directory_path: Union[str, Path],
    sort_by: str = "natural",
    recursive: bool = False,
) -> List[Path]:
    """Retrieves and sorts supported image files from a given directory.

    Args:
        directory_path: Path to the directory containing images.
        sort_by: Sorting strategy ('natural', 'name', 'date', 'reverse').
        recursive: Whether to scan subdirectories recursively.

    Returns:
        List of Path objects pointing to valid image files.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If directory_path is not a directory.
    """
    path = Path(directory_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Provided path is not a directory: {path}")

    pattern = "**/*" if recursive else "*"
    all_files = [p for p in path.glob(pattern) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]

    if sort_by == "natural":
        all_files.sort(key=lambda p: natural_sort_key(p.name))
    elif sort_by == "name":
        all_files.sort(key=lambda p: p.name.lower())
    elif sort_by == "date":
        all_files.sort(key=lambda p: p.stat().st_mtime)
    elif sort_by == "reverse":
        all_files.sort(key=lambda p: natural_sort_key(p.name), reverse=True)
    else:
        all_files.sort(key=lambda p: natural_sort_key(p.name))

    return all_files


def load_image(file_path: Union[str, Path]) -> np.ndarray:
    """Safely loads an image from disk, properly handling Windows unicode paths.

    Args:
        file_path: Path to the image file.

    Returns:
        Loaded image as a uint8 NumPy array in BGR format.

    Raises:
        FileNotFoundError: If image file does not exist.
        ValueError: If image file is corrupt or cannot be decoded.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    # Use numpy.fromfile + cv2.imdecode for Windows Unicode safety
    try:
        raw_bytes = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
    except Exception as e:
        raise ValueError(f"Failed reading raw bytes for {path}: {e}") from e

    if image is None:
        raise ValueError(f"OpenCV failed to decode image: {path}. File may be corrupted.")

    return image


def save_image(image: np.ndarray, file_path: Union[str, Path]) -> bool:
    """Safely writes an image to disk, handling Windows unicode paths and directories.

    Args:
        image: NumPy array representing the image (BGR or Grayscale).
        file_path: Destination path for the saved image.

    Returns:
        True if the image was successfully saved.

    Raises:
        ValueError: If image encoding fails.
    """
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix if path.suffix else ".jpg"

    success, encoded = cv2.imencode(ext, image)
    if not success:
        raise ValueError(f"Failed to encode image to format '{ext}'")

    with open(path, "wb") as f:
        f.write(encoded.tobytes())

    return True


def format_bytes(num_bytes: int) -> str:
    """Formats an integer byte count into a human-readable string.

    Args:
        num_bytes: Total number of bytes.

    Returns:
        Formatted string (e.g. '1.42 MB').
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"
