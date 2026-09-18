# Problem Statement & Project Scope: CLI PDF Scanner

## 1. Problem Statement

In academic, legal, engineering, and corporate environments, physical documents—including signed contracts, invoices, receipts, lab notebooks, handwritten lecture notes, and whiteboard diagrams—must routinely be converted into digital, multi-page PDF records. While high-end flatbed scanners provide clean scans, they lack portability and cannot capture documents on the go. Conversely, standard mobile phone photography suffers from severe real-world deficiencies:

1. **Perspective Distortion & Skew:** Photos taken at arbitrary angles exhibit trapezoidal skew rather than an orthographic, top-down rectangular presentation.
2. **Background Clutter & Margin Bleed:** Raw photos capture irrelevant desk surfaces, shadows, cables, and surrounding objects that bloat file sizes and look unprofessional. Standard boundary detection often captures dark desk margins at the top and bottom of the frame.
3. **Lighting Inconsistencies & Uneven Contrast:** Ambient indoor lighting creates intensity gradients across the page, necessitating robust gradient-based edge extraction rather than simple global thresholding.
4. **Privacy & Vendor Lock-in Risks:** Mainstream mobile scanner apps often enforce cloud synchronization, mandatory user accounts, subscription paywalls, watermarking, and invasive telemetry.
5. **Lack of Headless Automation:** Desktop scanning utilities typically rely on heavyweight graphical user interfaces (GUIs) that cannot be integrated into headless servers, CI/CD pipelines, remote SSH sessions, or scheduled batch jobs.

To resolve these challenges, there is a clear demand for an open-source, local-first, production-grade **Command-Line Interface (CLI) & Terminal User Interface (TUI) PDF Scanner** built on modern computer vision algorithms.

---

## 2. Project Scope & Target Users

### In-Scope Capabilities
- **Automated Document Boundary Detection:** Rapid identification of the primary quadrilateral document boundary against textured or contrasting surfaces using multi-strategy Otsu thresholding, closed Canny edges, and convex hull polygon approximation.
- **Precision Margin Refinement:** Directional Sobel gradient analysis along the document perimeter to snap corner coordinates directly onto the physical paper edges, completely eliminating dark desk margins at the top and bottom.
- **Perspective Rectification:** Precise 4-point homography and perspective warping to flatten skewed photographs into crisp, top-down orthographic scans.
- **Fail-Safe Fallback:** Resilient fallback to full-frame cropping whenever a confident 4-point polygon cannot be identified, preventing pipeline termination.
- **Multi-Page PDF Compilation:** Direct compilation of processed pages into a single organized PDF document, respecting natural page sorting, orientation rotations, and resolution metadata.
- **Terminal User Interface (TUI):** Rich interactive terminal dashboard with ASCII art banners, live pipeline status tables, per-page review, and summary cards.
- **Auditing & Telemetry:** Dual-stream structured logging to console and a persistent `scanner.log` file.

### Out-of-Scope (Future Iterations)
- Optical Character Recognition (OCR) text indexing and searchable PDF embedding.
- Deep learning-based corner segmentation models, keeping CPU footprint lightweight (<100MB).
- Cloud storage uploads or remote web APIs.

### Target Users
- **Engineers & Researchers:** Needing scriptable terminal tools to digitize lab records, research receipts, and technical diagrams directly from CLI environments.
- **System Administrators & DevOps:** Automating document processing pipelines on headless Linux/macOS/Windows servers via SSH or cron jobs.
- **Privacy-Conscious Professionals:** Lawyers, accountants, and medical staff requiring 100% offline, on-premise document processing with zero data leakage.
- **Students & Academics:** Compiling scanned assignment pages, handwritten problem sets, and receipts into standardized academic submissions.

---

## 3. High-Level Features

| Module | Feature | Implementation Detail |
| :--- | :--- | :--- |
| **Ingestion** | Multi-Format Image Ingestion | Supports `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.webp` with unicode path compatibility. |
| **Sorting** | Natural Alphanumeric Ordering | Correctly orders sequences like `page_1.png` $\to$ `page_2.png` $\to$ `page_10.png`. |
| **Preprocessing** | Aspect-Preserving Downscaling | Temporarily downsizes images for millisecond-level edge detection, caching scaling ratios. |
| **Vision** | Multi-Strategy Detection & Canny | Dynamic edge thresholds derived from median pixel intensity; convex hull polygon approximation. |
| **Refinement** | Directional Gradient Corner Snapping | Directional Sobel peak detection along margins to eliminate desk background on top/bottom. |
| **Geometry** | 4-Point Perspective Transform | Consistent clockwise corner sorting (`[TL, TR, BR, BL]`) and homographic warping. |
| **Compilation** | Lossless Multi-Page PDF Engine | Dual-engine architecture (Pillow + `img2pdf`) ensuring reliable builds across all OS platforms. |
| **CLI / TUI** | Rich Terminal User Interface | Interactive setup wizard, real-time live processing tables, per-page rotation prompts. |
| **Diagnostics** | Structured Logging & Error Handling | Graceful handling of corrupted files, missing folders, zero-byte inputs, and audit log generation. |
