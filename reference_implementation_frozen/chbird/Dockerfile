# Base Image: Ubuntu 22.04 LTS (Jammy Jellyfish)
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH="/root/.local/bin:${PATH}"

# 1. Install System Dependencies, Python & UV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg software-properties-common build-essential graphviz git openssh-client \
    && \

    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 python3.12-dev python3.12-venv \
    && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --set python3 /usr/bin/python3.12 && \
    python3.12 -m ensurepip --upgrade && \
    python3 -m pip install --no-cache-dir --upgrade pip && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 2. Install Python Dependencies (Cached Layer)
# This layer is only invalidated if requirements.txt changes.
WORKDIR /root/chbird_app
COPY requirements.txt .
RUN uv pip install --no-cache-dir --system -r requirements.txt

# 3. Copy Application Code, Assets & Config
# These layers are invalidated more frequently on code changes.
COPY --chown=root:root src ./src
COPY --chown=root:root pyproject.toml .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh 

# The entrypoint script needs the service account key at a specific path.
# We create the directory and copy the file into it.
RUN mkdir -p /root/chbird_build_assets
COPY dot_svs_acct.json /root/chbird_build_assets/dot_svs_acct.json

# --- Sanity Checks (Optional) ---
RUN echo "Python Version:" && python3 --version && \
    echo "UV Version:" && uv --version && \
    echo "Graphviz dot location:" && which dot && \
    echo "Installed packages:" && uv pip list

ENTRYPOINT ["/entrypoint.sh"]
# WARNING: YOU HAVE TO BE SUPER CAREFUL WITH THREADS HERE IF YOU INCREASE IT FROM 1 IT WILL BREAK THINGS IN PROD!!!! 
CMD ["python3","-m","chbird.FE"]
