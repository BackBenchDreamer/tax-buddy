"""
Application configuration via pydantic-settings.

All values can be overridden in backend/.env.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────
    PROJECT_NAME: str = "AI Tax Filing System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # ── Storage ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/taxbuddy.db"
    UPLOAD_DIR: str = "data/uploads"

    # ── OCR ──────────────────────────────────────────────────────────────
    OCR_CONFIDENCE_THRESHOLD: float = 0.70
    OCR_DPI: int = 200

    # ── NER ──────────────────────────────────────────────────────────────
    NER_USE_TRANSFORMER: bool = False           # set True once model is fine-tuned
    NER_TRANSFORMER_MODEL: str = "xlm-roberta-base"
    NER_CONFIDENCE_THRESHOLD: float = 0.60

    # ── Tax ──────────────────────────────────────────────────────────────
    DEFAULT_TAX_REGIME: str = "old"             # "old" | "new"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once per process."""
    return Settings()


settings = get_settings()
