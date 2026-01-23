# Master Ticket: Intelligent Archival Pipeline (v2.0)

**Goal:** Build a fault-tolerant, resumable, and deduplicated processing pipeline to ingest, classify, and extract text from 20+ years of diverse personal files ("Nerd Archive").

**Core Philosophy:**
1.  **Avoid Work:** Never OCR the same image twice (Global Image Cache). Never process the same file twice (File Hash Deduplication).
2.  **Safety First:** Single-threaded OCR to protect M4 memory. Fail-soft on bad files.
3.  **Data Fidelity:** Prefer native text extraction (PDF layer, Code, Docs) over OCR whenever possible.

---

## 1. Architecture Components

### A. The State Manager (SQLite)
The brain of the operation. It tracks what we've seen to ensure idempotency.
*   **Table `files`:**
    *   `file_path` (PK)
    *   `file_hash` (SHA256 - The true identity)
    *   `mtime` (Fast check for changes)
    *   `status` (`PENDING`, `PROCESSED`, `DUPLICATE`, `FAILED`, `SKIPPED`)
    *   `mime_type` (Detected type)
    *   `error_msg`
*   **Table `image_cache` (Global Deduplication):**
    *   `image_hash` (SHA256 of the pixel data)
    *   `ocr_text` (The expensive result)
    *   `model_version` (To allow future re-runs if models improve)

### B. The Scanner
*   **Logic:**
    1.  Walks target directories.
    2.  **Fast Check:** If `path` + `mtime` + `size` matches DB, skip hashing (assume unchanged).
    3.  **Slow Check:** If changed/new, compute SHA256.
    4.  **Dedupe:** If SHA256 exists in DB (even under a different path), mark as `DUPLICATE` and link to existing result (do not re-process).

### C. The Dispatcher (Pluggable)
Uses `python-magic` (MIME detection) to route files to the correct Strategy.

**Supported Strategies:**
1.  **`CodeStrategy`** (`.py`, `.rs`, `.md`, `.json`, `.txt`):
    *   Action: Read as UTF-8.
2.  **`OfficeStrategy`** (`.docx`, `.pptx`, `.xlsx`, `.odt`):
    *   Action: Extract text via libraries (e.g., `python-docx`).
3.  **`ImageStrategy`** (`.jpg`, `.png`, `.webp`):
    *   Action: Resize -> Check `image_cache` -> OCR if miss -> Save.
4.  **`PDFStrategy`** (Hybrid):
    *   Action: Iterate pages.
    *   **Try Native:** Attempt to extract text layer.
    *   **Fallback:** If text is sparse/garbled -> Render Page to Image -> Check `image_cache` -> OCR.
5.  **`ArchiveStrategy`** (`.zip`, `.tar`):
    *   Action: Log contents (list files) but do not unpack (for now).
6.  **`BinaryStrategy`** (`.exe`, `.bin`):
    *   Action: Skip/Ignore.

### D. The Output
*   **Sidecar Files:** Creates `{filename}.processed.txt` (or `.md`) next to the original file.
*   **Note:** If a file is a `DUPLICATE` of a file in another folder, we create a sidecar file that points to the original or copies the content (User preference: "Save output... so we don't have to process again").

---

## 2. Implementation Phases

### Phase 1: Foundation (Database & Scanner)
*   [ ] Initialize `pipeline.db` (SQLite).
*   [ ] Implement `FileScanner` with `mtime` optimization and SHA256 hashing.
*   [ ] Create basic `Dispatcher` skeleton.

### Phase 2: The Caching Layer
*   [ ] Implement `ImageCache` logic (lookup/insert).
*   [ ] Update `ocr_engine.py` to accept an image hash and check cache before running model.

### Phase 3: Strategy Implementation
*   [ ] **Text/Code:** Simple read.
*   [ ] **Image:** Connect to `ocr_engine`.
*   [ ] **PDF (Hybrid):** Implement the "Native Text vs OCR" decision logic.

### Phase 4: Integration & Robustness
*   [ ] Connect all parts.
*   [ ] Add "Resume" capability (run script again, it picks up where it left off).
*   [ ] Add detailed logging/error handling (Fail-Soft).

---

## 3. Tech Stack
*   **Language:** Python 3.12+
*   **DB:** `sqlite3` (Stdlib)
*   **ORM:** Raw SQL or lightweight wrapper (keep it simple).
*   **MIME:** `python-magic`
*   **PDF:** `pypdf` (Text), `pdf2image` (Rendering).
*   **Office:** `python-docx`, etc.
*   **LLM:** Existing `ocr_engine.py` (MLX Qwen3-VL).

---

## 4. Specific "Nerd File" Considerations
*   **Code:** Treat as text. Don't OCR screenshots of code unless necessary.
*   **Emails:** Parse `.eml` for body text.
*   **Legacy Docs:** Handle encoding errors (latin-1 vs utf-8) gracefully.
