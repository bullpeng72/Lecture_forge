"""
Configuration management for LectureForge.

Loads settings from environment variables (.env file).
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Global configuration class."""

    # ===== Project Paths =====
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    TEMPLATES_DIR = Path(__file__).parent / "templates"

    # ===== OpenAI API =====
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "gpt-4o")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))

    # ===== Search API =====
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")

    # ===== Image Search APIs =====
    UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")
    PEXELS_API_KEY: Optional[str] = os.getenv("PEXELS_API_KEY")
    MAX_IMAGES_PER_SEARCH: int = int(os.getenv("MAX_IMAGES_PER_SEARCH", "10"))
    IMAGE_FORMAT: str = os.getenv("IMAGE_FORMAT", "webp")
    IMAGE_MAX_WIDTH: int = int(os.getenv("IMAGE_MAX_WIDTH", "1200"))

    # ===== Vector DB =====
    VECTOR_DB_PATH: Path = Path(os.getenv("VECTOR_DB_PATH", str(DATA_DIR / "vector_db")))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # ===== Quality Assurance =====
    QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "80"))
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))

    # ===== Logging =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        errors = []

        # Required keys
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required in .env file")
        else:
            # Validate OpenAI API key format
            if not (cls.OPENAI_API_KEY.startswith(("sk-", "sk-proj-")) and len(cls.OPENAI_API_KEY) > 20):
                errors.append(
                    "OPENAI_API_KEY has invalid format. "
                    "Should start with 'sk-' or 'sk-proj-' and be at least 20 characters long."
                )

        if not cls.SERPER_API_KEY:
            errors.append("SERPER_API_KEY is required in .env file")
        else:
            # Validate Serper API key format (basic length check)
            if len(cls.SERPER_API_KEY) < 10:
                errors.append(
                    "SERPER_API_KEY appears invalid (too short). "
                    "Please verify your API key from serper.dev"
                )

        if errors:
            raise ValueError(
                "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        # Warnings for optional keys
        if not cls.UNSPLASH_ACCESS_KEY:
            print("⚠️  UNSPLASH_ACCESS_KEY not set. Image search will be limited.")
        elif len(cls.UNSPLASH_ACCESS_KEY) < 10:
            print("⚠️  UNSPLASH_ACCESS_KEY appears invalid (too short).")

        if not cls.PEXELS_API_KEY:
            print("⚠️  PEXELS_API_KEY not set. Image search will be limited.")
        elif len(cls.PEXELS_API_KEY) < 10:
            print("⚠️  PEXELS_API_KEY appears invalid (too short).")

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure required directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "images").mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)


# Validate configuration on import
try:
    Config.validate()
    Config.ensure_directories()
except ValueError as e:
    print(f"\n❌ Configuration Error:\n{e}\n")
    print("Please create a .env file based on .env.example and set required API keys.")
    exit(1)
