#!/bin/bash
set -euxo pipefail

echo "--- [Export Image Script] Started ---"

# --- Configuration ---
TAG=${BUILD_TIMESTAMP:-latest}
GDRIVE_PATH="/Users/husainal-mohssen/Library/CloudStorage/GoogleDrive-husain@chbird.ai/My Drive"
TEMP_DIR="/tmp/docker-export-$$"
CHBIRD_IMAGE_NAME="chbird-app:$TAG"
DOCS2MD_IMAGE_NAME="docs2md:$TAG"

# Local temporary paths
CHBIRD_LOCAL_TAR="${TEMP_DIR}/docker-img-chbird.tar"
DOCS2MD_LOCAL_TAR="${TEMP_DIR}/docker-img-docs2md.tar"
CHBIRD_LOCAL_GZ="${TEMP_DIR}/docker-img-chbird.tar.gz"
DOCS2MD_LOCAL_GZ="${TEMP_DIR}/docker-img-docs2md.tar.gz"

# Final GDrive paths
CHBIRD_EXPORT_PATH_GZ="${GDRIVE_PATH}/docker-img-chbird.tar.gz"
DOCS2MD_EXPORT_PATH_GZ="${GDRIVE_PATH}/docker-img-docs2md.tar.gz"

# Create temporary directory
echo ">>> Creating temporary export directory: ${TEMP_DIR}"
rm -rf "${TEMP_DIR}"
mkdir -p "${TEMP_DIR}"

# --- Export chbird-app ---
echo
echo ">>> Processing image: ${CHBIRD_IMAGE_NAME}"
if ! docker image inspect "${CHBIRD_IMAGE_NAME}" &> /dev/null; then
    echo ">>> Image '${CHBIRD_IMAGE_NAME}' not found. Checking for 'chbird-app:latest'..."
    if docker image inspect "chbird-app:latest" &> /dev/null; then
        echo ">>> Found 'chbird-app:latest', tagging as '${CHBIRD_IMAGE_NAME}'..."
        docker tag "chbird-app:latest" "${CHBIRD_IMAGE_NAME}"
    else
        echo "!!! ERROR: Neither '${CHBIRD_IMAGE_NAME}' nor 'chbird-app:latest' found."
        exit 1
    fi
fi
echo "    Saving '${CHBIRD_IMAGE_NAME}' to local tarball..."
docker save -o "${CHBIRD_LOCAL_TAR}" "${CHBIRD_IMAGE_NAME}"
echo "    Compressing tarball locally..."
pigz -p 10 -f "${CHBIRD_LOCAL_TAR}"
echo "    Moving compressed file to Google Drive..."
mv "${CHBIRD_LOCAL_GZ}" "${CHBIRD_EXPORT_PATH_GZ}"
echo "    Image successfully saved to ${CHBIRD_EXPORT_PATH_GZ}"

# --- Export docs2md ---
echo
echo ">>> Processing image: ${DOCS2MD_IMAGE_NAME}"
if ! docker image inspect "${DOCS2MD_IMAGE_NAME}" &> /dev/null; then
    echo ">>> Image '${DOCS2MD_IMAGE_NAME}' not found. Checking for 'docs2md:latest'..."
    if docker image inspect "docs2md:latest" &> /dev/null; then
        echo ">>> Found 'docs2md:latest', tagging as '${DOCS2MD_IMAGE_NAME}'..."
        docker tag "docs2md:latest" "${DOCS2MD_IMAGE_NAME}"
    else
        echo "!!! ERROR: Neither '${DOCS2MD_IMAGE_NAME}' nor 'docs2md:latest' found."
        exit 1
    fi
fi
echo "    Saving '${DOCS2MD_IMAGE_NAME}' to local tarball..."
docker save -o "${DOCS2MD_LOCAL_TAR}" "${DOCS2MD_IMAGE_NAME}"
echo "    Compressing tarball locally..."
pigz -p 10 -f "${DOCS2MD_LOCAL_TAR}"
echo "    Moving compressed file to Google Drive..."
mv "${DOCS2MD_LOCAL_GZ}" "${DOCS2MD_EXPORT_PATH_GZ}"
echo "    Image successfully saved to ${DOCS2MD_EXPORT_PATH_GZ}"

# --- Cleanup ---
echo
echo ">>> Cleaning up temporary directory..."
rm -rf "${TEMP_DIR}"
echo "✅ Temporary files cleaned up."

echo
echo "--- [Export Image Script] Finished. ---"
