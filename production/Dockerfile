# Multi-stage build for Customer Success FTE
# Stage 1: Build dependencies
# Stage 2: Runtime image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY production/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash fte && \
    chown -R fte:fte /app

USER fte

# Copy installed packages from builder
COPY --from=builder /home/fte/.local /home/fte/.local

# Make sure python can find user-installed packages
ENV PATH=/home/fte/.local/bin:$PATH

# Copy application code
COPY --chown=fte:fte production/ ./production/
COPY --chown=fte:fte incubation/ ./incubation/

# Create necessary directories
RUN mkdir -p logs data

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run API by default (can be overridden for worker)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
