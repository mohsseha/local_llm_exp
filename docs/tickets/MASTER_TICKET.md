# Master Ticket: The "Nerd Archive" Mirror Pipeline

**Goal:** Create a robust, resumable, and deduplicated pipeline to transform a messy input directory (20+ years of diverse files) into a clean, searchable "Mirror" directory of text/markdown files.

## Core Philosophy
1.  **Mirror Structure:** The output folder structure exactly matches the input.
    *   Input: `/Src/Projects/Old/main.c`
    *   Output: `/Dst/Projects/Old/main.c.md`
2.  **Universal Log:** *Every* file in the input must have a corresponding file in the output (except hidden/system files).
    *   Successfully processed files contain the text/content.
    *   Skipped/Ignored files contain a placeholder text explaining *why* (e.g., "Skipped: Binary file", "Skipped: Too small").
3.  **Content-Based Caching:**
    *   We track files by **SHA256 Content Hash**.
    *   If `FileA.jpg` and `FileB.jpg` are identical, we OCR `FileA` once, save the result in the DB, and when we see `FileB`, we just fetch the result from the DB (no re-compute).
4.  **Safety & Limits:**
    *   Single-threaded OCR (M4 Memory constraint).
    *   Hard limit: Output files truncated at 50,000 lines.
    *   Fail-soft: A crash on one file does not stop the batch.

## Architecture

### 1. State Manager (SQLite)
*   **File Table:** Maps `(path)` to `(sha256, status, last_seen)`.
*   **Content Cache:** Maps `(sha256)` to `(extracted_text, metadata)`.
    *   *Note:* This separates "What file is this?" from "What text is in this blob?".

### 2. The Scanner (Producer)
*   Walks the Input Directory.
*   Calculates SHA256 (possibly parallelized).
*   Updates the DB with "New" or "Unchanged" status.
*   Yields tasks to the Processor.

### 3. The Dispatcher (Router)
Decides how to handle a file based on Extension/MIME and specific rules (defined in Sub-Tickets).
*   **Text/Code Strategy:** Copy content (with size limits).
*   **Image Strategy:** Resize -> OCR.
*   **PDF Strategy:** Hybrid (Render -> OCR if images present).
*   **Binary/Ignored Strategy:** Write placeholder.

## Ticket Hierarchy
*   `TICKET_1_SCANNER_DB.md`: Database Schema & File Scanning Logic.
*   `TICKET_2_DISPATCHER_STRATEGIES.md`: The rules for Text, Code, Images, and PDFs.
*   `TICKET_3_OCR_INTEGRATION.md`: Adapting `ocr_engine.py` for the pipeline.
*   `TICKET_4_DRIVER.md`: The CLI entry point and orchestration.
