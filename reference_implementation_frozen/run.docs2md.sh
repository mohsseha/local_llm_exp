#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

if [ ! -d "./data" ]; then
  echo "Error: ./data directory not found."
  exit 1
fi

IMAGE_NAME="docs2md:latest"

if ! docker image inspect "${IMAGE_NAME}" &> /dev/null; then
    echo ">>> Docker image '${IMAGE_NAME}' not found."
    echo ">>> Downloading pre-built image from Google Drive..."

    # The image is stored on Google Drive. We use curl to download it.
    # The file ID is extracted from the shared link provided.
    FILE_ID="1DTuwjHw0zarkoVHbm2fPagkRTTOhWGNW"
    DOWNLOAD_URL="https://drive.usercontent.google.com/download?id=${FILE_ID}&export=download&confirm=t"
    IMAGE_ARCHIVE_GZ="docker-img-docs2md.tar.gz"

    # Use curl to download the file. The -L flag follows redirects.
    if curl -L -o "${IMAGE_ARCHIVE_GZ}" "${DOWNLOAD_URL}"; then
        echo ">>> Download complete. Loading image into Docker..."
        gunzip -c "${IMAGE_ARCHIVE_GZ}" | docker load
        echo ">>> Docker image loaded successfully."
        
        rm "${IMAGE_ARCHIVE_GZ}"
        echo ">>> Removed temporary archive: ${IMAGE_ARCHIVE_GZ}"
    else
        echo "!!! Failed to download the Docker image."
        echo "!!! Please check your internet connection or the Google Drive link."
        exit 1
    fi
fi


echo "✅ Pre-flight checks passed."

# 2. Cleanup
if [ -d "./data.md" ]; then
  echo "Removing existing ./data.md directory."
  rm -rf ./data.md
fi

# 3. Directory Preparation
echo "Creating empty ./data.md directory."
mkdir ./data.md

echo "🚀 Starting document conversion..."

# 4. Container Execution
docker run \
  --rm \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v "$(pwd)/data:/input:ro" \
  -v "$(pwd)/data.md:/output" \
  "${IMAGE_NAME}" 2>&1 || true

echo "✅ Conversion complete."

# 5. Output Processing & Cleanup
echo "Cleaning up output directory..."
cd ./data.md
rm -f _conversion_summary.md
rm -rf caches/

# 5a. Add Overview README
echo "Adding folder overview README..."
cp ../FOLDER_OVERVIEW_README.md ./FOLDER_OVERVIEW_README.md

# 6. Git Repository Initialization
echo "Initializing Git repository..."
git init
git add .
# Use a fixed author and date for the commit to ensure a deterministic SHA.
# This is important for caching and reproducibility.
export GIT_AUTHOR_NAME="ChBird On-Site"
export GIT_AUTHOR_EMAIL="noreply@chbird.ai"
export GIT_AUTHOR_DATE="2025-08-01T00:00:00Z"
export GIT_COMMITTER_NAME="ChBird On-Site"
export GIT_COMMITTER_EMAIL="noreply@chbird.ai"
export GIT_COMMITTER_DATE="2025-08-01T00:00:00Z"
git commit -m "Initial conversion of documents"

# 7. Capture and Export Commit SHA
echo "Capturing initial commit SHA..."
INIT_PROJ_SHA=$(git rev-parse HEAD)
export INIT_PROJ_SHA
echo "✅ Initial project SHA (${INIT_PROJ_SHA}) has been exported as an environment variable."

echo "🎉 Phase 1 complete. A new Git repository has been created in ./data.md."
