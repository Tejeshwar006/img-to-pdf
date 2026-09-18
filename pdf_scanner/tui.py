"""Terminal User Interface (TUI) for PDF Scanner using Rich."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from rich.align import Align
from rich.box import DOUBLE, ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .edge_detector import detect_and_warp_document
from .pdf_converter import images_to_pdf
from .utils import format_bytes, get_image_files, load_image, save_image, setup_logger

console = Console()


def render_banner() -> Panel:
    """Generates a styled ASCII title banner for the TUI."""
    title_text = Text()
    title_text.append("╔════════════════════════════════════════════════════════════════════╗\n", style="bold cyan")
    title_text.append("║                    📄  SCANNER-CLI  TUI                            ║\n", style="bold white")
    title_text.append("║       Automated Document Boundary Detection & PDF Compiler         ║\n", style="italic bright_blue")
    title_text.append("╚════════════════════════════════════════════════════════════════════╝", style="bold cyan")
    return Panel(
        Align.center(title_text),
        box=ROUNDED,
        border_style="cyan",
        subtitle="[dim]v1.0.0 • Local-First & Zero-GUI • Precision Computer Vision[/dim]",
        subtitle_align="center",
    )


def prompt_tui_configuration(
    initial_input: Optional[Path] = None,
    initial_output: Optional[Path] = None,
    initial_name: str = "scanned_document.pdf",
) -> Tuple[Path, Path, str, bool, bool]:
    """Guides the user through an interactive TUI configuration wizard.

    Returns:
        (input_dir, output_dir, output_name, interactive_mode, save_images)
    """
    console.clear()
    console.print(render_banner())

    # 1. Input directory
    default_input = "input"
    Path(default_input).mkdir(parents=True, exist_ok=True)
    if initial_input:
        default_input = str(initial_input)
        Path(default_input).mkdir(parents=True, exist_ok=True)

    in_path_str = Prompt.ask("\n[bold cyan]📁 Input Directory[/bold cyan] (folder containing photos)", default=default_input)
    in_path = Path(in_path_str).resolve()
    in_path.mkdir(parents=True, exist_ok=True)

    # 2. Output directory
    default_output = str(initial_output) if initial_output else "output"
    Path(default_output).mkdir(parents=True, exist_ok=True)
    out_path_str = Prompt.ask("[bold cyan]📂 Output Directory[/bold cyan] (where PDF will be saved)", default=default_output)
    out_path = Path(out_path_str).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    # 3. Output PDF filename
    pdf_name = Prompt.ask("[bold cyan]📄 Output PDF Filename[/bold cyan]", default=initial_name)
    if not pdf_name.lower().endswith(".pdf"):
        pdf_name += ".pdf"

    # 4. Review Mode
    console.print("\n[bold yellow]Workflow Options:[/bold yellow]")
    interactive_review = Confirm.ask(
        "Enable interactive page-by-page review (adjust rotation or exclude pages)?",
        default=False,
    )

    save_images = Confirm.ask(
        "Save intermediate precision-cropped JPEG images?",
        default=True,
    )

    return in_path, out_path, pdf_name, interactive_review, save_images


def run_tui(
    input_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    output_name: str = "scanned_document.pdf",
    interactive_review: bool = False,
    save_images: bool = False,
    auto_start: bool = False,
    sort_by: str = "natural",
    dpi: int = 150,
) -> None:
    """Runs the primary Rich TUI experience for document scanning.

    Args:
        input_dir: Pre-specified input directory, or None to prompt.
        output_dir: Pre-specified output directory, or None to prompt.
        output_name: Output PDF filename.
        interactive_review: Whether to prompt per page.
        save_images: Whether to save intermediate cropped JPEGs.
        auto_start: If True and input_dir exists, skip wizard and start processing.
        sort_by: Sorting strategy ('natural', 'name', 'date', 'reverse').
        dpi: Target PDF DPI resolution.
    """
    logger = setup_logger("pdf_scanner", log_file="scanner.log")

    # Automatically ensure default input and output directories exist
    input_dir = (input_dir or Path("input")).resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir = (output_dir or Path("output")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not auto_start:
        input_dir, output_dir, output_name, interactive_review, save_images = (
            prompt_tui_configuration(
                initial_input=input_dir,
                initial_output=output_dir,
                initial_name=output_name,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    images_subfolder = output_dir / "processed_pages"
    if save_images:
        images_subfolder.mkdir(parents=True, exist_ok=True)

    # Scan for images
    image_paths = get_image_files(input_dir, sort_by=sort_by)
    if not image_paths:
        console.print(f"\n[bold yellow]No supported image files found in {input_dir}[/bold yellow]")
        return

    # Configuration summary panel
    config_table = Table.grid(padding=(0, 2))
    config_table.add_column(style="bold cyan")
    config_table.add_column(style="white")
    config_table.add_row("Input Directory:", str(input_dir.resolve()))
    config_table.add_row("Output Directory:", str(output_dir.resolve()))
    config_table.add_row("Target PDF:", output_name)
    config_table.add_row("Color Mode:", "[bold green]Original TrueColor (No Filter)[/bold green]")
    config_table.add_row("Page Ordering:", sort_by.capitalize())
    config_table.add_row("Images Found:", f"{len(image_paths)} file(s)")
    config_table.add_row("Page Review:", "Enabled (Interactive)" if interactive_review else "Automated Batch")
    config_table.add_row("Save Cropped Images:", "Yes" if save_images else "No")

    console.print("\n", Panel(config_table, title="[bold green]Scan Session Config[/bold green]", box=ROUNDED, border_style="green"))

    # Live processing table
    results_table = Table(
        title="[bold cyan]Processing Pipeline Status[/bold cyan]",
        box=ROUNDED,
        show_lines=True,
    )
    results_table.add_column("#", justify="center", style="dim", width=4)
    results_table.add_column("File Name", style="bold white")
    results_table.add_column("Original Size", justify="center", style="dim")
    results_table.add_column("Boundary Detection", justify="center")
    results_table.add_column("Warped Size", justify="center", style="cyan")
    results_table.add_column("Color Mode", justify="center", style="green")
    results_table.add_column("Rotation", justify="center", style="magenta")
    results_table.add_column("Status", justify="center", style="bold green")

    processed_pages: List[np.ndarray] = []
    page_rotations: List[int] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        transient=True,
    )

    with progress:
        task = progress.add_task("[cyan]Processing documents...", total=len(image_paths))

        for idx, img_path in enumerate(image_paths, start=1):
            progress.update(task, description=f"[cyan]Scanning {img_path.name[:25]}...")
            time.sleep(0.05)

            try:
                raw_image = load_image(img_path)
            except Exception as e:
                logger.error("Failed to load %s: %s", img_path.name, e)
                results_table.add_row(
                    str(idx),
                    img_path.name,
                    "-",
                    "[red]Load Failed[/red]",
                    "-",
                    "-",
                    "-",
                    "[red]Skipped[/red]",
                )
                progress.advance(task)
                continue

            orig_h, orig_w = raw_image.shape[:2]

            # 1. Document boundary detection & perspective warp
            warped, quad_detected, corners = detect_and_warp_document(raw_image)
            warp_h, warp_w = warped.shape[:2]

            boundary_status = (
                "[bold green]✔ 4-Point Quad[/bold green]"
                if quad_detected
                else "[yellow]⚠ Full Fallback[/yellow]"
            )

            # 2. Interactive review per page if enabled
            rotation_deg = 0

            if interactive_review:
                progress.stop()
                console.print(f"\n[bold yellow]── Page Review [{idx}/{len(image_paths)}]: {img_path.name} ──[/bold yellow]")
                console.print(f"  • Resolution: {orig_w}x{orig_h} -> Warped: {warp_w}x{warp_h}")
                console.print(f"  • Boundary: {boundary_status}")

                include = Confirm.ask("  Include page in PDF?", default=True)
                if not include:
                    results_table.add_row(
                        str(idx),
                        img_path.name,
                        f"{orig_w}x{orig_h}",
                        boundary_status,
                        "-",
                        "Original",
                        "-",
                        "[dim yellow]Excluded by user[/dim yellow]",
                    )
                    progress.start()
                    progress.advance(task)
                    continue

                rot_choice = Prompt.ask(
                    "  Rotate page clockwise?",
                    choices=["0", "90", "180", "270"],
                    default="0",
                )
                rotation_deg = int(rot_choice)
                progress.start()

            # 3. Save intermediate image if requested
            if save_images:
                out_img_name = f"{img_path.stem}_cropped.jpg"
                out_img_path = images_subfolder / out_img_name
                save_image(warped, out_img_path)

            processed_pages.append(warped)
            page_rotations.append(rotation_deg)

            rot_str = f"{rotation_deg}°" if rotation_deg > 0 else "0°"
            results_table.add_row(
                str(idx),
                img_path.name,
                f"{orig_w}x{orig_h}",
                boundary_status,
                f"{warp_w}x{warp_h}",
                "[green]Original[/green]",
                rot_str,
                "[bold green]Processed[/bold green]",
            )
            progress.advance(task)

    console.print("\n", results_table)

    # PDF Compilation
    if not processed_pages:
        console.print("\n[bold red]No pages were included for PDF compilation.[/bold red]")
        return

    target_pdf_path = output_dir / output_name

    with console.status("[bold cyan]Compiling multi-page PDF document...[/bold cyan]", spinner="dots"):
        summary = images_to_pdf(
            processed_pages,
            target_pdf_path,
            page_rotations=page_rotations,
            dpi=dpi,
        )

    # Final Dashboard
    summary_panel = Panel(
        Align.center(
            f"[bold green]✔ PDF Successfully Generated![/bold green]\n\n"
            f"[bold white]Output Path :[/bold white] [cyan]{summary['output_path']}[/cyan]\n"
            f"[bold white]Total Pages :[/bold white] [yellow]{summary['pages']}[/yellow]\n"
            f"[bold white]File Size   :[/bold white] [green]{summary['size_human']}[/green] ({summary['size_bytes']:,} bytes)\n"
            f"[bold white]Audit Log   :[/bold white] [dim]{Path('scanner.log').resolve()}[/dim]\n"
        ),
        title="[bold green]Scan Summary[/bold green]",
        box=DOUBLE,
        border_style="green",
    )
    console.print("\n", summary_panel)
