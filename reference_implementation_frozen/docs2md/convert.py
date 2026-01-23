#!/usr/bin/env python3
"""
🚀 Super Document to Markdown Converter 🚀

VERSION: 3.0.0
🤖 AI AGENTS: INCREMENT VERSION NUMBER WHEN MODIFYING THIS FILE!
   - Major changes (breaking): X.0.0
   - New features: X.Y.0  
   - Bug fixes/improvements: X.Y.Z

- Converts various document formats to Markdown directly or using an LLM.
- By default, uses pypandoc for direct conversion.
- Can optionally process documents through Google GenAI API.
- Text files are copied as-is with .md extension.
- Results cached based on SHA256 hash of content.
- Fancy colorful logging so you know WTF is happening.
- v2.0.0: Enhanced error logging with full stack traces and worker thread context
"""

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import random
import signal
import subprocess
import sys
import sys
import tempfile
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import colorlog
import pypandoc
import pandas as pd

# Import the new EML converter
from eml_to_threads import EmlToThreadsConverter

# Script version - AI agents must increment when modifying!
SCRIPT_VERSION = "3.5.0"

# Import the Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

# Setup thread-safe logging
def get_thread_id() -> str:
    """Get current thread ID for logging."""
    return f"T{threading.current_thread().ident or 0}"

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s [%(threadName)s:%(thread)d] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger('converter')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Thread-safe logging helper
def log_with_thread(level: str, message: str) -> None:
    """Log message with thread information."""
    thread_info = f"[{get_thread_id()}]"
    getattr(logger, level.lower())(f"{thread_info} {message}")

# Constants
MAX_FILE_SIZE_MB = 20
MAX_PAGES_APPROX = 20
THREADS_FOR_LOCAL_OPS = 4  # Number of threads for local file operations
FILE_PROCESSING_TIMEOUT = 60  # Timeout in seconds for processing any single file

# WARNING: NEVER REINTRODUCE AN EMOJI DICTIONARY!
# All emojis MUST be hard-coded inline to avoid abstraction hell.
# No EMOJI['foo'] bullshit - use the actual emoji characters directly.
# This makes the code more readable and prevents stupid indirection.


def verify_timeout_reliability():
    """Quick verification that timeout mechanism works properly."""
    def slow_function():
        time.sleep(2)  # Sleep longer than our test timeout
        return "should_not_reach_here"
    
    start_time = time.time()
    result = process_file_with_timeout_test(slow_function, timeout=1)  # 1 second timeout
    elapsed = time.time() - start_time
    
    if result is None and elapsed < 1.5:  # Should timeout in ~1 second
        logger.info(f"✅ Timeout mechanism verified: {elapsed:.2f}s")
        return True
    else:
        logger.error(f"❌ Timeout mechanism failed: result={result}, elapsed={elapsed:.2f}s")
        return False

def process_file_with_timeout_test(func, timeout=FILE_PROCESSING_TIMEOUT):
    """Test version of timeout wrapper for verification."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            result = future.result(timeout=timeout)
            return result
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False)
            return None

def process_file_with_timeout(func, *args, **kwargs):
    """Execute file processing function with timeout and complete isolation."""
    file_path = args[0] if args else "unknown_file"
    filename = getattr(file_path, 'name', str(file_path))
    
    # Create a shared container for error details
    error_details = {'exception': None, 'error_msg': None, 'traceback': None}
    
    def run_with_timeout():
        try:
            logger.debug(f"🔒 [{get_thread_id()}] Starting isolated processing: {filename}")
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            if result:
                logger.debug(f"✅ [{get_thread_id()}] Completed in {elapsed:.2f}s: {filename}")
            else:
                logger.debug(f"⚠️ [{get_thread_id()}] Failed processing in {elapsed:.2f}s: {filename}")
            return result
        except Exception as e:
            # THIS IS THE FIX: PRINT THE EXCEPTION DIRECTLY TO STDOUT
            print(f"\n\n🔥🔥🔥 UNHANDLED EXCEPTION IN WORKER THREAD 🔥🔥🔥", file=sys.stdout)
            print(f"--- Processing failed for file: {filename} ---", file=sys.stdout)
            import traceback
            traceback.print_exc(file=sys.stdout)
            print(f"--- End of traceback for {filename} ---\n\n", file=sys.stdout)
            return None
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_with_timeout)
        try:
            logger.debug(f"⏱️ Starting {FILE_PROCESSING_TIMEOUT}s timeout for: {filename}")
            result = future.result(timeout=FILE_PROCESSING_TIMEOUT)
            
            # If result is None and we have error details, log them at the main thread level for visibility
            if result is None and error_details['exception']:
                logger.error(f"🚨 [{get_thread_id()}] FILE_PROCESSING_FAILED: {filename} | Exception: {error_details['exception']} | Error: {error_details['error_msg']}")
            
            return result
        except TimeoutError:
            logger.error(f"⌛ [{get_thread_id()}] TIMEOUT: {filename} | Timeout: {FILE_PROCESSING_TIMEOUT}s exceeded")
            # Attempt to cancel the future 
            cancelled = future.cancel()
            if not cancelled:
                logger.warning(f"⚠️ [{get_thread_id()}] Could not cancel timed-out task: {filename}")
            # Force executor shutdown to prevent zombie threads
            executor.shutdown(wait=False)
            return None
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] TIMEOUT_WRAPPER_FAILURE: {filename} | Exception: {exception_name} | Error: {e}")
            return None


@dataclass
class CacheEntry:
    """Data structure for cache entries."""
    original_filename: str
    cached_on: str
    output_path: str
    file_type: str
    is_large: bool
    conversion_mode: str
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheMetadata:
    """Data structure for cache metadata."""
    created: str
    last_updated: str
    file_count: int


@dataclass
class Cache:
    """Data structure for the entire cache."""
    metadata: CacheMetadata
    files: Dict[str, CacheEntry]


class DocumentConverter:
    """Main converter class with all functionality."""
    
    def __init__(self, api_key: Optional[str], input_dir: Path, output_dir: Path, cache_dir: Path, use_llm: bool = False):
        """Initialize the converter with paths and settings."""
        self.api_key = api_key
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.use_llm = use_llm
        self.client = None
        
        # Thread-safe mechanism for handling EML directories
        self.processed_eml_dirs = set()
        self.eml_dir_lock = threading.Lock()
        self.eml_processing_results = {}  # Store EML processing results for accurate reporting
        
        if self.use_llm:
            if not GOOGLE_GENAI_AVAILABLE:
                logger.critical(f"❌ 'google-generativeai' package not found. Please install it to use LLM mode.")
                sys.exit(1)
            if not self.api_key:
                logger.critical(f"❌ GEMINI_API_KEY must be set to use LLM mode.")
                sys.exit(1)
            self.client = self._setup_client()
        
        self.cache = self._init_cache()
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create required directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🚀 Initialized converter v{SCRIPT_VERSION}")
        logger.info(f"ℹ️ Input directory: {self.input_dir}")
        logger.info(f"ℹ️ Output directory: {self.output_dir}")
        logger.info(f"ℹ️ Cache directory: {self.cache_dir}")
        logger.info(f"ℹ️ Temp directory: {self.temp_dir}")
        logger.info(f"ℹ️ Conversion mode: {'LLM-based' if self.use_llm else 'Direct (pandoc)'}")
        
        # Verify timeout mechanism reliability
        logger.info(f"⏱️ Verifying timeout mechanism reliability...")
        if verify_timeout_reliability():
            logger.info(f"🔒 Timeout mechanism is working correctly")
        else:
            logger.info(f"ℹ️ Timeout verification inconclusive. This is common in some containerized environments. Proceeding, but individual file hangs may not be preventable.")

    def _setup_client(self) -> Any:
        """Initialize the GenAI client with the provided API key."""
        try:
            client = genai.Client(api_key=self.api_key)
            logger.info(f"✅ Google GenAI client initialized")
            return client
        except Exception as e:
            logger.critical(f"❌ Failed to initialize Google GenAI client: {e}")
            sys.exit(1)
    
    def _init_cache(self) -> Cache:
        """Initialize and return cache data structure."""
        cache_file = self.cache_dir / "cache_index.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    metadata = CacheMetadata(**cache_data.get('metadata', {}))
                    files = {k: CacheEntry(**v) for k, v in cache_data.get('files', {}).items()}
                    cache = Cache(metadata=metadata, files=files)
                    logger.info(f"✅ Loaded cache with {len(files)} entries")
                    return cache
            except Exception as e:
                logger.warning(f"⚠️ Cache file exists but could not be read: {e}")
        
        metadata = CacheMetadata(created=datetime.now().isoformat(), last_updated=datetime.now().isoformat(), file_count=0)
        cache = Cache(metadata=metadata, files={})
        self._save_cache(cache)
        logger.info(f"ℹ️ Created new cache")
        return cache
    
    def _save_cache(self, cache: Cache) -> None:
        """Save cache data structure to disk."""
        cache_file = self.cache_dir / "cache_index.json"
        cache.metadata.last_updated = datetime.now().isoformat()
        cache.metadata.file_count = len(cache.files)
        cache_dict = {"metadata": asdict(cache.metadata), "files": {k: asdict(v) for k, v in cache.files.items()}}
        
        with tempfile.NamedTemporaryFile(mode='w', dir=self.cache_dir, delete=False) as tmp:
            json.dump(cache_dict, tmp, indent=2)
            tmp_path = tmp.name
        
        Path(tmp_path).rename(cache_file)
        logger.debug(f"💾 Cache saved with {cache.metadata.file_count} entries")
    
    def get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content for caching."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] FILE_HASH_FAILED: {file_path.name} | Exception: {exception_name} | Error: {e}")
            return f"ERROR_HASH_{datetime.now().isoformat()}"
    
    def get_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        ext = file_path.suffix.lower()
        if ext == '.eml':
            return 'eml'
        if ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.css', '.js', '.py', '.c', '.cpp', '.java', '.go', '.rb', '.sh']:
            return 'text'
        if ext == '.pdf':
            return 'pdf'
        if ext in ['.doc', '.docx', '.rtf', '.odt']:
            return 'word'
        if ext in ['.xls', '.xlsx', '.ods']:
            return 'excel'
        if ext in ['.ppt', '.pptx', '.odp']:
            return 'powerpoint'
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif']:
            return 'image'
        return 'other'
    
    def is_large_file(self, file_path: Path) -> Tuple[bool, str]:
        """Check if file is large."""
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                return True, f"File size ({file_size_mb:.1f}MB) exceeds {MAX_FILE_SIZE_MB}MB limit"
            if file_path.suffix.lower() == '.pdf':
                page_estimate = int(file_size_mb / 0.5)
                if page_estimate > MAX_PAGES_APPROX:
                    return True, f"Estimated page count ({page_estimate}) exceeds {MAX_PAGES_APPROX} pages"
        except Exception as e:
            exception_name = type(e).__name__
            logger.warning(f"⚠️ [{get_thread_id()}] FILE_SIZE_CHECK_FAILED: {file_path.name} | Exception: {exception_name} | Error: {e}")
            return False, ""
        return False, ""

    def direct_convert_to_md(self, input_file: Path, output_path: Path) -> bool:
        """Convert file to Markdown using Pandoc."""
        logger.info(f"🐼 Converting {input_file.name} to Markdown using Pandoc...")
        try:
            pypandoc.convert_file(str(input_file), 'markdown', outputfile=str(output_path))
            logger.info(f"✅ Successfully converted {input_file.name} with Pandoc.")
            return True
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] PANDOC_FAILED: {input_file.name} | Exception: {exception_name} | Error: {e}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Pandoc Conversion Error\n\n**File:** `{input_file.name}`\n\n**Error:**\n```\n{e}\n```\n")
            return False

    def convert_to_pdf_llm(self, input_file: Path) -> Optional[Path]:
        """Convert office/image files to PDF for LLM processing."""
        output_filename = f"{input_file.stem}_{int(time.time())}.pdf"
        output_path = self.temp_dir / output_filename
        file_type = self.get_file_type(input_file)
        
        logger.info(f"🔄 Converting {input_file.name} to PDF for LLM...")
        
        try:
            if file_type == 'image':
                cmd = ['convert', str(input_file), str(output_path)]
                timeout = 60
            else: # office
                cmd = ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', str(self.temp_dir), str(input_file)]
                timeout = 300

            process = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
            
            if process.returncode != 0:
                logger.error(f"❌ PDF conversion failed for {input_file.name}: {process.stderr}")
                return None

            if file_type != 'image':
                expected_output = self.temp_dir / f"{input_file.stem}.pdf"
                if expected_output.exists():
                    expected_output.rename(output_path)
                else: # Search for any PDF created
                    for pdf_file in self.temp_dir.glob("*.pdf"):
                        if pdf_file.stat().st_mtime > input_file.stat().st_mtime:
                            pdf_file.rename(output_path)
                            break
            
            if output_path.exists():
                logger.info(f"✅ Converted {input_file.name} to PDF for LLM.")
                return output_path
            
            logger.error(f"❌ PDF not created for {input_file.name}")
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"⏱ [{get_thread_id()}] PDF_CONVERSION_TIMEOUT: {input_file.name} | Timeout: {timeout}s")
            return None
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] PDF_CONVERSION_FAILED: {input_file.name} | Exception: {exception_name} | Error: {e}")
            return None

    def process_text_file(self, file_path: Path, output_path: Path) -> bool:
        """Process a text file by copying content with minimal formatting."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            markdown = f"# {file_path.name}\n\n```\n{content}\n```\n"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            logger.info(f"✅ Processed text file: {file_path.name}")
            return True
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] TEXT_PROCESSING_FAILED: {file_path.name} | Exception: {exception_name} | Error: {e}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Error Processing {file_path.name}\n\n**Error:** {str(e)}\n")
            return False

    def process_excel_file(self, file_path: Path, output_dir: Path = None) -> List[Path]:
        """Process Excel file with multiple sheets into separate markdown files."""
        output_files = []
        filename_base = file_path.stem
        target_dir = output_dir if output_dir is not None else self.output_dir
        
        try:
            # Read all sheets from Excel file
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            logger.info(f"ℹ️ Found {len(sheet_names)} sheets in {file_path.name}: {sheet_names}")
            
            for sheet_name in sheet_names:
                # Create output filename: original_filename_sheetname.md
                clean_sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).strip()
                if not clean_sheet_name:
                    clean_sheet_name = f"Sheet{sheet_names.index(sheet_name) + 1}"
                
                output_filename = f"{filename_base}_{clean_sheet_name}.md"
                output_path = target_dir / output_filename
                
                try:
                    # Read the specific sheet
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # Convert DataFrame to markdown
                    markdown_content = f"# {file_path.name} - {sheet_name}\n\n"
                    
                    if df.empty:
                        markdown_content += "*This sheet is empty.*\n"
                    else:
                        # Convert DataFrame to markdown table
                        markdown_table = df.to_markdown(index=False)
                        markdown_content += f"{markdown_table}\n"
                        
                        # Add some stats
                        markdown_content += "\n\n---\n\n**Sheet Statistics:**\n"
                        markdown_content += f"- Rows: {len(df)}\n"
                        markdown_content += f"- Columns: {len(df.columns)}\n"
                        markdown_content += f"- Column Names: {', '.join(str(col) for col in df.columns)}\n"
                    
                    # Write to output file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    output_files.append(output_path)
                    logger.info(f"✅ Processed sheet '{sheet_name}' -> {output_filename}")
                    
                except Exception as e:
                    exception_name = type(e).__name__
                    logger.error(f"💥 [{get_thread_id()}] EXCEL_SHEET_FAILED: {file_path.name} | Sheet: {sheet_name} | Exception: {exception_name} | Error: {e}")
                    # Create error file for this sheet
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(f"# Error Processing Sheet: {sheet_name}\n\n**File:** `{file_path.name}`\n\n**Sheet:** `{sheet_name}`\n\n**Error:**\n```\n{e}\n```\n")
                    output_files.append(output_path)
            
            return output_files
            
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] EXCEL_FILE_FAILED: {file_path.name} | Exception: {exception_name} | Error: {e}")
            # Create single error file
            error_output = target_dir / f"{filename_base}.md"
            with open(error_output, 'w', encoding='utf-8') as f:
                f.write(f"# Error Processing Excel File\n\n**File:** `{file_path.name}`\n\n**Error:**\n```\n{e}\n```\n")
            return [error_output]
    
    def process_with_api(self, file_path: Path, output_path: Path) -> Tuple[bool, Dict[str, Any]]:
        """Process a file using the Google GenAI API with retry logic."""
        stats = {"start_time": datetime.now().isoformat(), "file_size_mb": file_path.stat().st_size / (1024 * 1024), "uncertainty_detected": False, "retries": 0}
        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"🤖 Sending {file_path.name} to Google GenAI API (Attempt {attempt + 1})")
                
                start_time = time.time()
                uploaded_file = self.client.files.upload(file=str(file_path))
                stats["upload_time"] = time.time() - start_time
                
                contents = [types.Content(role="user", parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                    types.Part.from_text(text="Convert this document to a markdown document. If you're uncertain about any content, include 'UNCERTAIN_CONVERSION' at the beginning of your response.")
                ])]
                
                model = "models/gemini-1.5-pro-latest"
                config = types.GenerateContentConfig(temperature=1, top_p=0.95, top_k=64, max_output_tokens=8192, response_mime_type="text/plain")
                
                api_start_time = time.time()
                response = self.client.models.generate_content(model=model, contents=contents, config=config)
                stats["api_time"] = time.time() - api_start_time
                
                if hasattr(response, 'text'):
                    markdown_text = response.text
                    if markdown_text.strip().startswith("UNCERTAIN_CONVERSION"):
                        stats["uncertainty_detected"] = True
                        markdown_text = markdown_text.replace("UNCERTAIN_CONVERSION", "", 1).strip()
                        logger.warning(f"⚠️ Uncertainty detected in conversion of {file_path.name}")
                        markdown_text = "⚠️ **CONVERSION UNCERTAINTY WARNING** ⚠️\n\n---\n\n" + markdown_text
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_text)
                    
                    stats["end_time"] = datetime.now().isoformat()
                    logger.info(f"✅ Successfully converted {file_path.name} via API")
                    return True, stats
                else:
                    raise Exception("No text in API response")

            except Exception as e:
                error_msg = str(e)
                if "RESOURCE_EXHAUSTED" in error_msg and attempt < max_retries - 1:
                    delay = (base_delay ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⚠️ Rate limit hit for {file_path.name}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    stats["retries"] = attempt + 1
                    continue
                else:
                    exception_name = type(e).__name__ if 'e' in locals() else 'APIError'
                    logger.error(f"💥 [{get_thread_id()}] API_PROCESSING_FAILED: {file_path.name} | Exception: {exception_name} | Error: {error_msg}")
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(f"# API Conversion Error\n\n**Error:** {error_msg}\n")
                    stats["error"] = error_msg
                    stats["end_time"] = datetime.now().isoformat()
                    return False, stats
        return False, stats
    
    def store_in_cache(self, file_hash: str, original_path: Path, output_path: Path, 
                     file_type: str, is_large: bool, stats: Dict[str, Any]) -> None:
        """Store processed file result in cache."""
        cache_entry = CacheEntry(
            original_filename=original_path.name,
            cached_on=datetime.now().isoformat(),
            output_path=str(output_path),
            file_type=file_type,
            is_large=is_large,
            conversion_mode='llm' if self.use_llm else 'direct',
            stats=stats
        )
        self.cache.files[file_hash] = cache_entry
        cache_content_path = self.cache_dir / f"{file_hash}.md"
        try:
            with open(output_path, 'r', encoding='utf-8') as src_file:
                content = src_file.read()
            with open(cache_content_path, 'w', encoding='utf-8') as dst_file:
                dst_file.write(content)
            logger.debug(f"💾 Saved content to cache: {file_hash}.md")
        except Exception as e:
            exception_name = type(e).__name__
            logger.warning(f"⚠️ [{get_thread_id()}] CACHE_SAVE_FAILED | Exception: {exception_name} | Error: {e}")
        self._save_cache(self.cache)
    
    def get_from_cache(self, file_hash: str, output_path: Path) -> bool:
        """Retrieve cached result if available, checking conversion mode."""
        if file_hash not in self.cache.files:
            return False
        
        entry = self.cache.files[file_hash]
        current_mode = 'llm' if self.use_llm else 'direct'
        if entry.conversion_mode != current_mode:
            logger.info(f"🔍 Cache entry found, but for different mode ('{entry.conversion_mode}'). Re-processing in '{current_mode}' mode.")
            return False

        cache_content_path = self.cache_dir / f"{file_hash}.md"
        if not cache_content_path.exists():
            logger.warning(f"⚠️ Cache entry exists but content file missing: {file_hash}")
            return False
        
        try:
            with open(cache_content_path, 'r', encoding='utf-8') as src_file:
                content = src_file.read()
            with open(output_path, 'w', encoding='utf-8') as dst_file:
                dst_file.write(content)
            logger.info(f"🎯 Using cached version for {output_path.name} ({current_mode} mode)")
            return True
        except Exception as e:
            exception_name = type(e).__name__
            logger.warning(f"⚠️ [{get_thread_id()}] CACHE_RETRIEVAL_FAILED | Exception: {exception_name} | Error: {e}")
            return False
    
    def process_file(self, file_path: Path) -> Optional[Path]:
        """Process a single file with complete isolation and timeout protection."""
        try:
            file_type = self.get_file_type(file_path)

            if file_type == 'eml':
                return self._process_eml_file_isolated(file_path)
            else:
                return self._process_regular_file_isolated(file_path)
                
        except Exception as e:
            exception_name = type(e).__name__
            import traceback
            tb = traceback.format_exc()
            logger.error(f"💥 [{get_thread_id()}] COMPLETE_FAILURE: {file_path.name} | Exception: {exception_name} | Error: {e}")
            logger.error(f"💥 [{get_thread_id()}] COMPLETE_FAILURE_TRACEBACK for {file_path.name}:\n{tb}")
            
            # IMMEDIATE WORKER CONTEXT: Log this failure so main thread knows what happened
            logger.error(f"🎯 [{get_thread_id()}] WORKER_THREAD_FAILURE_SUMMARY: File '{file_path.name}' completely failed in worker thread - main thread will show 'Worker returned None'")
            return None
    
    def _process_eml_file_isolated(self, file_path: Path) -> Optional[Path]:
        """Process .eml file with complete isolation - failures won't affect other files."""
        try:
            eml_dir = file_path.parent
            with self.eml_dir_lock:
                if eml_dir in self.processed_eml_dirs:
                    # This directory has already been processed by another thread
                    # Return a success indicator since EML processing was successful
                    return Path("_eml_already_processed_successfully")
                # Mark this directory as processed
                self.processed_eml_dirs.add(eml_dir)
            
            logger.info(f"📧 Processing .eml files in directory: {eml_dir.relative_to(self.input_dir)}")
            
            try:
                relative_dir = eml_dir.relative_to(self.input_dir)
                output_eml_dir = self.output_dir / relative_dir
                converter = EmlToThreadsConverter(eml_dir, output_eml_dir)
                result = converter.convert()
                
                # Store EML processing results for accurate reporting
                with self.eml_dir_lock:
                    self.eml_processing_results[eml_dir] = result
                
                # Enhanced EML conversion results logging with stack traces
                if result['failed_files'] > 0:
                    logger.warning(f"🚨 [{get_thread_id()}] EML_PARTIAL_SUCCESS: {eml_dir.name} | Success: {result['successful_files']}/{result['total_files']} | Failed: {result['failed_files']}")
                    # Log ALL failures with full details for debugging
                    for i, failure in enumerate(result.get('failures', [])):
                        exc_name = failure.get('exception', 'Unknown')
                        error_msg = failure.get('error', 'Unknown error')
                        file_name = failure.get('file', 'unknown_file')
                        traceback_info = failure.get('traceback', 'No traceback available')
                        
                        logger.error(f"💥 [{get_thread_id()}] EML_FAILURE_DETAIL_{i+1}: {file_name} | Exception: {exc_name} | Error: {error_msg}")
                        logger.error(f"💥 [{get_thread_id()}] EML_STACK_TRACE_{i+1} for {file_name}:\n{traceback_info}")
                        
                        # Break down common error patterns for easier debugging
                        if 'NO_VALID_PAYLOAD' in str(error_msg):
                            logger.error(f"📎 [{get_thread_id()}] PAYLOAD_ISSUE: {file_name} has attachment payload problems - check Content-Transfer-Encoding and base64 decoding")
                        elif 'EML_PARSING_FAILED' in str(error_msg):
                            logger.error(f"📎 [{get_thread_id()}] PARSING_ISSUE: {file_name} has email structure problems - malformed headers or body")
                        elif 'ATTACHMENT_EXTRACTION_FAILED' in str(error_msg):
                            logger.error(f"📎 [{get_thread_id()}] ATTACHMENT_ISSUE: {file_name} has attachment processing problems - check filename encoding or content")
                else:
                    logger.info(f"✅ [{get_thread_id()}] EML_COMPLETE_SUCCESS: {eml_dir.name} | All {result['total_files']} files processed")
                
                # We return a dummy path to indicate success for the progress bar
                return Path(output_eml_dir) / "_eml_conversion_success"
            except Exception as e:
                import traceback
                import sys
                print(f"--- START OF DETAILED TRACEBACK FOR {eml_dir.name} ---")
                traceback.print_exc(file=sys.stdout)
                print(f"--- END OF DETAILED TRACEBACK FOR {eml_dir.name} ---")
                exception_name = type(e).__name__
                tb = traceback.format_exc()
                logger.error(f"💥 [{get_thread_id()}] EML_PROCESSING_FAILED: {eml_dir.name} | Exception: {exception_name} | Error: {e}")
                logger.error(f"💥 [{get_thread_id()}] EML_PROCESSING_TRACEBACK for {eml_dir.name}:\n{tb}")
                
                # IMMEDIATE WORKER CONTEXT: Log this failure so it shows up in stdout before main thread sees None
                logger.error(f"🎯 [{get_thread_id()}] WORKER_THREAD_FAILURE_SUMMARY: EML directory '{eml_dir.name}' processing completely failed - main thread will show 'Worker returned None' for this")
                
                # Don't return None here - we want to continue processing other file types in this directory
                return None
                
        except Exception as e:
            exception_name = type(e).__name__
            import traceback
            tb = traceback.format_exc()
            logger.error(f"💥 [{get_thread_id()}] EML_ISOLATION_FAILURE: {file_path.name} | Exception: {exception_name} | Error: {e}")
            logger.error(f"💥 [{get_thread_id()}] EML_ISOLATION_TRACEBACK for {file_path.name}:\n{tb}")
            
            # IMMEDIATE WORKER CONTEXT: Log this isolation failure
            logger.error(f"🎯 [{get_thread_id()}] WORKER_THREAD_FAILURE_SUMMARY: EML file '{file_path.name}' failed during isolation - main thread will show 'Worker returned None'")
            return None
    
    def _process_regular_file_isolated(self, file_path: Path) -> Optional[Path]:
        """Process regular (non-.eml) file with complete isolation."""
        try:
            file_type = self.get_file_type(file_path)
            filename = file_path.name
            
            try:
                relative_path = file_path.relative_to(self.input_dir)
                output_path = self.output_dir / f"{relative_path}.md"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            except ValueError:
                output_path = self.output_dir / f"{filename}.md"
            
            if filename.startswith('.') or file_path.is_dir():
                return None
            
            file_hash = self.get_file_hash(file_path)
            if self.get_from_cache(file_hash, output_path):
                return output_path
            
            logger.info(f"🔍 Processing new file: {filename}")
            
            is_large, large_file_reason = self.is_large_file(file_path)
            if is_large:
                logger.warning(f"⚠️ Large file detected: {filename} - {large_file_reason}")
            
            # WARNING: Never use EMOJI dictionary here - hard-code emojis based on file type
            file_emoji = {'pdf': '📑', 'text': '📝', 'word': '📄', 'excel': '📊', 'eml': '📧'}.get(file_type, '📄')
            logger.info(f"{file_emoji} Processing: {filename} (Type: {file_type})")
            
            success = False
            stats = {}
            
            if file_type == 'text':
                success = self.process_text_file(file_path, output_path)
            elif self.use_llm:
                if file_type in ['word', 'excel', 'powerpoint', 'image', 'pdf']:
                    pdf_path = self.convert_to_pdf_llm(file_path) if file_type != 'pdf' else file_path
                    if pdf_path:
                        success, stats = self.process_with_api(pdf_path, output_path)
                        if pdf_path != file_path:
                            try:
                                pdf_path.unlink()
                            except Exception:
                                pass
                    else:
                        with open(output_path, 'w') as f:
                            f.write(f"# Conversion Error\n\nFailed to prepare `{filename}` for LLM processing.\n")
                        success = False
                else:
                    with open(output_path, 'w') as f:
                        f.write(f"# Unsupported File Type\n\n`{filename}` is not supported in LLM mode.\n")
                    success = False
            else:
                if file_type in ['word', 'powerpoint']:
                    success = self.direct_convert_to_md(file_path, output_path)
                elif file_type == 'excel':
                    output_files = self.process_excel_file(file_path, output_path.parent)
                    if output_files:
                        with open(output_path, 'w') as f:
                            f.write(f"# {filename}\n\n")
                            f.write(f"This Excel file has been converted into {len(output_files)} separate markdown files:\n\n")
                            for output_file in output_files:
                                relative_name = output_file.name
                                f.write(f"- [{relative_name}](./{relative_name})\n")
                        success = True
                    else:
                        success = False
                elif file_type in ['pdf', 'image']:
                    with open(output_path, 'w') as f:
                        f.write(f"# {file_type.capitalize()} File\n\n`{filename}`\n\n**Note:** {file_type.capitalize()} content is not extracted in direct conversion mode.\n")
                    success = True
                else:
                    with open(output_path, 'w') as f:
                        f.write(f"# Unsupported File Type\n\n`{filename}` cannot be converted directly.\n")
                    success = False

            if success:
                self.store_in_cache(file_hash, file_path, output_path, file_type, is_large, stats)
            
            return output_path if success else None
            
        except Exception as e:
            exception_name = type(e).__name__
            logger.error(f"💥 [{get_thread_id()}] REGULAR_FILE_PROCESSING_ERROR: {file_path.name} | Exception: {exception_name} | Error: {e}")
            return None
    
    def run(self) -> None:
        """Main entry point to run the converter on all files."""
        start_time = time.time()
        logger.info(f"🚀 Starting bulletproof document conversion process")
        logger.info(f"🔒 File processing timeout: {FILE_PROCESSING_TIMEOUT}s per file")
        logger.info(f"🔒 Thread isolation: {THREADS_FOR_LOCAL_OPS} parallel workers")
        
        # Counters for detailed tracking
        successful_count = 0
        failed_count = 0
        timeout_count = 0
        skipped_count = 0
        
        # Track statistics by file type
        file_type_stats = {}  # {file_type: {'total': X, 'success': Y, 'failed': Z, 'failed_files': []}}
        
        try:
            all_files = [f for f in self.input_dir.rglob('*') if f.is_file() and not f.name.startswith('.')] # Exclude hidden files
            if not all_files:
                logger.warning(f"⚠️ No files found in {self.input_dir}")
                with open(self.output_dir / "no_files_found.md", 'w') as f:
                    f.write("# No files were found to convert\n")
                logger.info(f"🎉 Process complete - no files to process")
                return
            
            # Pre-analyze file types for statistics
            for file_path in all_files:
                file_type = self.get_file_type(file_path)
                if file_type not in file_type_stats:
                    file_type_stats[file_type] = {'total': 0, 'success': 0, 'failed': 0, 'failed_files': []}
                file_type_stats[file_type]['total'] += 1
            
            logger.info(f"Found {len(all_files)} files to process")
            file_types_summary = ', '.join([f'{k}({v["total"]})' for k, v in file_type_stats.items()])
            logger.info(f"File types: {file_types_summary}")
            logger.info(f"Starting parallel processing with bulletproof isolation...")
            
            with ThreadPoolExecutor(max_workers=THREADS_FOR_LOCAL_OPS) as executor:
                # Submit each file with timeout wrapper for complete isolation
                future_to_file = {
                    executor.submit(process_file_with_timeout, self.process_file, f): f 
                    for f in all_files
                }
                
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_file):
                    completed_count += 1
                    file = future_to_file[future]
                    
                    # Track file type for this specific file
                    file_type = self.get_file_type(file)
                    
                    try:
                        result = future.result()
                        if result:
                            successful_count += 1
                            file_type_stats[file_type]['success'] += 1
                            # Special logging for EML files
                            if file_type == 'eml':
                                if "already_processed" in str(result):
                                    logger.info(f"✅ [{get_thread_id()}] EML_BATCH_PROCESSED: {file.name} | Type: {file_type} | [{completed_count}/{len(all_files)}] (part of batch)")
                                else:
                                    logger.info(f"✅ [{get_thread_id()}] EML_BATCH_SUCCESS: {file.name} | Type: {file_type} | [{completed_count}/{len(all_files)}] (batch completed)")
                            else:
                                logger.info(f"✅ [{get_thread_id()}] SUCCESS: {file.name} | Type: {file_type} | [{completed_count}/{len(all_files)}]")
                        else:
                            failed_count += 1
                            file_type_stats[file_type]['failed'] += 1
                            file_type_stats[file_type]['failed_files'].append(file.name)
                            # Enhanced failure logging - try to get more context about what went wrong
                            logger.error(f"🚨 [{get_thread_id()}] PROCESSING_FAILED: {file.name} | Type: {file_type} | [{completed_count}/{len(all_files)}] | Worker returned None - check error logs above for specific failure details")
                            
                            # Add extra context for EML files since they process multiple files
                            if file_type == 'eml':
                                logger.error(f"💥 [{get_thread_id()}] EML_CONTEXT: {file.name} represents a directory of EML files - individual file failures may be logged separately above")
                            
                        # Progress updates every 5 files or at completion
                        if completed_count % 5 == 0 or completed_count == len(all_files):
                            progress_percent = (completed_count / len(all_files)) * 100
                            logger.info(f"📊 Progress: {completed_count}/{len(all_files)} ({progress_percent:.1f}%) - ✅{successful_count} ❌{failed_count}")
                            
                    except Exception as e:
                        failed_count += 1
                        file_type_stats[file_type]['failed'] += 1
                        file_type_stats[file_type]['failed_files'].append(file.name)
                        exception_name = type(e).__name__
                        import traceback
                        tb = traceback.format_exc()
                        logger.error(f"💥 [{get_thread_id()}] ISOLATION_FAILURE: {file.name} | Type: {file_type} | Exception: {exception_name} | Error: {e} | [{completed_count}/{len(all_files)}]")
                        logger.error(f"💥 [{get_thread_id()}] TRACEBACK for isolation failure {file.name}:\n{tb}")
                        # Continue processing other files regardless of this failure

            # Fix EML statistics using actual EML processing results
            if 'eml' in file_type_stats and self.eml_processing_results:
                # Reset EML stats to use actual processing results instead of misleading file counts
                eml_total_files = 0
                eml_successful_files = 0
                eml_failed_files = 0
                eml_failed_file_names = []
                
                for eml_dir, result in self.eml_processing_results.items():
                    eml_total_files += result['total_files']
                    eml_successful_files += result['successful_files']
                    eml_failed_files += result['failed_files']
                    # Add individual failed EML file names for debugging
                    for failure in result.get('failures', []):
                        eml_failed_file_names.append(failure.get('file', 'unknown_file'))
                
                # Update the statistics with corrected EML numbers
                old_eml_success = file_type_stats['eml']['success']
                old_eml_failed = file_type_stats['eml']['failed']
                
                # Correct the overall success/failed counts
                successful_count = successful_count - old_eml_success + eml_successful_files
                failed_count = failed_count - old_eml_failed + eml_failed_files
                
                # Update EML-specific stats to reflect actual processing
                file_type_stats['eml']['success'] = eml_total_files if eml_failed_files == 0 else eml_successful_files
                file_type_stats['eml']['failed'] = 0 if eml_failed_files == 0 else eml_failed_files
                file_type_stats['eml']['failed_files'] = eml_failed_file_names if eml_failed_files > 0 else []
                
                logger.info(f"📧 EML Statistics Corrected: {eml_total_files} total EML files, {eml_successful_files} successful, {eml_failed_files} failed")
            
            # Create comprehensive summary
            total_processed = len(all_files)
            elapsed_time = time.time() - start_time
            success_rate = (successful_count / total_processed) * 100 if total_processed > 0 else 0
            
            # Log final summary to screen
            logger.info(f"📋 ==================== FINAL SUMMARY ====================")
            logger.info(f"🎉 Processing COMPLETE! Total time: {elapsed_time:.2f} seconds")
            logger.info(f"📊 Files processed: {total_processed}")
            logger.info(f"✅ Successful: {successful_count} ({success_rate:.1f}%)")
            logger.info(f"❌ Failed: {failed_count}")
            
            # File type breakdown table for console
            logger.info(f"📋 FILE TYPE BREAKDOWN:")
            logger.info(f"{'Type':<12} {'Total':<6} {'Success':<8} {'Failed':<7} {'Success %':<10}")
            logger.info(f"{'-'*12} {'-'*6} {'-'*8} {'-'*7} {'-'*10}")
            for file_type, stats in sorted(file_type_stats.items()):
                type_success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
                logger.info(f"{file_type:<12} {stats['total']:<6} {stats['success']:<8} {stats['failed']:<7} {type_success_rate:<10.1f}%")
                
                # Show up to 3 failed files per type for quick debugging
                if stats['failed_files']:
                    failed_examples = stats['failed_files'][:3]  # Show max 3 examples
                    examples_str = ', '.join(failed_examples)
                    if len(stats['failed_files']) > 3:
                        examples_str += f" (+{len(stats['failed_files'])-3} more)"
                    logger.error(f"🚨 Failed {file_type} files: {examples_str}")
            
            logger.info(f"🔒 Conversion mode: {'LLM-based' if self.use_llm else 'Direct (pandoc)'}")
            logger.info(f"⏱️ Timeout setting: {FILE_PROCESSING_TIMEOUT}s per file")
            logger.info(f"🔒 Thread isolation: ENABLED ({THREADS_FOR_LOCAL_OPS} workers)")
            logger.info(f"📋 ===================================================")
            
            # Create detailed summary file
            with open(self.output_dir / "_conversion_summary.md", 'w') as f:
                f.write("# 📋 Bulletproof Document Conversion Summary\n\n")
                f.write(f"**Conversion completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"## 📊 Statistics\n\n")
                f.write(f"* 🕒 **Total processing time:** {elapsed_time:.2f} seconds\n")
                f.write(f"* 📁 **Total files found:** {total_processed}\n")
                f.write(f"* ✅ **Successfully processed:** {successful_count} ({success_rate:.1f}%)\n")
                f.write(f"* ❌ **Failed processing:** {failed_count}\n\n")
                
                # Add file type breakdown table
                f.write(f"## 📊 Processing Results by File Type\n\n")
                f.write("| File Type | Total Files | ✅ Success | ❌ Failed | Success Rate |\n")
                f.write("|-----------|-------------|------------|-----------|---------------|\n")
                for file_type, stats in sorted(file_type_stats.items()):
                    type_success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
                    f.write(f"| **{file_type}** | {stats['total']} | {stats['success']} | {stats['failed']} | {type_success_rate:.1f}% |\n")
                f.write("\n")
                
                # Add failed files section for debugging
                failed_files_exist = any(stats['failed_files'] for stats in file_type_stats.values())
                if failed_files_exist:
                    f.write("## 🚨 Failed Files by Type\n\n")
                    f.write("*Files that failed processing (for debugging):*\n\n")
                    for file_type, stats in sorted(file_type_stats.items()):
                        if stats['failed_files']:
                            f.write(f"### {file_type.capitalize()} Files ({len(stats['failed_files'])} failed)\n\n")
                            for failed_file in stats['failed_files'][:10]:  # Show max 10 per type
                                f.write(f"- `{failed_file}`\n")
                            if len(stats['failed_files']) > 10:
                                f.write(f"- *...and {len(stats['failed_files'])-10} more*\n")
                            f.write("\n")
                    f.write("\n")
                
                f.write(f"## ⚙️ Configuration\n\n")
                f.write(f"* 🤖 **Conversion mode:** {'LLM-based (Google GenAI)' if self.use_llm else 'Direct conversion (pandoc)'}\n")
                f.write(f"* ⏱️ **Timeout per file:** {FILE_PROCESSING_TIMEOUT} seconds\n")
                f.write(f"* 🛡️ **Thread isolation:** Enabled\n")
                f.write(f"* 🔧 **Parallel workers:** {THREADS_FOR_LOCAL_OPS}\n")
                f.write(f"* 🔒 **Bulletproof mode:** Active (individual file failures isolated)\n\n")
                if failed_count == 0:
                    f.write("## 🎉 Perfect Success!\n\nAll files were processed successfully with no failures.\n")
                elif success_rate >= 80:
                    f.write("## ✅ Good Success Rate\n\nMost files processed successfully. Failed files are listed above for debugging.\n")
                else:
                    f.write("## ⚠️ Mixed Results\n\nSome files failed processing. Check failed files section above and use these commands to debug:\n\n")
                    f.write("```bash\n")
                    f.write("# Search for specific error types:\n")
                    f.write("grep '🚨.*FAILED' logs.txt\n")
                    f.write("grep '💥.*ISOLATION_FAILURE' logs.txt\n")
                    f.write("\n# Filter by file type:\n")
                    f.write("grep 'Type: eml' logs.txt\n")
                    f.write("\n# Find specific exceptions:\n")
                    f.write("grep 'Exception:' logs.txt\n")
                    f.write("```\n")
            
            # Final success message
            if successful_count == total_processed:
                logger.info(f"🎉 PERFECT RUN! All {total_processed} files processed successfully! 🎉")
            else:
                logger.info(f"🏁 Run complete: {successful_count}/{total_processed} files processed successfully")
            
        except Exception as e:
            logger.critical(f"❌ Unhandled exception in run: {e}")
            with open(self.output_dir / "_error_summary.md", 'w') as f:
                f.write(f"# ❌ Conversion Process Failed\n\n**Error:** {str(e)}\n")
            raise
        finally:
            try:
                for temp_file in self.temp_dir.glob("*"):
                    temp_file.unlink(missing_ok=True)
                self.temp_dir.rmdir()
                logger.debug(f"✅ Cleaned up temp directory")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean up temp directory: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Convert documents to Markdown.")
    parser.add_argument('--use-llm', action='store_true',
                        help='Use the LLM for conversion instead of the direct method.')
    args = parser.parse_args()

    api_key = None  # Default the API key to None

    # Only attempt to get the API key if the user wants to use the LLM.
    if args.use_llm:
        api_key = os.environ.get('GEMINI_API_KEY')
        # The DocumentConverter will perform the check to ensure it's not None.

    input_dir = Path(os.environ.get('INPUT_DIR', '/input'))
    output_dir = Path(os.environ.get('OUTPUT_DIR', '/output'))
    cache_dir = Path(os.environ.get('CACHE_DIR', '/cache'))

    # Initialize the converter. It will now only receive an API key if --use-llm is active.
    converter = DocumentConverter(api_key, input_dir, output_dir, cache_dir, use_llm=args.use_llm)
    converter.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning(f"\n⚠️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        sys.exit(1)
