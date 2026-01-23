FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including LibreOffice and ImageMagick
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libreoffice \
    imagemagick \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick policy to allow PDF conversion
RUN find /etc -name "policy.xml" -type f -exec sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' {} \;

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY convert.py .
COPY eml_to_threads.py .

# Create directories for input and output
RUN mkdir -p /input /output /cache

# Run the script
CMD ["python", "convert.py"]