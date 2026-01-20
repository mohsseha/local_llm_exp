# Master Ticket: Qwen3-VL OCR Proof of Concept

**Goal:** Verify that **Qwen3-VL** can accurately convert a representative sample of your receipt/document images into structured Markdown.

**Phase:** 1 (PoC only).
**Input:** A manually curated folder of ~10-20 "Representative Images" (mix of clear scans, blurry receipts, simple tables, complex tables).
**Output:** A matching folder of Markdown files for manual inspection.

### 1. Recommended Architecture (PoC)

**Deployment Strategy:**
*   **Recommendation:** Use **`llama-cpp-python`** with the appropriate hardware flags.
*   **Rationale:** Lowest barrier to entry. It allows you to interact with the model directly in Python without managing a separate server architecture.
*   **Constraint:** Must ensure the library is built with **Metal** support on Mac (for speed) and **AVX2** support on Linux (for the old CPU).

**Hardware Assignment:**
*   **Development (Mac M4):** Run the script here first using the **7B** model (Quantized to 4-bit/Q4_K_M).
    *   *Why:* Fast iteration to get the prompt and image handling code right.
*   **Evaluation (Linux Box):** Once the code works, move it to Linux and switch to the **32B** model (Quantized to Q8_0 or Q6_K).
    *   *Why:* The M4 (16GB) cannot fit the high-fidelity 32B model. The Linux box (64GB) is the only place we can verify the "real" accuracy.

### 2. Functional Requirements

1.  **Image Loader:**
    *   Accept a local directory path.
    *   Filter for valid image extensions (`.jpg`, `.png`).
    *   *Note:* Ignore PDFs for this PoC. We will convert your test sample to images manually to isolate variables.
2.  **Resolution Handler:**
    *   **Recommendation:** Resize images so the long edge is approx **1500-2000px**.
    *   *Rationale:* Qwen's vision encoder slices images into 14x14 patches. Too big = slow & potential confusion. Too small = unreadable text.
3.  **The Prompt:**
    *   Must instruct the model to ignore conversational filler ("Here is the text...") and output *only* Markdown.
    *   Must explicitly ask for layout preservation (tables as Markdown tables).
4.  **Output Generation:**
    *   Save file as `{original_filename}_ocr.md`.
    *   (Optional) Save the raw console log to a separate file for debugging model "thought" process.

### 3. Model & Data Links (Reference)

The coding agent should verify the latest model hashes, but these are the standard targets.

*   **The Library:**
    *   [llama-cpp-python Repo](https://github.com/abetlen/llama-cpp-python) - *Installation instructions for Metal (Mac) and OpenBLAS (Linux).*
*   **The Models (HuggingFace):**
    *   *Target Family:* **Qwen/Qwen3-VL-Instruct** (or Qwen2.5-VL if Qwen3 is not found in GGUF format yet).
    *   *Search Query:* `Qwen3-VL-Instruct-GGUF` or `Qwen2.5-VL-72B-Instruct-GGUF` (for the big equivalent).
    *   *Author Reference:* Look for quants by **Qwen** (official) or **Bartowski** (reliable community quantizer).
*   **Vision Projectors:**
    *   *Critical:* These models require a specific "mmproj" (multimodal projector) file to handle images. The agent must download the `.mmproj` file corresponding to the model.

### 4. Definition of Done
1.  Python script `ocr_poc.py` runs without error on the Mac M4.
2.  Script successfully processes a folder of 5 images.
3.  Output Markdown files are generated.
4.  **Manual Review:** You can open the Markdown and the Image side-by-side and confirm the prices/dates match.
