"""
FastAPI application entry point.

Startup sequence
----------------
1. Configure structured logging
2. Initialise SQLite DB (create tables if missing)
3. Mount API router
4. CORS middleware
"""

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.database import init_db
from app.api.router import api_router

# ── Logging must be configured before any module-level loggers fire ──────────
configure_logging(level="DEBUG" if settings.DEBUG else "INFO")
log = logging.getLogger(__name__)

# ── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="OCR → NER → Validation → Tax Engine — production-grade Indian tax filing API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)


# ── Lifecycle ────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    log.info("=== %s starting up ===", settings.PROJECT_NAME)
    init_db()
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    log.info("Upload directory: %s", settings.UPLOAD_DIR)


@app.on_event("shutdown")
async def on_shutdown():
    log.info("=== %s shutting down ===", settings.PROJECT_NAME)


# ── Dev entrypoint ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug" if settings.DEBUG else "info",
    )
