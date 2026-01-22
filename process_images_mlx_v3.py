#!/usr/bin/env python3
"""
Main entry point for Local OCR Pipeline.
Orchestrates file scanning, PDF extraction, and OCR processing using modular components.
"""

import sys
import os
import tempfile
from pathlib import Path
from typing import List

# Suppress HuggingFace Tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import our new modules
import ocr_engine
import pdf_processor

# Constants
IMAGE_DIR = Path("poc_images")

def get_files_to_process(directory: Path) -> List[Path]:
    """Get all JPEG/PNG/PDF files from directory."""
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG", "*.pdf", "*.PDF"]
    files = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))
    
    return sorted(files)

def process_file_item(file_path: Path, temp_dir: Path) -> None:
    """Dispatches processing for a single file (Image or PDF)."""
    
    output_path = file_path.with_suffix(".mlx.txt")
    
    # --- PDF Processing ---
    if file_path.suffix.lower() == '.pdf':
        print(f"📄 Processing PDF: {file_path.name}...")
        
        full_text = []
        
        # Iterate over pages yielded by the helper
        for page_num, page_image in pdf_processor.extract_pdf_pages(file_path):
            
            # Send PIL Image to OCR Engine
            # Note: ocr_engine handles resizing and temp file saving internally
            page_text = ocr_engine.transcribe_image(page_image, temp_dir)
            
            if page_text:
                full_text.append(f"\n--- Page {page_num} ---\n")
                full_text.append(page_text)
        
        # Write results if we got any
        if full_text:
            final_text = "\n".join(full_text)
            output_path.write_text(final_text, encoding="utf-8")
            print(f"  ✅ PDF Saved to {output_path.name}\n")
        else:
            print(f"  ⚠️ No text extracted from PDF.\n")

    # --- Standard Image Processing ---
    else:
        print(f"🖼️ Processing Image: {file_path.name}...")
        
        # Send Path to OCR Engine
        text = ocr_engine.transcribe_image(file_path, temp_dir)
        
        if text:
            output_path.write_text(text, encoding="utf-8")
            print(f"  ✅ Saved to {output_path.name}\n")
        else:
            print(f"  ⚠️ Skipped {file_path.name}\n")


def main() -> None:
    files = get_files_to_process(IMAGE_DIR)
    
    if not files:
        print(f"No matching files found in {IMAGE_DIR}")
        return

    print(f"📋 Found {len(files)} files to process in {IMAGE_DIR}\n")
    
    # Global temp context for the run
    # (Passed down to engine for transient file creation)
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        for file_path in files:
            process_file_item(file_path, temp_dir)

    print(f"{ '='*40}")
    print(f"🎉 Complete.")

if __name__ == "__main__":
    main()
