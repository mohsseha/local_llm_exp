#!/bin/bash
set -euxo pipefail

echo "--- [Build Script] Started ---"
echo ">>> Ensuring local git repo is up to date..."

# --- Configuration ---
BUILD_CONTEXT_DIR="./tmp-build-dir"
HOST_PERSISTENT_DATA_DIR="${HOME}/opt-chbird-data"
export HOST_PERSISTENT_DATA_DIR # Export for docker-compose

# --- Prepare Build Context for 'app' service ---
echo ">>> Preparing fresh build context in ${BUILD_CONTEXT_DIR}..."
rm -rf "${BUILD_CONTEXT_DIR}"
mkdir -p "${BUILD_CONTEXT_DIR}"

# --- Fetch Service Account Key from GCS ---
echo ">>> Fetching service account key from GCS..."
gsutil cp gs://chbirdai/app/dot_svs_acct.json "${BUILD_CONTEXT_DIR}/dot_svs_acct.json"

# --- Copy Local Files to Build Context ---
echo ">>> Copying application source files to build context..."
cp ../../requirements.txt "${BUILD_CONTEXT_DIR}/requirements.txt"
cp ./chbird/Dockerfile "${BUILD_CONTEXT_DIR}/Dockerfile"
cp ./chbird/entrypoint.sh "${BUILD_CONTEXT_DIR}/entrypoint.sh"
[ -f .dockerignore ] && cp .dockerignore "${BUILD_CONTEXT_DIR}/.dockerignore"

# --- Copy and Compile Python Source ---
echo ">>> Copying and compiling Python source from 'src' directory..."
# Based on pyproject.toml, package 'chbird' is in 'src'
cp -r ../../src "${BUILD_CONTEXT_DIR}/src"
cp ../../pyproject.toml "${BUILD_CONTEXT_DIR}/pyproject.toml"

echo ">>> Compiling .py files to .pyc..."
python3 -m compileall -b "${BUILD_CONTEXT_DIR}/src"

echo ">>> Removing .py source files..."
find "${BUILD_CONTEXT_DIR}/src" -type f -name "*.py" -delete

# --- Ensure Host Data Directory Exists ---
echo ">>> Ensuring host data directory exists: ${HOST_PERSISTENT_DATA_DIR}"
mkdir -p "${HOST_PERSISTENT_DATA_DIR}"

# --- Docker Compose Build ---
TAG=${BUILD_TIMESTAMP:-latest}
echo ">>> Building new images with tag: $TAG"
docker compose build --build-arg TAG="$TAG"

# Tag the built image with the timestamp
docker tag chbird-app:latest "chbird-app:$TAG"

echo "--- [Build Script] Finished. Images are built with tag: $TAG ---"
