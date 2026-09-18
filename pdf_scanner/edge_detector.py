"""Edge detection, document contour identification, and precision 4-point perspective transform."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .preprocessor import preprocess_image

logger = logging.getLogger("pdf_scanner")


def auto_canny(image: np.ndarray, sigma: float = 0.33) -> np.ndarray:
    """Computes Canny edge map with dynamically calculated thresholds based on median intensity.

    Args:
        image: Single-channel grayscale image array.
        sigma: Threshold sensitivity parameter.

    Returns:
        Binary edge map.
    """
    v = np.median(image)
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    edges = cv2.Canny(image, lower, upper)

    # Dilate slightly to connect disconnected boundary segments
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    return dilated


def order_points(pts: np.ndarray) -> np.ndarray:
    """Orders a list of four 2D coordinates in clockwise order:
    [top-left, top-right, bottom-right, bottom-left].

    Args:
        pts: Array of shape (4, 2) containing corner coordinates.

    Returns:
        Ordered array of shape (4, 2) with dtype float32.
    """
    rect = np.zeros((4, 2), dtype=np.float32)

    # Sum of coordinates: top-left has min sum, bottom-right has max sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # Difference of coordinates: top-right has min diff, bottom-left has max diff
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def is_valid_quad(pts: np.ndarray, min_side_len: float = 30.0) -> bool:
    """Validates that a 4-point polygon is a non-degenerate quadrilateral.

    Args:
        pts: Array of shape (4, 2) containing corner coordinates.
        min_side_len: Minimum acceptable side length in pixels.

    Returns:
        True if the quadrilateral is valid and non-degenerate.
    """
    if pts.shape != (4, 2):
        return False

    ordered = order_points(pts)
    (tl, tr, br, bl) = ordered

    top = np.hypot(tr[0] - tl[0], tr[1] - tl[1])
    bottom = np.hypot(br[0] - bl[0], br[1] - bl[1])
    left = np.hypot(bl[0] - tl[0], bl[1] - tl[1])
    right = np.hypot(br[0] - tr[0], br[1] - tr[1])

    if min(top, bottom, left, right) < min_side_len:
        return False

    width = max(top, bottom)
    height = max(left, right)
    aspect = width / max(height, 1e-5)
    if aspect < 0.15 or aspect > 6.0:
        return False

    return True


def find_document_contour(
    image: np.ndarray,
    min_area_ratio: float = 0.05,
) -> Optional[np.ndarray]:
    """Locates the largest 4-point convex polygon representing document boundaries
    using a multi-strategy ensemble (Otsu binarization, closed Canny edges, and convex hulls).

    Args:
        image: Single-channel grayscale image array or binary edge map.
        min_area_ratio: Minimum fraction of total image area required for a valid contour.

    Returns:
        NumPy array of shape (4, 2) containing detected corners, or None if not found.
    """
    height, width = image.shape[:2]
    total_area = float(height * width)
    min_area = total_area * min_area_ratio
    max_area = total_area * 0.98

    # Fast rejection for flat / blank images
    if float(np.std(image)) < 5.0 or int(image.max()) - int(image.min()) < 15:
        return None

    blurred = cv2.GaussianBlur(image, (5, 5), 0)

    # Multi-strategy binary candidates
    raw_maps: List[Tuple[str, np.ndarray]] = []

    # 1. Otsu thresholding (ideal for light paper on desk)
    _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    raw_maps.append(("otsu", otsu))
    raw_maps.append(("otsu_inv", cv2.bitwise_not(otsu)))

    # 2. Adaptive Gaussian thresholding
    adaptive_thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
    )
    raw_maps.append(("adaptive", adaptive_thresh))

    # 3. Multi-threshold Canny with morphological closing
    kernel5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    kernel9 = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))

    for lower, upper in [(30, 100), (50, 150), (20, 80)]:
        canny = cv2.Canny(blurred, lower, upper)
        closed5 = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, kernel5)
        closed9 = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, kernel9)
        raw_maps.append((f"canny_{lower}_{upper}_c5", closed5))
        raw_maps.append((f"canny_{lower}_{upper}_c9", closed9))

    # 4. Standard auto-canny
    raw_maps.append(("auto_canny", auto_canny(image)))

    border_px = max(2, int(min(height, width) * 0.015))
    k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    candidate_maps: List[Tuple[str, np.ndarray]] = []
    for name, bin_map in raw_maps:
        # Clear outer frame boundary to prevent edge-hugging contours
        bordered = bin_map.copy()
        bordered[:border_px, :] = 0
        bordered[-border_px:, :] = 0
        bordered[:, :border_px] = 0
        bordered[:, -border_px:] = 0
        cleaned = cv2.morphologyEx(bordered, cv2.MORPH_OPEN, k_open)
        candidate_maps.append((name, cleaned))
        candidate_maps.append((f"{name}_raw", bin_map))

    best_quad: Optional[np.ndarray] = None
    best_area: float = 0.0

    for name, bin_map in candidate_maps:
        contours, _ = cv2.findContours(bin_map.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        top_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:6]

        for c in top_contours:
            area = cv2.contourArea(c)
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)

            for candidate_contour, c_area in [(c, area), (hull, hull_area)]:
                if c_area < min_area or c_area > max_area:
                    continue

                peri = cv2.arcLength(candidate_contour, True)

                for eps in (0.02, 0.03, 0.04, 0.05, 0.015, 0.01):
                    approx = cv2.approxPolyDP(candidate_contour, eps * peri, True)

                    if len(approx) == 4 and cv2.isContourConvex(approx):
                        pts = approx.reshape(4, 2)
                        if is_valid_quad(pts) and c_area > best_area:
                            best_area = c_area
                            best_quad = pts

    return best_quad


def refine_quad_corners(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Refines detected quadrilateral corners by snapping onto true paper edges
    using directional Sobel gradient peak analysis along the top and bottom margins.

    Args:
        image: Full-resolution input image (BGR or Grayscale).
        pts: Initial corner coordinates of shape (4, 2).

    Returns:
        Refined corner coordinates of shape (4, 2) with dtype float32.
    """
    h, w = image.shape[:2]
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    sob_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)

    rect = order_points(pts)
    tl, tr, br, bl = rect

    # 1. Refine Top Boundary (Transition from dark background to light document)
    top_y_approx = int(min(tl[1], tr[1]))
    search_top_max = int(min(h * 0.35, max(top_y_approx + 100, 180)))
    mid_x_start = int(max(0, min(tl[0], bl[0]) + w * 0.1))
    mid_x_end = int(min(w - 1, max(tr[0], br[0]) - w * 0.1))

    if mid_x_end > mid_x_start and search_top_max > 10:
        top_slice = sob_y[0:search_top_max, mid_x_start:mid_x_end]
        top_profile = top_slice.mean(axis=1)
        if len(top_profile) > 10:
            best_top_y = int(np.argmax(top_profile))
            # If peak is positive and significant
            if top_profile[best_top_y] > 5.0:
                diff = best_top_y - top_y_approx
                # If detected corner was above the true paper edge
                if diff > 10 or top_y_approx < 30:
                    tl[1] = max(tl[1], float(best_top_y))
                    tr[1] = max(tr[1], float(best_top_y))

    # 2. Refine Bottom Boundary (Transition from light document to dark background/shadow)
    bottom_y_approx = int(max(bl[1], br[1]))
    search_bot_min = int(max(h * 0.65, min(bottom_y_approx - 120, h - 220)))

    if mid_x_end > mid_x_start and search_bot_min < h - 10:
        bot_slice = -sob_y[search_bot_min:h, mid_x_start:mid_x_end]
        bot_profile = bot_slice.mean(axis=1)
        if len(bot_profile) > 10:
            best_bot_offset = int(np.argmax(bot_profile))
            best_bot_y = search_bot_min + best_bot_offset
            if bot_profile[best_bot_offset] > 5.0:
                diff = bottom_y_approx - best_bot_y
                # If detected corner was below the true paper edge
                if diff > 10 or bottom_y_approx > h - 30:
                    bl[1] = min(bl[1], float(best_bot_y))
                    br[1] = min(br[1], float(best_bot_y))

    return np.array([tl, tr, br, bl], dtype=np.float32)


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Extracts and flattens a quadrilateral document region using a 4-point perspective warp.

    Args:
        image: Source image array to warp (full resolution).
        pts: Array of shape (4, 2) with the 4 corner points on the source image.

    Returns:
        Warped top-down orthographic view of the document.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.hypot(br[0] - bl[0], br[1] - bl[1])
    width_b = np.hypot(tr[0] - tl[0], tr[1] - tl[1])
    max_width = max(int(width_a), int(width_b))

    height_a = np.hypot(tr[0] - br[0], tr[1] - br[1])
    height_b = np.hypot(tl[0] - bl[0], tl[1] - bl[1])
    max_height = max(int(height_a), int(height_b))

    max_width = max(max_width, 20)
    max_height = max(max_height, 20)

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype=np.float32,
    )

    m = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, m, (max_width, max_height), flags=cv2.INTER_LINEAR)

    return warped


def detect_and_warp_document(
    image: np.ndarray,
    target_height: int = 800,
    min_area_ratio: float = 0.05,
) -> Tuple[np.ndarray, bool, Optional[np.ndarray]]:
    """Complete document boundary detection, refinement, and perspective correction pipeline.

    If a 4-point document contour is detected, refines top/bottom edges and warps to top-down view.
    If no reliable contour is found, safely falls back to returning the full image.

    Args:
        image: Full-resolution raw input image (BGR format).
        target_height: Downscaled height for fast edge analysis.
        min_area_ratio: Minimum ratio of document area relative to frame area.

    Returns:
        A tuple of (warped_image, quad_detected, scaled_corners):
            warped_image: Processed document image (or full image if fallback).
            quad_detected: True if 4-point contour was found and warped, False if fallback.
            scaled_corners: Array of corners scaled to original image coordinates, or None.
    """
    # 1. Preprocessing for fast boundary detection
    preprocessed_gray, _, scale_ratio = preprocess_image(image, target_height=target_height)

    # 2. Multi-strategy document contour search
    doc_contour = find_document_contour(preprocessed_gray, min_area_ratio=min_area_ratio)

    if doc_contour is None:
        logger.warning("No 4-point document contour detected. Falling back to full image crop.")
        return image.copy(), False, None

    # 3. Map contour coordinates back to original full-resolution space
    orig_corners = (doc_contour.astype(np.float32) * scale_ratio).astype(np.float32)

    # 4. Refine top and bottom edges using directional gradient analysis
    refined_corners = refine_quad_corners(image, orig_corners)

    # 5. Apply 4-point perspective warp on the original full-resolution image
    try:
        warped = four_point_transform(image, refined_corners)
        return warped, True, refined_corners
    except Exception as e:
        logger.warning("Perspective transform failed (%s). Falling back to full image crop.", e)
        return image.copy(), False, None
