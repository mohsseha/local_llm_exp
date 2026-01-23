# Ticket 5: Future Email Processing (Placeholder)

**Goal:** Establish the architecture to support "Conversation Threading" for emails (`.eml`, `.msg`) in the future, without implementing the logic now.

## 1. Requirement
*   **Do NOT** implement email parsing in Phase 1.
*   **DO** ensure the `Dispatcher` has a slot for `EmailStrategy`.
*   **Current Action:** The `Dispatcher` should identify `.eml` files and treat them as "Skipped/Pending Implementation" (or use a simple placeholder text file).

## 2. Future Vision (Context for later)
*   **Grouping:** The system will eventually group `.eml` files by `Message-ID` or Subject into a single `.thread.md` file (Conversation View).
*   **Reference:** See `reference_implementation_frozen/docs2md/eml_to_threads.py` for a working implementation of this logic.
*   **Input:** A folder of 50 `.eml` files.
*   **Output:** 1 `.thread.md` file (summarizing the 50 emails).

## 3. Implementation Plan (Phase 1)
*   In `Dispatcher`:
    ```python
    if ext == '.eml':
        return PlaceholderStrategy("Email support coming in v2.0")
    ```
