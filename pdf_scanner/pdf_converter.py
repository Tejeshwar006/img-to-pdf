"""PDF generation and compilation pipeline from scanned images."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np
from PIL import Image

from .utils import format_bytes

logger = logging.getLogger("pdf_scanner")


def numpy_to_pil(image: np.ndarray, rotation_angle: int = 0) -> Image.Image:
    """Converts a NumPy image array (BGR or Grayscale) to a PIL Image with optional rotation.

    Args:
        image: NumPy array in BGR (3 channels) or Grayscale (2D / 1 channel).
        rotation_angle: Clockwise rotation in degrees (0, 90, 180, 270).

    Returns:
        RGB PIL Image object.
    """
    if len(image.shape) == 2 or image.shape[2] == 1:
        # Grayscale
        pil_img = Image.fromarray(image).convert("RGB")
    else:
        # BGR to RGB conversion
        rgb_arr = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_arr)

    if rotation_angle % 360 != 0:
        # PIL rotate is counter-clockwise by default, so use -rotation_angle for clockwise
        pil_img = pil_img.rotate(-rotation_angle, expand=True)

    return pil_img


def images_to_pdf(
    images: List[Union[np.ndarray, Image.Image, Path, str]],
    output_path: Union[str, Path],
    page_rotations: Optional[List[int]] = None,
    dpi: int = 150,
) -> Dict[str, Any]:
    """Compiles a sequence of processed images into a unified, multi-page PDF document.

    Args:
        images: List of images (NumPy arrays, PIL Images, or file path strings).
        output_path: Destination path for the compiled PDF file.
        page_rotations: Optional list of clockwise rotation angles (0, 90, 180, 270) per page.
        dpi: Target resolution metadata for the PDF pages.

    Returns:
        Dictionary containing compilation summary:
        {'output_path': Path, 'pages': int, 'size_bytes': int, 'size_human': str}

    Raises:
        ValueError: If the input images list is empty.
        IOError: If PDF writing fails.
    """
    if not images:
        raise ValueError("Cannot compile PDF: images list is empty.")

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    pil_images: List[Image.Image] = []
    num_images = len(images)

    for idx, item in enumerate(images):
        rot = page_rotations[idx] if (page_rotations and idx < len(page_rotations)) else 0

        if isinstance(item, np.ndarray):
            pil_img = numpy_to_pil(item, rotation_angle=rot)
        elif isinstance(item, Image.Image):
            pil_img = item.convert("RGB")
            if rot % 360 != 0:
                pil_img = pil_img.rotate(-rot, expand=True)
        elif isinstance(item, (str, Path)):
            p = Path(item).resolve()
            if not p.exists():
                raise FileNotFoundError(f"Image path not found: {p}")
            with Image.open(p) as disk_img:
                pil_img = disk_img.convert("RGB")
                if rot % 360 != 0:
                    pil_img = pil_img.rotate(-rot, expand=True)
        else:
            raise TypeError(f"Unsupported image type: {type(item)}")

        pil_images.append(pil_img)

    # First attempt: Try img2pdf if available for ultra-fast lossless stream insertion
    try:
        import img2pdf  # type: ignore

        jpeg_bytes_list: List[bytes] = []
        for pimg in pil_images:
            buf = io.BytesIO()
            pimg.save(buf, format="JPEG", quality=95)
            jpeg_bytes_list.append(buf.getvalue())

        pdf_bytes = img2pdf.convert(jpeg_bytes_list)
        with open(out_file, "wb") as f:
            f.write(pdf_bytes)

        logger.debug("Compiled PDF using img2pdf engine.")
    except (ImportError, Exception) as e:
        logger.debug("Using Pillow PDF engine (img2pdf unavailable or skipped: %s)", e)
        first_page = pil_images[0]
        subsequent_pages = pil_images[1:] if len(pil_images) > 1 else []

        first_page.save(
            str(out_file),
            "PDF",
            resolution=float(dpi),
            save_all=True,
            append_images=subsequent_pages,
            quality=95,
        )

    file_size = out_file.stat().st_size
    summary = {
        "output_path": out_file,
        "pages": num_images,
        "size_bytes": file_size,
        "size_human": format_bytes(file_size),
    }

    logger.info(
        "Successfully generated PDF '%s' (%d pages, %s)",
        out_file.name,
        num_images,
        summary["size_human"],
    )
    return summary
