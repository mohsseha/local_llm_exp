# Ticket 1: Scanner & Database Layer

**Goal:** Implement the SQLite state manager and the file scanning logic.

## 1. Database Schema (`pipeline.db`)

### Table: `files`
Tracks the files currently present on the disk.
*   `path` (TEXT PK): Absolute path of the source file.
*   `file_hash` (TEXT): SHA256 of the file content.
*   `size_bytes` (INTEGER): File size.
*   `mtime` (REAL): Last modified timestamp.
*   `status` (TEXT): `PENDING`, `PROCESSED`, `FAILED`, `SKIPPED`.
*   `error_msg` (TEXT): If failed/skipped, why?

### Table: `content_cache`
Stores the expensive extraction results to allow deduplication.
*   `content_hash` (TEXT PK): SHA256 (same as `file_hash`).
*   `extracted_text` (TEXT): The full result content.
*   `strategy_used` (TEXT): e.g., 'ocr_qwen', 'text_copy'.
*   `model_version` (TEXT): Version of the OCR engine used (for future invalidation).

## 2. Scanner Logic (`scanner.py`)

### `class ArchiveScanner`
1.  **Input:** Root directory path.
2.  **Process:**
    *   Walk directory tree.
    *   For each file:
        *   Check `files` table for `path`.
        *   If `path` exists AND `mtime` matches AND `size` matches -> **Yield (SKIP/NO-OP)**.
        *   Else (New/Changed):
            *   Compute SHA256.
            *   Upsert into `files` table with `status=PENDING`.
            *   Yield `FileObject` for processing.

### Constraints
*   **Parallel Hashing:** The hashing step (CPU bound-ish) can be parallelized (Threadpool) if impactful, but ensure DB writes are locked/safe.
*   **Memory:** Don't load 10GB ISOs into RAM to hash. Read in chunks (e.g., 64KB).
