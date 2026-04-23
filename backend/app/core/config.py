from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Tax Buddy"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = "sqlite:///./tax_buddy.db"
    upload_dir: Path = Path("./storage/uploads")
    output_dir: Path = Path("./storage/outputs")
    ml_model_path: Path = Path("./storage/models/xlm-roberta-tax-ner")
    max_upload_mb: int = 25


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.ml_model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
