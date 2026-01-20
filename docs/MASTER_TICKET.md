# Master Ticket: Qwen3-VL OCR Proof of Concept

**Goal:** Verify that **Qwen3-VL** (Strictly Version 3+) can accurately convert receipt/document images into structured Markdown on a Linux CPU server.

**Phase:** 1 (PoC - Linux Only).
**Input:** A manually curated folder of ~10-20 "Representative Images".
**Output:** A matching folder of Markdown files.

### 1. Architecture & Environment

**Environment Path:**
*   Preferred `uv` environment: `/home/husainal-mohssen/default_env`

**Model Architecture (Qwen3-VL Updates):**
*   **Interleaved-MRoPE:** Enhanced spatial/temporal reasoning.
*   **DeepStack:** Fuses multi-level ViT features for fine-grained detail.
*   **Resolution:** Flexible pixel budgets (H x W multiples of 32). Recommended long edge: 1500-2000px.

**Hardware:**
*   **System:** Linux Workstation (64GB RAM).
*   **Compute:** CPU Only.
*   **Constraint:**
    *   Must fit in 64GB RAM.
    *   Target Model: **Qwen3-VL** (32B or 72B GGUF).
    *   **STRICT RULE:** Do NOT use Qwen 2.5 or older. If Qwen 3 is unavailable, STOP.

**Software:**
*   **Manager:** `uv` for dependency/venv management.
*   **Engine:** `llama-cpp-python` (Confirmed Qwen3 support as of Oct 2025).
*   **Model Source:** Official `Qwen/Qwen3-VL-*-GGUF` or reliable community quants.

### 2. Implementation Steps

#### Step 1: Sanity Check (Current Focus)
1.  **Environment Setup:** Initialize `uv` project and install `llama-cpp-python` + `huggingface_hub`.
2.  **Model Identification & Download:**
    *   Identify the largest **Qwen3-VL** GGUF that fits in 64GB RAM.
    *   Download the model + `mmproj` file.
3.  **Resolution Handling:** Ensure scripts account for Qwen3's 16-pixel patch size and 32-pixel rounding.
4.  **Minimal Run:** Create `sanity_check.py` to load the model and generate a text response.

#### Step 2: Functional PoC (Later)
1.  **Image Loader:** Filter for `.jpg`, `.png`. Resize images based on Qwen3-VL specific constraints.
2.  **Prompt Engineering:** Instruct model to output pure Markdown.
3.  **Execution:** Run batch process, saving `{filename}_ocr.md`.

### 3. Model Details

*   **Family:** Qwen3-VL (ONLY).
*   **Likely Candidates:**
    *   `Qwen/Qwen3-VL-32B-Instruct-GGUF`
    *   `Qwen/Qwen3-VL-72B-Instruct-GGUF` (Highly quantized)
*   **Files Needed:**
    *   `.gguf` (Main Model)
    *   `mmproj-model-f16.gguf` (Vision Adapter)

### 4. Definition of Done (Step 1)
1.  Virtual environment created.
2.  **Qwen3-VL** model files present in `./models/`.
3.  `sanity_check.py` runs and prints a response from the Qwen3 model.
