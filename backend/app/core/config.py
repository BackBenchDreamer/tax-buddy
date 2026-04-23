from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    app_name: str = "Tax Buddy India"
    app_version: str = "1.0.0"
    debug: bool = False
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/taxbuddy.db"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    output_dir: Path = BASE_DIR / "data" / "outputs"
    model_dir: Path = BASE_DIR / "data" / "models"
    max_upload_size_mb: int = 20
    ocr_confidence_threshold: float = 0.6
    ner_model_name: str = "xlm-roberta-base"
    ner_model_path: str = ""  # override with fine-tuned path

    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.model_dir.mkdir(parents=True, exist_ok=True)
