# Ticket 3: OCR Engine Integration

**Goal:** Adapt the existing `ocr_engine.py` to work as a callable library for the new pipeline, respecting the strict memory and resizing constraints.

## 1. Refinements to `ocr_engine.py`

### Interface
The engine needs a clean synchronous API that the `ImageStrategy` and `PDFStrategy` can call.

```python
def process_image_data(image: PIL.Image) -> str:
    """
    1. Resize image (Max 1024px longest side).
    2. Convert to Qwen-compatible format.
    3. Run Inference (Single-threaded).
    4. Return generated text.
    """
```

### Constraints
*   **Singleton:** The model (`Qwen3-VL-8B`) must be loaded *once* at startup and held in memory.
*   **Threading:** The inference call must be protected by a lock (if we ever add parallelism) or strictly run sequentially.
*   **Error Handling:** If `mlx-vlm` throws an OOM or error, catch it, log it, and return `[OCR_FAILED]`. Do not crash the process.

## 2. Dependencies
*   Ensure `mlx`, `mlx-vlm`, `pillow` are available.
*   Verify model path resolution works when called from a different directory (the driver script location).
