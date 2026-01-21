# Local LLM Exploration 🚀

The goal of this project is to explore running Large Language Models (LLMs) locally. 💻

## Current Focus 🔍

Using **Qwen3-VL** for high-quality multimodal OCR and document parsing.

## Setup Instructions (Mac M4 / Linux) 🛠️

### 1. Environment
This project uses `uv` for python management.
```bash
# Install dependencies
uv sync
```

### 2. Build llama.cpp
The `llama.cpp` directory is ignored by git. You need to clone and build it locally for your architecture (Metal on Mac M4):
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build -DGGML_METAL=ON  # Use Metal for M4
cmake --build build --config Release -j
cd ..
```

### 3. Download Models
Use the provided script to download the GGUF models:
```bash
./download_models.sh
```

### 4. Run Server
Start the Qwen3-VL server:
```bash
./run_qwen_server.sh
```

## Tools 🧰
- `main.py`: Main entry point for processing.
- `test_server.py`: Test the running server.
- `download_models.sh`: Helper to fetch models from HuggingFace.
