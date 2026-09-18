# Production-Ready CLI PDF Scanner

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A high-performance, modular Command-Line Interface (CLI) & Terminal User Interface (TUI) document scanner and PDF compiler built with Python, OpenCV, Pillow, and Rich. Automatically detects document boundaries in raw photos (including real smartphone and WhatsApp camera captures on cluttered desks), corrects perspective distortion via 4-point homography warping with precision top and bottom edge snapping, and compiles multi-page PDFs with a rich interactive terminal experience.

---

## Repository Layout & Expected URL Notes
- **Repository URL Pattern:** `https://github.com/{username}/{repo-name}`
- **Standard Submission Clone:**
  ```bash
  git clone https://github.com/{username}/pdf-scanner.git
  cd pdf-scanner
  ```

---

## Key Features

- **Automatic Directory Generation:**
  - Standard `input/` and `output/` folders are generated automatically on startup if they do not already exist.
- **Rich Terminal User Interface (TUI):**
  - Interactive configuration wizard with ASCII title banners and styled panels.
  - Live progress monitoring with real-time pipeline status tables (`Boundary Detection`, `Warped Size`, `Status`).
  - Interactive per-page review mode (adjust rotation or exclude pages).
  - Clean summary dashboard cards upon completion.
- **Precision Document Boundary Detection & Cropping:**
  - Multi-strategy detection combining Otsu binarization, multi-scale Canny edge maps with morphological closing, and convex hull polygon approximation.
  - **Directional Gradient Refinement:** Directional Sobel peak analysis along top and bottom margins to eliminate dark desk margins and snap corners tightly to physical paper boundaries.
- **4-Point Perspective Warp:** Computes homography matrices to flatten angled or skewed photos into top-down, orthographic scans.
- **Original TrueColor Quality:** Preserves the unmanipulated photographic color fidelity of documents without artificial filters or binarization distortion.
- **Fail-Safe Fallback:** Seamlessly falls back to full-frame image cropping if no confident 4-corner document polygon is located.
- **Multi-Page PDF Compiler:** Converts processed images directly into structured multi-page PDF documents with customizable DPI, page ordering (`natural`, `name`, `date`, `reverse`), and page rotation.
- **Resilient Engineering:** Natural alphanumeric page ordering (`page_1`, `page_2`, `page_10`), Windows Unicode path safety, and dual logging to stdout and `scanner.log`.

---

## Tech Stack

| Technology | Purpose |
| :--- | :--- |
| **Python 3.9+** | Core programming language |
| **OpenCV (`opencv-python`)** | Image preprocessing, Canny/Sobel edge detection, contour analysis, perspective transforms |
| **NumPy** | Matrix operations, vectorized math, corner coordinate ordering |
| **Pillow (PIL)** | Image conversion, color space normalization, lossless PDF generation |
| **Rich** | Terminal User Interface (TUI), styled panels, tables, live progress bars |
| **Click** | Command-line interface definition, flag parsing |
| **TQDM** | Real-time terminal progress visualization in headless mode |

---

## Project Structure

```
pdf_scanner/
├── docs/
│   ├── architecture.md            # Architecture documentation & diagrams
│   └── diagrams/                  # Mermaid diagram source files
├── input/                         # Auto-generated input photo directory
├── output/                        # Auto-generated PDF output directory
├── pdf_scanner/                   # Core Python package
│   ├── __init__.py                # Package exports & version
│   ├── cli.py                     # Click CLI entrypoint
│   ├── preprocessor.py            # Image downsampling & noise reduction
│   ├── edge_detector.py           # Contour finding, edge refinement & 4-point perspective warp
│   ├── pdf_converter.py           # Multi-page PDF compiler & page ordering
│   ├── tui.py                     # Rich Terminal User Interface application
│   └── utils.py                   # File I/O, Unicode safety, natural sorting, logging
├── .gitignore
├── requirements.txt               # Dependency specifications
├── statement.md                   # Problem statement & scope specification
├── PROJECT_REPORT.md              # Academic project report
├── README.md                      # Setup & usage guide
└── main.py                        # Executable CLI launcher
```

---

## Step-by-Step Setup Guide

### Prerequisites
- Python 3.9 or newer
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/{username}/pdf-scanner.git
cd pdf-scanner
```

### 2. Create and Activate Virtual Environment
**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
.\venv\Scripts\activate.bat
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Command-Line Execution Examples

### 1. Interactive TUI Wizard (Default)
Run with no arguments to enter the interactive terminal wizard (automatically generates `input/` and `output/` folders):
```bash
python main.py
```

### 2. Direct Folder Scanning via TUI
Specify input and output folders; the TUI automatically launches:
```bash
python main.py -i input -o output -n my_document.pdf
```

### 3. Save Intermediate Cropped Images
Retain the perspective-rectified `.jpg` files in `output/processed_pages/`:
```bash
python main.py -i input -o output -n archive.pdf --save-images
```

### 4. Interactive Per-Page Review
Prompt to review each page, rotate (0°, 90°, 180°, 270°), or exclude pages:
```bash
python main.py -i input -o output --interactive
```

### 5. Custom Page Ordering
Sort input pages in reverse order or by date:
```bash
python main.py -i input -o output --sort-by reverse
```

### 6. Headless Batch Mode (for CI/CD or Scripts)
Run non-interactively without TUI rendering:
```bash
python main.py -i input -o output --headless --batch-mode
```
