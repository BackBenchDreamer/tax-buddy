# =============================================================================
# Tax Buddy — FastAPI Backend
# =============================================================================
# Multi-stage build keeps the final image lean.
# Stage 1: Install heavy dependencies (tesseract, poppler, Python packages)
# Stage 2: Runtime image

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
    # Build tools (needed for some pip packages)
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pdf2image python-multipart

# ── Application code ──────────────────────────────────────────────────────────
COPY backend/ ./

# Create runtime directories
RUN mkdir -p data/uploads data/samples logs

# ── Runtime ───────────────────────────────────────────────────────────────────
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/system/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
