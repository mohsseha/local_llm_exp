#!/bin/bash
set -euxo pipefail

echo "--- [Entrypoint] Started ---"

# --- Setup Application Config ---
echo ">>> [Entrypoint] Setting up application config..."
# dot_svs_acct.json is now in /root/chbird_build_assets from Dockerfile COPY
cp /root/chbird_build_assets/dot_svs_acct.json /root/.service_acct.json 
chmod 600 /root/.service_acct.json

# --- Install chbird Package in Editable Mode ---
echo ">>> [Entrypoint] Installing chbird package in editable mode (system-wide)..."
uv pip install -e . --system --no-deps --no-cache-dir

# --- Launch Application ---
echo ">>> [Entrypoint] Launching application with command: $@"
exec "$@"
