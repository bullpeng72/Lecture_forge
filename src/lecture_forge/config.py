"""
Configuration management for LectureForge.

Loads settings from environment variables (.env file).
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Module-level logger (uses standard logging, not rich)
logger = logging.getLogger("lecture_forge.config")


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
    SEARCH_NUM_RESULTS: int = int(os.getenv("SEARCH_NUM_RESULTS", "10"))
    SEARCH_TIMEOUT: int = int(os.getenv("SEARCH_TIMEOUT", "30"))

    # ===== Image Search APIs =====
    UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")
    PEXELS_API_KEY: Optional[str] = os.getenv("PEXELS_API_KEY")
    MAX_IMAGES_PER_SEARCH: int = int(os.getenv("MAX_IMAGES_PER_SEARCH", "10"))
    IMAGE_SEARCH_PER_PAGE: int = int(os.getenv("IMAGE_SEARCH_PER_PAGE", "10"))
    IMAGE_SEARCH_TIMEOUT: int = int(os.getenv("IMAGE_SEARCH_TIMEOUT", "30"))
    IMAGE_FORMAT: str = os.getenv("IMAGE_FORMAT", "webp")
    IMAGE_MAX_WIDTH: int = int(os.getenv("IMAGE_MAX_WIDTH", "1200"))

    # ===== Image Extraction & Quality =====
    # Minimum dimensions for extracted images (filters out icons/logos)
    IMAGE_MIN_WIDTH: int = int(os.getenv("IMAGE_MIN_WIDTH", "200"))
    IMAGE_MIN_HEIGHT: int = int(os.getenv("IMAGE_MIN_HEIGHT", "200"))

    # Quality thresholds (0.0 ~ 1.0)
    # Extraction phase: Conservative filtering (reject obvious junk only)
    IMAGE_EXTRACTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_EXTRACTION_QUALITY_THRESHOLD", "0.25"))
    # Selection phase: Strict filtering (select best images for lecture)
    IMAGE_SELECTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_SELECTION_QUALITY_THRESHOLD", "0.30"))

    # ===== Vector DB =====
    VECTOR_DB_PATH: Path = Path(os.getenv("VECTOR_DB_PATH", str(DATA_DIR / "vector_db")))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # ===== Quality Assurance =====
    QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "80"))
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))

    # Diagram quality threshold (0-100)
    DIAGRAM_QUALITY_THRESHOLD: int = int(os.getenv("DIAGRAM_QUALITY_THRESHOLD", "70"))

    # ===== Web Scraping =====
    WEB_SCRAPER_TIMEOUT: int = int(os.getenv("WEB_SCRAPER_TIMEOUT", "30"))

    # ===== Deep Web Crawler =====
    DEEP_CRAWLER_MAX_DEPTH: int = int(os.getenv("DEEP_CRAWLER_MAX_DEPTH", "2"))
    DEEP_CRAWLER_MAX_PAGES: int = int(os.getenv("DEEP_CRAWLER_MAX_PAGES", "10"))
    DEEP_CRAWLER_DELAY: float = float(os.getenv("DEEP_CRAWLER_DELAY", "1.0"))
    DEEP_CRAWLER_TIMEOUT: int = int(os.getenv("DEEP_CRAWLER_TIMEOUT", "30"))
    DEEP_CRAWLER_BASE_URL: str = os.getenv("DEEP_CRAWLER_BASE_URL", "https://news.hada.io")

    # ===== Playwright Crawler =====
    PLAYWRIGHT_MAX_DEPTH: int = int(os.getenv("PLAYWRIGHT_MAX_DEPTH", "2"))
    PLAYWRIGHT_MAX_PAGES: int = int(os.getenv("PLAYWRIGHT_MAX_PAGES", "10"))
    PLAYWRIGHT_DELAY: float = float(os.getenv("PLAYWRIGHT_DELAY", "2.0"))
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))

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
                errors.append("SERPER_API_KEY appears invalid (too short). " "Please verify your API key from serper.dev")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

        # Warnings for optional keys
        if not cls.UNSPLASH_ACCESS_KEY:
            logger.warning("UNSPLASH_ACCESS_KEY not set. Image search will be limited.")
        elif len(cls.UNSPLASH_ACCESS_KEY) < 10:
            logger.warning("UNSPLASH_ACCESS_KEY appears invalid (too short).")

        if not cls.PEXELS_API_KEY:
            logger.warning("PEXELS_API_KEY not set. Image search will be limited.")
        elif len(cls.PEXELS_API_KEY) < 10:
            logger.warning("PEXELS_API_KEY appears invalid (too short).")

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure required directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "images").mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
