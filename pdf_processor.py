"""
PDF Processing Utilities.

Handles breaking down PDFs into individual page images for processing.
"""

from pathlib import Path
from typing import Iterator, Tuple, Optional
from PIL import Image
from pdf2image import convert_from_path, pdfinfo_from_path

def count_pdf_pages(file_path: Path) -> int:
    """Returns the number of pages in a PDF safely."""
    try:
        info = pdfinfo_from_path(file_path)
        return info["Pages"]
    except Exception as e:
        print(f"    ⚠️ Could not read PDF info for {file_path.name}: {e}")
        return 0

def extract_pdf_pages(file_path: Path) -> Iterator[Tuple[int, Image.Image]]:
    """
    Yields (page_number, PIL.Image) for each page in the PDF.
    
    Processing is done lazily page-by-page to conserve memory.
    """
    num_pages = count_pdf_pages(file_path)
    if num_pages == 0:
        return

    print(f"  • Found {num_pages} pages.")

    for i in range(1, num_pages + 1):
        print(f"  • Processing Page {i}/{num_pages}...")
        try:
            # Convert single page
            # fmt='jpeg' reduces memory vs ppm internally in pdf2image
            pages = convert_from_path(file_path, first_page=i, last_page=i, fmt='jpeg')
            
            if pages:
                yield i, pages[0]
            else:
                print(f"    ⚠️ Failed to extract page {i}")
                
        except Exception as e:
            print(f"    ❌ Error extracting page {i}: {e}")
