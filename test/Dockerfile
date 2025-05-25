# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    bc \
    && rm -rf /var/lib/apt/lists/*

# Copy test files
COPY . /app/

# List files to debug
RUN ls -la /app/

# Make the entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Install Python dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-html \
    pytest-xdist \
    pytest-timeout

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
