# =============================================================================
# Tax Buddy — FastAPI Backend (Production)
# =============================================================================
# Multi-stage build for optimized image size
# Includes: Tesseract, Poppler, PaddleOCR, Python dependencies

FROM python:3.11-slim AS base

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # Poppler (pdf2image)
    poppler-utils \
    # OpenCV runtime libs
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libgomp1 \
    # Build tools (needed for some pip packages)
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ── Create app user (security best practice) ──────────────────────────────────
RUN useradd -m -u 1000 appuser

# ── Python environment ────────────────────────────────────────────────────────
WORKDIR /app

# Use system Python directly inside the container
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ── Install Python dependencies ───────────────────────────────────────────────
COPY backend/requirements.txt ./requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY backend/ ./

# Create runtime directories
RUN mkdir -p data/uploads data/samples logs && \
    chown -R appuser:appuser /app

# ── Switch to non-root user ───────────────────────────────────────────────────
USER appuser

# ── Environment variables (override via docker-compose or -e flags) ───────────
# API Configuration
ENV PROJECT_NAME="AI Tax Filing System"
ENV API_V1_STR="/api/v1"
ENV DEBUG="false"

# Storage
ENV DATABASE_URL="sqlite:///./data/taxbuddy.db"
ENV UPLOAD_DIR="data/uploads"

# OCR
ENV OCR_CONFIDENCE_THRESHOLD="0.70"
ENV OCR_DPI="200"

# NER
ENV NER_USE_TRANSFORMER="false"
ENV NER_TRANSFORMER_MODEL="xlm-roberta-base"
ENV NER_CONFIDENCE_THRESHOLD="0.60"

# Tax
ENV DEFAULT_TAX_REGIME="old"

# Groq API (set via docker-compose secrets or -e flag)
ENV GROQ_API_KEY=""
ENV GROQ_MODEL="llama3-70b-8192"
ENV GROQ_TIMEOUT="30"

# CORS
ENV CORS_ORIGINS='["http://localhost:3000","http://localhost:8501"]'

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/system/health')"

# ── Start application ─────────────────────────────────────────────────────────
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Made with Bob
