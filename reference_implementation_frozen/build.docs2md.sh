#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Use timestamp from parent script, fallback to latest if not set
TAG=${BUILD_TIMESTAMP:-latest}
IMAGE_NAME="docs2md:$TAG"

echo "Building docs2md Docker image with tag: $IMAGE_NAME"
docker build -t docs2md:latest docs2md
echo "✅ Docker image $IMAGE_NAME built successfully."
