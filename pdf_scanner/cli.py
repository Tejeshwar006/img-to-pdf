"""Command-Line Interface (CLI) for the PDF Scanner tool."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import click
import cv2
import numpy as np
from tqdm import tqdm

from .edge_detector import detect_and_warp_document
from .pdf_converter import images_to_pdf
from .tui import run_tui
from .utils import format_bytes, get_image_files, load_image, save_image, setup_logger


@click.command(name="pdf-scanner")
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    required=False,
    help="Path to the directory containing raw input images (opens interactive TUI if omitted).",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("output"),
    show_default=True,
    help="Directory where output PDF and processed images are saved.",
)
@click.option(
    "--output-name",
    "-n",
    type=str,
    default="scanned_document.pdf",
    show_default=True,
    help="Filename for the compiled PDF document.",
)
@click.option(
    "--tui/--no-tui",
    default=True,
    help="Enable Rich Terminal User Interface (TUI) experience (default: enabled).",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    help="Run headlessly without interactive TUI displays.",
)
@click.option(
    "--batch-mode",
    "-b",
    is_flag=True,
    default=False,
    help="Run in headless automated batch mode.",
)
@click.option(
    "--interactive",
    is_flag=True,
    default=False,
    help="Interactively review page rotation and inclusion per document.",
)
@click.option(
    "--save-images",
    "-s",
    is_flag=True,
    default=False,
    help="Save intermediate cropped scanned images to disk.",
)
@click.option(
    "--sort-by",
    type=click.Choice(["natural", "name", "date", "reverse"], case_sensitive=False),
    default="natural",
    show_default=True,
    help="Image ordering criteria before PDF compilation.",
)
@click.option(
    "--dpi",
    type=int,
    default=150,
    show_default=True,
    help="DPI resolution metadata for the generated PDF pages.",
)
@click.option(
    "--filter",
    "-f",
    "filter_mode",
    type=str,
    default="original",
    show_default=True,
    help="Color mode (default: original / unfiltered TrueColor).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose debug logging.",
)
def cli(
    input_dir: Optional[Path],
    output_dir: Path,
    output_name: str,
    filter_mode: str,
    tui: bool,
    headless: bool,
    batch_mode: bool,
    interactive: bool,
    save_images: bool,
    sort_by: str,
    dpi: int,
    verbose: bool,
) -> None:
    """Production-Ready CLI PDF Scanner.

    Detects document boundaries, applies 4-point perspective correction,
    and compiles multi-page PDFs.
    """
    import logging

    log_level = logging.DEBUG if verbose else logging.INFO
    logger = setup_logger("pdf_scanner", log_file="scanner.log", level=log_level)

    # Automatically generate input and output directories if needed
    if input_dir is None:
        input_dir = Path("input")
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # If headless or explicitly requested batch-mode / no-tui, run non-interactive batch runner
    use_tui = tui and not headless and not batch_mode

    if use_tui:
        auto_start = not interactive
        try:
            run_tui(
                input_dir=input_dir,
                output_dir=output_dir,
                output_name=output_name,
                interactive_review=interactive,
                save_images=save_images,
                auto_start=auto_start,
                sort_by=sort_by,
                dpi=dpi,
            )
            return
        except KeyboardInterrupt:
            click.secho("\nOperation cancelled by user.", fg="yellow")
            sys.exit(130)

    # ----------------- Headless / No-TUI Engine -----------------
    click.echo("=" * 60)
    click.secho("  CLI PDF Scanner (Headless Batch Engine)", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Input Directory  : {input_dir.resolve()}")
    click.echo(f"Output Directory : {output_dir.resolve()}")
    click.echo(f"Output PDF Name  : {output_name}")
    click.echo("Color Mode       : Original (No Filter / TrueColor)")
    click.echo(f"Save Images      : {'Yes' if save_images else 'No'}")
    click.echo("-" * 60)

    # 1. Retrieve Image Files
    try:
        image_paths = get_image_files(input_dir, sort_by=sort_by)
    except Exception as e:
        logger.error("Failed to read input directory: %s", e)
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)

    if not image_paths:
        click.secho(
            f"No supported images (.jpg, .png, .bmp, .tiff) found in {input_dir}",
            fg="yellow",
        )
        sys.exit(0)

    click.secho(f"Found {len(image_paths)} image(s) to process.\n", fg="green")

    processed_pages: List[np.ndarray] = []
    page_rotations: List[int] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    if save_images:
        images_subfolder = output_dir / "processed_pages"
        images_subfolder.mkdir(parents=True, exist_ok=True)

    with tqdm(total=len(image_paths), desc="Processing images", unit="img") as pbar:
        for idx, img_path in enumerate(image_paths, start=1):
            pbar.set_postfix_str(f"{img_path.name[:20]}")
            try:
                raw_image = load_image(img_path)
            except Exception as e:
                logger.error("Could not load image %s: %s", img_path.name, e)
                pbar.update(1)
                continue

            warped, quad_found, _ = detect_and_warp_document(raw_image)

            if save_images:
                out_img_name = f"{img_path.stem}_cropped.jpg"
                out_img_path = images_subfolder / out_img_name
                save_image(warped, out_img_path)

            processed_pages.append(warped)
            page_rotations.append(0)
            pbar.update(1)

    if not processed_pages:
        click.secho("\nNo pages were successfully processed. PDF generation aborted.", fg="red")
        sys.exit(1)

    pdf_target_name = output_name if output_name.lower().endswith(".pdf") else f"{output_name}.pdf"
    pdf_destination = output_dir / pdf_target_name

    click.echo("\nCompiling PDF document...")
    try:
        summary = images_to_pdf(
            processed_pages,
            output_path=pdf_destination,
            page_rotations=page_rotations,
            dpi=dpi,
        )
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        click.secho(f"Failed to generate PDF: {e}", fg="red", err=True)
        sys.exit(1)

    click.echo("-" * 60)
    click.secho(" Scanning & PDF Compilation Completed Successfully!", fg="green", bold=True)
    click.echo(f"  Target File : {summary['output_path']}")
    click.echo(f"  Total Pages : {summary['pages']}")
    click.echo(f"  File Size   : {summary['size_human']} ({summary['size_bytes']} bytes)")
    if save_images:
        click.echo(f"  Page Images : {images_subfolder.resolve()}")
    click.echo(f"  Log File    : {Path('scanner.log').resolve()}")
    click.echo("=" * 60)


if __name__ == "__main__":
    cli()
