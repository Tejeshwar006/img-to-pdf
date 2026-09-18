"""PDF Scanner - Production-Ready CLI Document Scanner in Python.

Provides automated document corner detection, precision 4-point perspective warping,
and PDF compilation.
"""

__version__ = "1.0.0"
__author__ = "Advanced Computer Vision Engineering Team"

from .edge_detector import (
    detect_and_warp_document,
    four_point_transform,
    order_points,
    refine_quad_corners,
)
from .pdf_converter import images_to_pdf
from .preprocessor import preprocess_image, resize_image
from .tui import run_tui
from .utils import get_image_files, setup_logger

__all__ = [
    "detect_and_warp_document",
    "four_point_transform",
    "order_points",
    "refine_quad_corners",
    "images_to_pdf",
    "preprocess_image",
    "resize_image",
    "get_image_files",
    "setup_logger",
    "run_tui",
]
