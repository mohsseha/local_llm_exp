# Ticket 2: Dispatcher & Strategies

**Goal:** Implement the routing logic that decides *how* to process a file based on its type and properties.

## 1. The Dispatcher
*   **Input:** `FileObject` (Path, Hash, Extension).
*   **Logic:**
    1.  Check `content_cache` using `hash`. If found -> **Return Cached Result** immediately.
    2.  If Miss -> Determine Strategy based on Extension + Magic Number.
    3.  **TIMEOUT GUARD:** Every strategy execution must be wrapped in a strict timeout (e.g., 60-120s). If it hangs, kill it and return "Skipped: Timeout".
        *   *Reference:* See `reference_implementation_frozen/docs2md/convert.py` -> `process_file_with_timeout` for a robust ThreadPool implementation.
    4.  Execute Strategy.
    5.  Save Result to `content_cache`.
    6.  Write Output File (Mirror).

## 2. Strategies

### A. `TextCodeStrategy`
*   **Whitelist:** `.py`, `.c`, `.h`, `.js`, `.ts`, `.md`, `.txt`, `.json`, `.xml`, `.html`, `.css`, etc.
*   **Rules:**
    *   **Max Lines:** 50,000. If > 50k, read first 50k, append "\n[TRUNCATED: File exceeded 50k lines]" (this is correct as it's literal text).
    *   **Encoding:** Force UTF-8. On error -> `errors='replace'` (insert replacement char).
    *   **Blacklist:** Skip known "garbage" patterns (e.g., `.min.js` > 1MB).

### B. `ImageStrategy`
*   **Extensions:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`.
*   **Filters (Skip Condition):**
    *   Resolution < 200x200 px.
    *   Size < 30 KB.
    *   *Output:* "Skipped: Image too small/low-res".
*   **Action:** Resize (Max 1024px) -> Send to OCR Engine.

### C. `PDFStrategy`
*   **Extensions:** `.pdf`.
*   **Logic:**
    *   Iterate Pages.
    *   **If Page has Image(s):** Render FULL Page (1024px) -> OCR.
    *   **If Page has NO Images:** Extract Native Text.
    *   Combine all pages into one text block.

### D. `OfficeStrategy` (Excel Explosion)
*   **Reference:** See `reference_implementation_frozen/docs2md/convert.py` -> `process_excel_file`.
*   **Excel (`.xlsx`, `.xls`):**
    *   **Do NOT** flatten into one file.
    *   **Action:** Create a directory named `{filename}_content/`.
    *   **Content:** Create 1 MD file per Sheet: `Sheet1.md`, `Financials.md`.
    *   **Main File:** The main `{filename}.xlsx.md` becomes a Table of Contents linking to the sheet files.
*   **Word/PowerPoint:**
    *   Use `python-docx` / `python-pptx` to extract text.
    *   Fallback: If text extraction fails, treat as "Binary" (or potentially render to PDF -> OCR in future).
    *   *Note:* The old implementation used `libreoffice --headless` to render to PDF. This is robust but requires external dependencies. We stick to python-native for Phase 1.

### E. `PlaceholderStrategy` (Default)
*   **Target:** Binaries (`.exe`, `.iso`, `.zip`), Audio/Video, Emails (`.eml`), Unknown types.
*   **Action:** Write text file: "Skipped: Unsupported file type [EXTENSION]" (this is correct as it's literal text).

## 3. Output Writer
*   **Location:** `Output_Root` + `Relative_Path` + `.md` (or directory for Excel).
*   **Format:**
    ```yaml
    ---
    status: success
    source: original_filename.ext
    processor: strategy_name
    timestamp: 2026-01-22
    ---
    
    ... Content ...
    ```