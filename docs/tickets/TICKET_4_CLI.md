# Ticket 4: CLI Driver & Robustness

**Goal:** Create the entry point script (`archive_mirror.py`) that orchestrates the pipeline with extreme fault tolerance.

## 1. CLI Arguments
Using `argparse`:
*   `input_dir` (Required): Source directory to scan.
*   `output_dir` (Required): Destination directory for the mirror.
*   `--reset`: Optional flag to clear the DB cache (force re-process).
*   `--workers`: Number of threads for the *Scanner* phase (Default: 4).

## 2. Orchestration Flow
1.  **Setup:**
    *   Initialize/Connect `pipeline.db`.
    *   Initialize `OCREngine` (Load Model).
2.  **Scan Phase:**
    *   Run `ArchiveScanner`.
    *   *Robustness:* Handle permission errors on directories gracefully (Log & Skip).
3.  **Process Phase:**
    *   Iterate through `PENDING` files.
    *   **The Watchdog:**
        *   Launch processing in a separate thread (or process pool).
        *   Wait `TIMEOUT` seconds (e.g., 60s).
        *   If timeout -> **Kill/Cancel** -> Mark as `FAILED (Timeout)` in DB -> Write "Skipped: Timeout" to output.
        *   *Reference:* `reference_implementation_frozen/docs2md/convert.py`.
    *   **Update DB:** Mark as `PROCESSED`.
    *   **Log:** Real-time status update.

## 3. Robustness Requirements
*   **Fail-Soft:** A crash in `pypdf`, `pandas`, or `PIL` must NEVER crash the main loop.
*   **Signal Handling:** `Ctrl+C` should stop *after* the current file finishes (graceful shutdown).
*   **Logging:**
    *   Console: Brief (`[OK] file.txt`).
    *   File (`pipeline.log`): Full stack traces for every failure.
    *   *Note:* The old implementation had excellent color-coded logging—copy that style if possible.