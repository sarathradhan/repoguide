"""Application configuration module."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.APP_NAME: str = os.getenv("APP_NAME", "RepoGuide AI")
        self.APP_DESCRIPTION: str = os.getenv(
            "APP_DESCRIPTION",
            "AI-powered GitHub repository understanding assistant",
        )
        self.APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        )
        self.CORS_ORIGINS: list[str] = [
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        ]


settings = Settings()

