#!/bin/bash
# Script to build and run the document converter container

set -e  # Exit immediately if a command exits with a non-zero status

# Print colorful banner
echo -e "\033[1;36m"
echo "🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀"
echo "📄 Document to Markdown Converter 📄"
echo "🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀 🚀"
echo -e "\033[0m"

# Create necessary directories if they don't exist
mkdir -p ../data.md
mkdir -p ../cache

echo "📂 Building the Docker image..."
docker build -t document-converter .

echo "🔄 Running the container..."
echo "   • Input: ../data (read-only)"
echo "   • Output: ../data.md"
echo "   • Cache: ../cache"

# Run the container with three volume mounts:
# 1. Input directory (read-only)
# 2. Output directory
# 3. Cache directory (persistent)
docker run \
  -v ../data:/input:ro \
  -v ../data.md:/output \
  -v ../cache:/cache \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  document-converter

echo -e "\033[1;32m"
echo "✅ Conversion complete! Results saved to ../data.md"
echo -e "\033[0m"
