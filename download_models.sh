#!/bin/bash
# Script to download Qwen3-VL GGUF models from HuggingFace

MODEL_DIR="models"
mkdir -p "$MODEL_DIR"

echo "📥 Downloading Qwen3-VL-8B-Instruct (Recommended for 16GB RAM)..."

# 8B Model (Q4_K_M)
uv run huggingface-cli download Qwen/Qwen3-VL-8B-Instruct-GGUF \
    Qwen3VL-8B-Instruct-Q4_K_M.gguf \
    --local-dir "$MODEL_DIR"

# 8B Vision Projector
uv run huggingface-cli download Qwen/Qwen3-VL-8B-Instruct-GGUF \
    mmproj-Qwen3VL-8B-Instruct-F16.gguf \
    --local-dir "$MODEL_DIR"

echo "✅ Download complete. Models are in $MODEL_DIR/"
