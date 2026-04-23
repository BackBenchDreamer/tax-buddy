from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Tax Filing System"
    API_V1_STR: str = "/api/v1"
    
    # Add your DB URIs, secret keys, etc. here
    # DATABASE_URL: str = "sqlite:///./test.db"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
