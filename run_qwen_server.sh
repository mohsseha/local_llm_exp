#!/bin/bash
# Script to run Qwen3-VL using llama-server

MODEL_PATH="models/Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MMPROJ_PATH="models/mmproj-Qwen3VL-8B-Instruct-F16.gguf"
SERVER_BIN="./llama.cpp/build/bin/llama-server"

echo "Starting Qwen3-VL Server..."
echo "Model: $MODEL_PATH"
echo "MMProj: $MMPROJ_PATH"

# Check if files exist
if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model file not found!"
    exit 1
fi

if [ ! -f "$MMPROJ_PATH" ]; then
    echo "Error: MMProj file not found!"
    exit 1
fi

if [ ! -f "$SERVER_BIN" ]; then
    echo "Error: llama-server binary not found! Did you compile llama.cpp?"
    exit 1
fi

# Run server
# --n-gpu-layers 0 for CPU-only (adjust if you have a GPU)
# --ctx-size 2048 to save memory
$SERVER_BIN \
    --model "$MODEL_PATH" \
    --mmproj "$MMPROJ_PATH" \
    --port 8080 \
    --host 0.0.0.0 \
    --n-gpu-layers 0 \
    --threads 6 \
    --threads-batch 6 \
    --ctx-size 2048 \
    --jinja
