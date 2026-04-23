from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.api.routes import upload, extract, validate, tax, itr

setup_logging(settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    # Ensure data/logs dir exists
    (settings.upload_dir.parent.parent / "data" / "logs").mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Hybrid AI Workflow for Automated Tax Return Filing in India",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(extract.router, prefix="/api/v1", tags=["Extraction"])
app.include_router(validate.router, prefix="/api/v1", tags=["Validation"])
app.include_router(tax.router, prefix="/api/v1", tags=["Tax Computation"])
app.include_router(itr.router, prefix="/api/v1", tags=["ITR Generation"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
