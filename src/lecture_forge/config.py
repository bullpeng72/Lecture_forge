"""
Configuration management for LectureForge.

Loads settings from environment variables (.env file).

The .env file is searched in the following order:
  1. LECTURE_FORGE_ENV_FILE environment variable (if set)
  2. ./.env (current working directory)
  3. Platform-specific user directory:
     - Windows: %LOCALAPPDATA%\\lecture-forge\\.env
     - Mac/Linux: ~/.lecture-forge/.env
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Module-level logger (uses standard logging, not rich)
logger = logging.getLogger("lecture_forge.config")


def get_default_config_dir() -> Path:
    """
    Get the default configuration directory based on platform.

    Returns:
        Path to the platform-specific config directory
    """
    if sys.platform == "win32":
        # Windows: Use LOCALAPPDATA
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "lecture-forge"
        else:
            # Fallback to home directory
            return Path.home() / "lecture-forge"
    else:
        # Unix-like systems (Mac, Linux)
        return Path.home() / ".lecture-forge"


def find_and_load_env() -> Optional[Path]:
    """
    Find and load .env file from multiple locations.

    Search order:
      1. LECTURE_FORGE_ENV_FILE environment variable (if set)
      2. ./.env (current working directory)
      3. Platform-specific user directory

    Returns:
        Path to the loaded .env file, or None if not found
    """
    # 1. Explicitly specified path via environment variable
    explicit_path = os.getenv("LECTURE_FORGE_ENV_FILE")
    if explicit_path:
        env_path = Path(explicit_path).expanduser().resolve()
        if env_path.exists():
            load_dotenv(env_path, override=True)
            logger.info(f"✓ Loaded .env from: {env_path}")
            return env_path
        else:
            logger.warning(
                f"⚠️  LECTURE_FORGE_ENV_FILE points to non-existent file: {env_path}"
            )

    # 2. Current working directory
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)
        logger.info(f"✓ Loaded .env from current directory: {cwd_env}")
        return cwd_env

    # 3. Platform-specific user directory
    user_config_dir = get_default_config_dir()
    user_env = user_config_dir / ".env"
    if user_env.exists():
        load_dotenv(user_env)
        logger.info(f"✓ Loaded .env from user config directory: {user_env}")
        return user_env

    # Not found
    logger.warning("⚠️  No .env file found in any standard location")
    return None


# Load .env file at module import
ENV_FILE_PATH = find_and_load_env()


class Config:
    """Global configuration class."""

    # ===== Project Paths =====
    # For installed packages, use user's directories
    USER_CONFIG_DIR = get_default_config_dir()
    DATA_DIR = Path(os.getenv("DATA_DIR", str(USER_CONFIG_DIR / "data")))
    OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(USER_CONFIG_DIR / "outputs")))

    # Templates are always in the package directory
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
    # Extraction phase: Filter for meaningful images (diagrams, charts, text-rich images)
    # Enhanced algorithm: size(15%) + aspect(15%) + compression(20%) + content(30%) + meaningful(20%)
    IMAGE_EXTRACTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_EXTRACTION_QUALITY_THRESHOLD", "0.35"))
    # Selection phase: Strict filtering (select best images for lecture inclusion)
    IMAGE_SELECTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_SELECTION_QUALITY_THRESHOLD", "0.40"))

    # ===== Vector DB =====
    VECTOR_DB_PATH: Path = Path(os.getenv("VECTOR_DB_PATH", str(DATA_DIR / "vector_db")))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # ===== RAG Cache =====
    RAG_CACHE_PATH: Path = Path(os.getenv("RAG_CACHE_PATH", str(DATA_DIR / "rag_cache")))
    RAG_CACHE_TTL: int = int(os.getenv("RAG_CACHE_TTL", "86400"))  # 24 hours in seconds
    RAG_CACHE_MAX_SIZE: int = int(os.getenv("RAG_CACHE_MAX_SIZE", "1000"))  # Max number of cached queries

    # ===== Quality Assurance =====
    QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "80"))
    QUALITY_THRESHOLD_SECTION: int = int(os.getenv("QUALITY_THRESHOLD_SECTION", "70"))  # Relaxed for section-level
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))

    # Diagram quality threshold (0-100)
    DIAGRAM_QUALITY_THRESHOLD: int = int(os.getenv("DIAGRAM_QUALITY_THRESHOLD", "70"))

    # ===== Content Metrics =====
    # Lecture speed (words per minute)
    # Reading speed: 200-250 wpm, but lectures are slower due to:
    #   - Pauses for comprehension
    #   - Code demonstrations
    #   - Interactive elements
    LECTURE_WORDS_PER_MINUTE: int = int(os.getenv("LECTURE_WORDS_PER_MINUTE", "120"))

    # Difficulty multipliers for word count
    DIFFICULTY_MULTIPLIER_BEGINNER: float = float(os.getenv("DIFFICULTY_MULTIPLIER_BEGINNER", "1.3"))
    DIFFICULTY_MULTIPLIER_INTERMEDIATE: float = float(os.getenv("DIFFICULTY_MULTIPLIER_INTERMEDIATE", "1.0"))
    DIFFICULTY_MULTIPLIER_ADVANCED: float = float(os.getenv("DIFFICULTY_MULTIPLIER_ADVANCED", "1.1"))

    # Code examples per time (minutes per example)
    CODE_EXAMPLES_PER_TIME_BEGINNER: int = int(os.getenv("CODE_EXAMPLES_PER_TIME_BEGINNER", "20"))
    CODE_EXAMPLES_PER_TIME_INTERMEDIATE: int = int(os.getenv("CODE_EXAMPLES_PER_TIME_INTERMEDIATE", "15"))
    CODE_EXAMPLES_PER_TIME_ADVANCED: int = int(os.getenv("CODE_EXAMPLES_PER_TIME_ADVANCED", "12"))

    # Practice problems per time (minutes per problem)
    PRACTICE_PER_TIME_BEGINNER: int = int(os.getenv("PRACTICE_PER_TIME_BEGINNER", "25"))
    PRACTICE_PER_TIME_INTERMEDIATE: int = int(os.getenv("PRACTICE_PER_TIME_INTERMEDIATE", "20"))
    PRACTICE_PER_TIME_ADVANCED: int = int(os.getenv("PRACTICE_PER_TIME_ADVANCED", "30"))

    # Subsections and visuals
    SUBSECTION_MINUTES: int = int(os.getenv("SUBSECTION_MINUTES", "12"))  # Minutes per subsection
    VISUAL_PER_MINUTES: int = int(os.getenv("VISUAL_PER_MINUTES", "10"))  # Minutes per visual

    # Word count tolerance
    MIN_WORDS_RATIO: float = float(os.getenv("MIN_WORDS_RATIO", "0.75"))  # Allow 25% under
    MAX_WORDS_RATIO: float = float(os.getenv("MAX_WORDS_RATIO", "1.3"))  # Allow 30% over

    # ===== Slide Generation =====
    MAX_ITEMS_PER_SLIDE: int = int(os.getenv("MAX_ITEMS_PER_SLIDE", "4"))  # Maximum content blocks per slide

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
    PLAYWRIGHT_WAIT_STATE: str = os.getenv("PLAYWRIGHT_WAIT_STATE", "networkidle")  # networkidle, domcontentloaded, load

    # ===== Logging =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_env_file_locations(cls) -> list[str]:
        """Get list of .env file search locations for user guidance."""
        locations = []

        # 1. Environment variable
        locations.append("LECTURE_FORGE_ENV_FILE environment variable (if set)")

        # 2. Current directory
        locations.append("./.env (current working directory)")

        # 3. Platform-specific user directory
        user_config_dir = get_default_config_dir()
        if sys.platform == "win32":
            locations.append(f"{user_config_dir}\\.env (recommended for Windows)")
        else:
            locations.append(f"{user_config_dir}/.env (recommended)")

        return locations

    @classmethod
    def get_recommended_env_path(cls) -> Path:
        """Get the recommended .env file path for the current platform."""
        return get_default_config_dir() / ".env"

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        errors = []

        # Check if .env file was found
        if not ENV_FILE_PATH:
            error_msg = "❌ No .env file found!\n\n"
            error_msg += "📍 LectureForge searches for .env files in these locations:\n"
            for i, location in enumerate(cls.get_env_file_locations(), 1):
                error_msg += f"   {i}. {location}\n"

            error_msg += "\n🚀 Quick start:\n"
            error_msg += "   Run: lecture-forge init\n\n"
            error_msg += "   Or manually create a .env file at:\n"
            error_msg += f"   {cls.get_recommended_env_path()}\n"

            errors.append(error_msg)

        # Required keys
        if not cls.OPENAI_API_KEY:
            errors.append(
                "❌ OPENAI_API_KEY is required\n"
                "   Get your key from: https://platform.openai.com"
            )
        else:
            # Validate OpenAI API key format
            if not (
                cls.OPENAI_API_KEY.startswith(("sk-", "sk-proj-"))
                and len(cls.OPENAI_API_KEY) > 20
            ):
                errors.append(
                    "❌ OPENAI_API_KEY has invalid format\n"
                    "   Should start with 'sk-' or 'sk-proj-' and be at least 20 characters long."
                )

        if not cls.SERPER_API_KEY:
            errors.append(
                "❌ SERPER_API_KEY is required\n"
                "   Get your free key from: https://serper.dev\n"
                "   (2,500 searches/month free)"
            )
        else:
            # Validate Serper API key format (basic length check)
            if len(cls.SERPER_API_KEY) < 10:
                errors.append(
                    "❌ SERPER_API_KEY appears invalid (too short)\n"
                    "   Please verify your API key from serper.dev"
                )

        if errors:
            raise ValueError("\n" + "\n".join(errors))

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
        cls.USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "images").mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
