"""Application configuration module."""
import os
from pathlib import Path
from typing import Optional
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
        self.APP_VERSION: str = os.getenv("APP_VERSION", "0.3.0")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:5174",
        )
        self.CORS_ORIGINS: list[str] = [
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        ]

        # GitHub Ingestion Limits & Settings
        # Keep enough of each repository snapshot available for browsing and analysis.
        self.MAX_SOURCE_FILES: int = int(os.getenv("MAX_SOURCE_FILES", "500"))
        self.MAX_FILE_SIZE_BYTES: int = int(
            os.getenv("MAX_FILE_SIZE_BYTES", str(100 * 1024))
        )  # 100 KB
        self.MAX_TOTAL_SIZE_BYTES: int = int(
            os.getenv("MAX_TOTAL_SIZE_BYTES", str(5 * 1024 * 1024))
        )  # 5 MB
        self.CONCURRENT_DOWNLOADS_LIMIT: int = int(
            os.getenv("CONCURRENT_DOWNLOADS_LIMIT", "10")
        )
        self.GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN") or None

        # AI & Vector Storage Settings (Milestone 3)
        chroma_directory = Path(
            os.getenv("CHROMA_PERSIST_DIRECTORY", str(BASE_DIR / "storage"))
        ).expanduser()
        if not chroma_directory.is_absolute():
            chroma_directory = BASE_DIR / chroma_directory
        self.CHROMA_PERSIST_DIRECTORY: str = str(chroma_directory)
        conversation_db_path = Path(
            os.getenv(
                "CONVERSATIONS_DB_PATH",
                str(Path(self.CHROMA_PERSIST_DIRECTORY) / "conversations.sqlite3"),
            )
        ).expanduser()
        if not conversation_db_path.is_absolute():
            conversation_db_path = BASE_DIR / conversation_db_path
        self.CONVERSATIONS_DB_PATH: str = str(conversation_db_path)
        self.EMBEDDING_MODEL_NAME: str = os.getenv(
            "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
        self.CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

        # Milestone 4: Groq grounded answer generation
        self.GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY") or None
        self.GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.GROQ_API_BASE_URL: str = os.getenv(
            "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"
        ).rstrip("/")
        self.GROQ_TIMEOUT_SECONDS: float = float(
            os.getenv("GROQ_TIMEOUT_SECONDS", "60")
        )
        self.RAG_MIN_SIMILARITY: float = float(
            os.getenv("RAG_MIN_SIMILARITY", "0.20")
        )
        self.RAG_MAX_CONTEXT_CHARS: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "24000"))


settings = Settings()
