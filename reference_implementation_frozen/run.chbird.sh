#!/bin/bash
set -euo pipefail

# --- Configuration ---
CONTAINER_NAME="chbirdai.local"
IMAGE_NAME="chbird-app:latest"

# --- Docker Image Check ---
if ! docker image inspect "${IMAGE_NAME}" &> /dev/null;
then
    echo ">>> Docker image '${IMAGE_NAME}' not found."
    echo ">>> Downloading pre-built image from Google Drive..."

    # The image is stored on Google Drive. We use curl to download it.
    # The file ID is extracted from the shared link provided.
    FILE_ID="1rsWo2L4EoGpa9Hg3nv7PQqZzVcozjDu2"
    DOWNLOAD_URL="https://drive.usercontent.google.com/download?id=${FILE_ID}&export=download&confirm=t"
    IMAGE_ARCHIVE_GZ="docker-img-chbird.tar.gz"

    # Use curl to download the file. The -L flag follows redirects.
    # We also check for curl's exit code to ensure the download was successful.
    if curl -L -o "${IMAGE_ARCHIVE_GZ}" "${DOWNLOAD_URL}"; then
        echo ">>> Download complete. Loading image into Docker..."
        # The exported image is gzipped, so we pipe it to docker load.
        gunzip -c "${IMAGE_ARCHIVE_GZ}" | docker load
        echo ">>> Docker image loaded successfully."
        
        # Clean up the downloaded archive to save space.
        rm "${IMAGE_ARCHIVE_GZ}"
        echo ">>> Removed temporary archive: ${IMAGE_ARCHIVE_GZ}"
    else
        echo "!!! Failed to download the Docker image."
        echo "!!! Please check your internet connection or the Google Drive link."
        exit 1
    fi
fi

HOST_DATA_DIR_NAME="data.md"
HOST_DATA_DIR_PATH="$(pwd)/${HOST_DATA_DIR_NAME}"
HOST_CACHE_DIR="$(pwd)/opt_chbird_cache"

# --- Environment Variables for the Container ---
# These will be passed to the application running inside Docker.
export INIT_PROJ_SHA="$(git -C ${HOST_DATA_DIR_PATH} rev-parse HEAD)"
export INIT_PROJ_URL="/data"
export INIT_PROJ_LOCAL_NAME="test project"

# --- Setup ---
echo ">>> Preparing to launch container..."
mkdir -p "${HOST_CACHE_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}"$; then
  echo "Found and removing existing container: ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}"
fi

# --- Execution ---
echo ">>> Starting container \
'${CONTAINER_NAME}' with image '${IMAGE_NAME}' in foreground..."
docker run \
  --name "${CONTAINER_NAME}" \
  --rm \
  -p 8080:8080 \
  -v "${HOST_DATA_DIR_PATH}:/data:ro" \
  -v "${HOST_CACHE_DIR}:/opt:rw" \
  -e "INIT_PROJ_SHA=${INIT_PROJ_SHA}" \
  -e "INIT_PROJ_URL=${INIT_PROJ_URL}" \
  -e "INIT_PROJ_LOCAL_NAME=${INIT_PROJ_LOCAL_NAME}" \
  "${IMAGE_NAME}"

echo "--- Script finished. Container has stopped. ---"
