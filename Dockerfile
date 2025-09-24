# Use Playwright base image with browsers preinstalled
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# System deps (sqlite3 CLI optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    xvfb \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

# Copy source
COPY . .

# Ensure data dir exists (mounted at runtime)
RUN mkdir -p /app/data /app/config /app/trash

# Default envs
ENV PYTHONUNBUFFERED=1 \
    USE_PLAYWRIGHT=1

# Run
CMD ["python", "-m", "src.main"]



