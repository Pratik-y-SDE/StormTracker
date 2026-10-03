# ==============================================================================
# Dockerfile — Cyclone Impact Forecaster (ZATICS v3.0)
# Production-ready container for Google Cloud Run & Docker
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY api/ ./api/
COPY run.py .
COPY test_backend.py .
COPY README.md .

# Pre-initialize SQLite database on build
RUN python -c "from backend.db import init_db; init_db()"

# Expose container port
EXPOSE 8000

# Start server listening on Cloud Run's dynamic $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
