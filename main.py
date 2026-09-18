#!/usr/bin/env python3
"""Root executable entrypoint for the CLI PDF Scanner."""

from pathlib import Path
from pdf_scanner.cli import cli

if __name__ == "__main__":
    # Automatically generate default input and output folders if not present
    Path("input").mkdir(parents=True, exist_ok=True)
    Path("output").mkdir(parents=True, exist_ok=True)
    cli()
