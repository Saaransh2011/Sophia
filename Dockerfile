# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install system utilities and audio/video tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ffmpeg \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy project specification
COPY pyproject.toml README.md ./

# Install python package dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source
COPY sophia/ sophia/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV SOPHIA_HOME=/root/.sophia

# Default entrypoint
ENTRYPOINT ["sophia"]
CMD ["test"]
