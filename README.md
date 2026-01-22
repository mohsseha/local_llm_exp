# Local Qwen3-VL OCR (MLX)

A modular, high-performance OCR pipeline for Mac Silicon (M-series) using **Qwen3-VL-8B**.

## Features

- **Hardware Optimized:** Runs efficiently on 16GB/24GB Macs using `mlx-vlm`.
- **Memory Safe:** Automatic image resizing (max 1024px) to prevent OOM errors on large files.
- **PDF Support:** Processes multi-page PDFs page-by-page.
- **Modular:** Separated into `ocr_engine.py` (Core Logic) and `pdf_processor.py` (Utils).

## Setup

1. **Environment:** Ensure you are in a Python environment with `mlx`, `mlx-vlm`, `pillow`, `pdf2image`, and `pdf2image`'s system dependency `poppler`.

   ```bash
   brew install poppler
   pip install mlx mlx-vlm pillow pdf2image
   ```

## Usage

Place your images (`.jpg`, `.png`) or documents (`.pdf`) in the `poc_images/` directory.

Run the main script:

```bash
python3 process_images_mlx_v3.py
```

The script will:
1. Scan `poc_images/`.
2. Process each file (splitting PDFs into temporary page images).
3. Generate a Markdown text file (`.mlx.txt`) for each input.

## Project Structure

- `process_images_mlx_v3.py`: Main orchestrator script.
- `ocr_engine.py`: Core module for model loading and inference.
- `pdf_processor.py`: Utilities for handling PDF page extraction.
- `poc_images/`: Input directory for files to process.