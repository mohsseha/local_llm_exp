# 🚀 Bulletproof Document to Markdown Converter

A **bulletproof**, **multi-threaded** document conversion tool that transforms various document formats into Markdown with complete **fault isolation** and **timeout protection**.

## ✨ Features

### 🛡️ **Bulletproof Architecture**
- **Complete thread isolation** - individual file failures cannot crash the entire process
- **60-second timeout per file** - prevents hanging on problematic documents
- **Automatic error recovery** - continues processing even if files fail catastrophically
- **Resource leak prevention** - proper cleanup of timed-out processes

### 📊 **Rich Logging & Progress Tracking**
- **Real-time progress updates** with emoji indicators
- **Thread-safe logging** with thread IDs for debugging
- **File type breakdown table** showing success rates by document type
- **Comprehensive final summary** with detailed statistics

### 🔄 **Flexible Conversion Modes**
- **Direct conversion** using pandoc (default, fast)
- **LLM-powered conversion** using Google GenAI for complex documents
- **Smart caching** based on file content hash
- **Multi-format support** (PDF, Word, Excel, PowerPoint, images, emails, text)

### 📧 **Advanced Email Processing**
- **Bulletproof .eml parsing** with proper header API usage
- **Thread organization** - groups related emails into conversations
- **Attachment extraction** with deduplication
- **HTML to Markdown conversion** for rich email content

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Build the Docker image
docker build -t docs2md .

# Run with direct conversion (pandoc)
docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/cache docs2md

# Run with LLM conversion (requires API key)
docker run -e GEMINI_API_KEY=your_key_here -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/cache docs2md --use-llm

# Monitor progress in real-time
docker logs -f <container_id>
```

### Using run script

```bash
# Process a single file or directory
./run.docs2md.sh /path/to/your/documents

# The script handles Docker building and volume mounting automatically
```

### Local Python Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export INPUT_DIR=/path/to/input
export OUTPUT_DIR=/path/to/output  
export CACHE_DIR=/path/to/cache

# Run conversion
python convert.py                    # Direct mode
python convert.py --use-llm         # LLM mode (requires GEMINI_API_KEY)
```

## 📋 Supported File Types

| Type | Extensions | Direct Mode | LLM Mode | Notes |
|------|------------|-------------|----------|-------|
| **Text** | `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`, `.py`, etc. | ✅ Copy | ✅ Copy | Preserved as-is |
| **PDF** | `.pdf` | ⚠️ Metadata only | ✅ Full extraction | OCR and text extraction |
| **Word** | `.doc`, `.docx`, `.rtf`, `.odt` | ✅ Pandoc | ✅ LLM conversion | |
| **Excel** | `.xls`, `.xlsx`, `.ods` | ✅ Sheet splitting | ✅ LLM analysis | Each sheet becomes separate MD |
| **PowerPoint** | `.ppt`, `.pptx`, `.odp` | ✅ Pandoc | ✅ LLM conversion | |
| **Images** | `.jpg`, `.png`, `.gif`, `.bmp`, `.tiff` | ⚠️ Metadata only | ✅ OCR + Analysis | Vision model processing |
| **Email** | `.eml` | ✅ Thread parsing | ✅ Thread parsing | Groups into conversations |

## 🛡️ Bulletproof Features

### Isolation & Recovery
- **Individual file isolation** - one corrupted file won't stop processing
- **Timeout protection** - 60-second limit prevents infinite hangs  
- **Memory safety** - automatic cleanup of failed processes
- **Thread safety** - parallel processing without race conditions

### Error Handling
- **Graceful degradation** - creates error reports for failed files
- **Detailed logging** - every failure logged with context
- **Continue on error** - never stops due to individual file issues
- **Resource cleanup** - prevents zombie processes and memory leaks

### Progress Monitoring
```bash
# Real-time monitoring via Docker logs
docker logs -f <container_id>

# Example output:
🚀 Starting bulletproof document conversion process
🔒 File processing timeout: 60s per file
🔒 Thread isolation: 4 parallel workers
📊 Found 150 files to process
📊 File types: pdf(45), word(23), excel(12), eml(70)
✅ [1/150] SUCCESS: report.pdf
✅ [2/150] SUCCESS: presentation.pptx
⚠️ [3/150] FAILED: corrupted.pdf
📊 Progress: 75/150 (50.0%) - ✅65 ❌10
```

## 📊 Final Summary

After processing, you'll get a comprehensive summary:

### Console Summary
```
📋 ==================== FINAL SUMMARY ====================
🎉 Processing COMPLETE! Total time: 127.45 seconds
📊 Files processed: 150
✅ Successful: 142 (94.7%)
❌ Failed: 8

📋 FILE TYPE BREAKDOWN:
Type         Total  Success  Failed  Success %
------------ ------ -------- ------- ----------
eml          70     68       2       97.1%     
pdf          45     43       2       95.6%     
word         23     23       0       100.0%    
excel        12     8        4       66.7%     

🔒 Conversion mode: Direct (pandoc)
⏱️ Timeout setting: 60s per file
🔒 Thread isolation: ENABLED (4 workers)
📋 ===================================================
```

### Markdown Summary File

A detailed `_conversion_summary.md` file is created with:
- Processing statistics and timing
- File type breakdown table
- Configuration details  
- Success rate analysis

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INPUT_DIR` | `/input` | Directory containing documents to convert |
| `OUTPUT_DIR` | `/output` | Directory for generated Markdown files |
| `CACHE_DIR` | `/cache` | Directory for caching converted files |
| `GEMINI_API_KEY` | - | Google GenAI API key (required for LLM mode) |

### Timeouts & Limits

```python
FILE_PROCESSING_TIMEOUT = 60  # seconds per file
MAX_FILE_SIZE_MB = 20          # size limit for processing
MAX_PAGES_APPROX = 20          # page limit for PDFs
THREADS_FOR_LOCAL_OPS = 4      # parallel workers
```

## 🔧 Advanced Usage

### Custom Docker Build

```bash
# Build with custom timeout
docker build --build-arg TIMEOUT=120 -t docs2md .

# Build for specific architecture  
docker build --platform linux/amd64 -t docs2md .
```

### Email Processing

The tool automatically:
1. **Groups emails** by conversation thread
2. **Extracts attachments** with deduplication
3. **Converts HTML** content to Markdown
4. **Removes quoted text** for cleaner output
5. **Handles encoding** issues gracefully

### Caching System

- **Content-based hashing** - only reprocesses changed files
- **Mode-aware caching** - separate cache for direct vs LLM modes
- **Automatic cleanup** - manages disk space efficiently

## 🐛 Troubleshooting

### Common Issues

**Files timing out?**
```bash
# Increase timeout in convert.py
FILE_PROCESSING_TIMEOUT = 120  # 2 minutes
```

**Out of memory?**
```bash
# Reduce parallel workers
THREADS_FOR_LOCAL_OPS = 2
```

**LLM mode not working?**
```bash
# Check API key
echo $GEMINI_API_KEY

# Verify Google GenAI installation
pip install google-generativeai
```

**Docker build failing?**
```bash
# Clean Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -t docs2md .
```

### Logging Levels

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# View specific thread logs
docker logs <container_id> | grep "T12345"
```

## 📝 Dependencies

### Core Requirements
- `pypandoc` - Document conversion engine
- `colorlog` - Rich console logging
- `pandas` - Excel file processing
- `openpyxl` - Excel format support
- `html2text` - HTML to Markdown conversion

### Optional (LLM Mode)
- `google-generativeai` - Google GenAI integration

### System Requirements
- `pandoc` - Universal document converter
- `libreoffice` - Office document processing (headless mode)
- `imagemagick` - Image format conversion

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add bulletproof error handling to any new features
4. Test with various file types and edge cases
5. Update documentation
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built for reliability** 🛡️ **Designed for scale** 📈 **Optimized for visibility** 👀