"""Image preprocessing pipeline for edge detection and document scanning."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def resize_image(image: np.ndarray, target_height: int = 800) -> Tuple[np.ndarray, float]:
    """Resizes an image maintaining aspect ratio for fast edge detection.

    Args:
        image: Original input image array (H, W, C) or (H, W).
        target_height: Desired height in pixels.

    Returns:
        A tuple of (resized_image, scale_ratio) where
        scale_ratio = original_height / resized_height.
    """
    orig_h, orig_w = image.shape[:2]
    if orig_h <= target_height or target_height <= 0:
        return image.copy(), 1.0

    scale_ratio = orig_h / float(target_height)
    target_width = int(orig_w / scale_ratio)

    resized = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized, scale_ratio


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Converts a BGR or multi-channel image to single-channel 8-bit grayscale.

    Args:
        image: Input image array.

    Returns:
        Grayscale image array.
    """
    if len(image.shape) == 2:
        return image.copy()
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def reduce_noise(
    image: np.ndarray,
    method: str = "gaussian",
    ksize: int = 5,
) -> np.ndarray:
    """Applies noise reduction filter to smooth out textures and sensor noise.

    Args:
        image: Grayscale or BGR image array.
        method: Smoothing method ('gaussian', 'bilateral', 'median').
        ksize: Kernel size (must be an odd integer).

    Returns:
        Smoothed image array.
    """
    if ksize % 2 == 0:
        ksize += 1

    if method == "bilateral":
        return cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
    if method == "median":
        return cv2.medianBlur(image, ksize)
    # Default to Gaussian Blur
    return cv2.GaussianBlur(image, (ksize, ksize), 0)


def preprocess_image(
    image: np.ndarray,
    target_height: int = 800,
    noise_reduction: str = "gaussian",
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Runs standard preprocessing sequence to prepare raw image for contour detection.

    Args:
        image: Full-resolution raw input image (BGR).
        target_height: Height to downscale to for edge detection efficiency.
        noise_reduction: Method for smoothing ('gaussian', 'bilateral', 'median').

    Returns:
        A tuple of (preprocessed_gray, resized_bgr, scale_ratio).
    """
    resized_bgr, scale_ratio = resize_image(image, target_height=target_height)
    gray = to_grayscale(resized_bgr)
    smoothed = reduce_noise(gray, method=noise_reduction, ksize=5)

    # Optional morphological closing to bridge gaps between document text and border
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)

    return closed, resized_bgr, scale_ratio
