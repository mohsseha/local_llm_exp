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
mkdir -p ~/Documents.md
mkdir -p ~/Document_cache

echo "📂 Building the Docker image..."
docker build -t document-converter .

echo "🔄 Running the container..."
echo "   • Input: ~/Documents (read-only)"
echo "   • Output: ~/Documents.md"
echo "   • Cache: ~/Document_cache"

# Run the container with three volume mounts:
# 1. Input directory (read-only)
# 2. Output directory
# 3. Cache directory (persistent)
docker run \
  -v ~/Documents:/tmp/Documents:ro \
  -v ~/Documents.md:/tmp/Output \
  -v ~/Document_cache:/tmp/Document_cache \
  document-converter

echo -e "\033[1;32m"
echo "✅ Conversion complete! Results saved to ~/Documents.md"
echo -e "\033[0m"
