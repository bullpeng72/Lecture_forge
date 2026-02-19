"""
Configuration management for LectureForge.

Loads settings from environment variables (.env file).

The .env file is searched in the following order:
  1. LECTURE_FORGE_ENV_FILE environment variable (if set)
  2. ./.env (current working directory)
  3. Platform-specific user directory:
     - Windows: %USERPROFILE%\\Documents\\LectureForge\\.env
     - Mac/Linux: ~/Documents/LectureForge/.env
     - Fallback: ~/LectureForge/.env

Migration (v0.3.1+):
  - Automatically migrates from old ~/.lecture-forge/ to new visible location
  - Preserves all data (.env, vector_db, images, outputs, cache)
  - One-time operation on first run after upgrade
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Import exceptions (after module-level setup to avoid circular imports)
# These will be imported after Config class definition

# ===== CRITICAL: Disable ChromaDB telemetry BEFORE any imports =====
# This MUST be set before ChromaDB is imported anywhere in the application
# to prevent PostHog telemetry errors (capture() API incompatibility)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
# Also set CHROMA_TELEMETRY for redundancy
os.environ["CHROMA_TELEMETRY"] = "False"

# Suppress ChromaDB telemetry error messages (non-fatal PostHog API errors)
# ChromaDB 0.4.24 has a bug with PostHog capture() API that causes error logs
# but doesn't affect functionality. We suppress these specific error messages.
logging.getLogger("chromadb.telemetry.posthog").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.WARNING)  # Only show warnings and above

# Module-level logger (uses standard logging, not rich)
logger = logging.getLogger("lecture_forge.config")


def get_default_config_dir() -> Path:
    """
    Get the default configuration directory based on platform.

    New behavior (v0.3.1+):
      - Uses visible directory in Documents folder for better accessibility
      - Auto-migrates from old ~/.lecture-forge/ on first run

    Directory locations:
      - Windows: %USERPROFILE%\\Documents\\LectureForge
      - Mac/Linux: ~/Documents/LectureForge
      - Fallback: ~/LectureForge (if Documents doesn't exist)

    Returns:
        Path to the platform-specific config directory
    """
    if sys.platform == "win32":
        # Windows: Documents\LectureForge
        user_profile = os.getenv("USERPROFILE")
        if user_profile:
            docs = Path(user_profile) / "Documents"
            if docs.exists():
                return docs / "LectureForge"
        # Fallback to home directory
        return Path.home() / "LectureForge"
    else:
        # Mac/Linux: ~/Documents/LectureForge
        docs = Path.home() / "Documents"
        if docs.exists():
            return docs / "LectureForge"
        else:
            # Fallback: ~/LectureForge (if Documents doesn't exist)
            return Path.home() / "LectureForge"


def migrate_from_hidden_dir() -> bool:
    """
    Migrate data from old ~/.lecture-forge/ to new visible location.

    This function automatically runs on module import to migrate existing
    installations from the hidden directory to the new visible directory.

    Migration process:
      1. Check if old ~/.lecture-forge/ exists
      2. Check if new location already exists (skip if yes)
      3. Move entire directory to new location
      4. Preserve all data (.env, vector_db, images, outputs, cache)

    Returns:
        True if migration was performed, False otherwise
    """
    old_dir = Path.home() / ".lecture-forge"
    new_dir = get_default_config_dir()

    # Skip if old dir doesn't exist
    if not old_dir.exists():
        return False

    # Skip if already migrated (new dir exists)
    if new_dir.exists():
        # If both exist, warn user (manual intervention needed)
        if old_dir.exists():
            logger.warning(
                f"Both old ({old_dir}) and new ({new_dir}) directories exist. "
                "Please manually merge or remove the old directory."
            )
        return False

    # Perform migration
    logger.info(f"Migrating from {old_dir} to {new_dir}...")

    try:
        import shutil

        # Create parent directory if needed
        new_dir.parent.mkdir(parents=True, exist_ok=True)

        # Move entire directory
        shutil.move(str(old_dir), str(new_dir))

        logger.info(f"✓ Migration completed successfully!")
        logger.info(f"  Old location: {old_dir} (removed)")
        logger.info(f"  New location: {new_dir}")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        logger.error(f"Please manually move files from:")
        logger.error(f"  {old_dir} → {new_dir}")
        return False


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


# Auto-migrate from old hidden directory (v0.3.1+)
migrate_from_hidden_dir()

# Load .env file at module import
ENV_FILE_PATH = find_and_load_env()


def resolve_config_path(env_var: str, default_subdir: str, base_dir: Path) -> Path:
    """
    Resolve a path from environment variable, handling relative paths correctly.

    If the path is relative (e.g., "./data"), it's resolved relative to base_dir.
    If the path is absolute, it's used as-is.

    Args:
        env_var: Environment variable name
        default_subdir: Default subdirectory name if env var not set
        base_dir: Base directory for resolving relative paths

    Returns:
        Absolute Path object
    """
    path_str = os.getenv(env_var, str(base_dir / default_subdir))
    path = Path(path_str)

    # If path is relative, resolve it relative to base_dir
    if not path.is_absolute():
        path = base_dir / path

    return path.resolve()


class Config:
    """Global configuration class."""

    # ===== Project Paths =====
    # For installed packages, use user's directories
    USER_CONFIG_DIR = get_default_config_dir()
    DATA_DIR = resolve_config_path("DATA_DIR", "data", USER_CONFIG_DIR)
    OUTPUT_DIR = resolve_config_path("OUTPUT_DIR", "outputs", USER_CONFIG_DIR)

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
    IMAGE_MAX_WIDTH: int = int(os.getenv("IMAGE_MAX_WIDTH", "1920"))  # Full HD support

    # ===== Image Extraction & Quality =====
    # Minimum dimensions for extracted images (filters out icons/logos)
    # v0.2.5+: Increased default from 200x200 to 500x300 for better quality
    IMAGE_MIN_WIDTH: int = int(os.getenv("IMAGE_MIN_WIDTH", "500"))
    IMAGE_MIN_HEIGHT: int = int(os.getenv("IMAGE_MIN_HEIGHT", "300"))

    # Quality thresholds (0.0 ~ 1.0)
    # Extraction phase: Filter for meaningful images (diagrams, charts, text-rich images)
    # Enhanced algorithm: size(15%) + aspect(15%) + compression(20%) + content(30%) + meaningful(20%)
    IMAGE_EXTRACTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_EXTRACTION_QUALITY_THRESHOLD", "0.35"))
    # Selection phase: Strict filtering (select best images for lecture inclusion)
    IMAGE_SELECTION_QUALITY_THRESHOLD: float = float(os.getenv("IMAGE_SELECTION_QUALITY_THRESHOLD", "0.40"))

    # ===== Image Quality Analysis - Color Diversity =====
    # Standard deviation thresholds for color diversity scoring
    # Higher std = more color variation = better content
    IMAGE_STD_HIGH: int = int(os.getenv("IMAGE_STD_HIGH", "50"))  # High color diversity
    IMAGE_STD_MEDIUM: int = int(os.getenv("IMAGE_STD_MEDIUM", "30"))  # Medium diversity
    IMAGE_STD_LOW: int = int(os.getenv("IMAGE_STD_LOW", "15"))  # Low diversity
    IMAGE_STD_MINIMAL: int = int(os.getenv("IMAGE_STD_MINIMAL", "5"))  # Almost solid color

    # ===== Image Quality Analysis - Edge Density =====
    # Edge density thresholds for content structure detection
    # Higher edge density = more structure/detail = better for diagrams
    IMAGE_EDGE_DENSITY_HIGH: float = float(os.getenv("IMAGE_EDGE_DENSITY_HIGH", "0.15"))  # High detail
    IMAGE_EDGE_DENSITY_MEDIUM: float = float(os.getenv("IMAGE_EDGE_DENSITY_MEDIUM", "0.08"))  # Medium detail
    IMAGE_EDGE_DENSITY_LOW: float = float(os.getenv("IMAGE_EDGE_DENSITY_LOW", "0.04"))  # Low detail
    IMAGE_EDGE_DENSITY_MINIMAL: float = float(os.getenv("IMAGE_EDGE_DENSITY_MINIMAL", "0.02"))  # Minimal edges

    # ===== Image Quality Analysis - Compression Ratio =====
    # Bytes per pixel thresholds for compression quality
    # Higher bpp = less compression = better quality
    IMAGE_COMPRESSION_SOLID: float = float(os.getenv("IMAGE_COMPRESSION_SOLID", "0.05"))  # Solid color/icon
    IMAGE_COMPRESSION_LOW: float = float(os.getenv("IMAGE_COMPRESSION_LOW", "0.2"))  # Highly compressed
    IMAGE_COMPRESSION_MEDIUM: float = float(os.getenv("IMAGE_COMPRESSION_MEDIUM", "1.0"))  # Medium quality
    IMAGE_COMPRESSION_HIGH: float = float(os.getenv("IMAGE_COMPRESSION_HIGH", "1.5"))  # High quality

    # ===== Image Selection - Weighting Factors =====
    # Each content-type group has its own quality/importance pair.
    # All three groups share IMAGE_WEIGHT_POSITION, and each pair + position must sum to ~1.0.

    # diagram / chart: quality matters more (structured content)
    IMAGE_WEIGHT_QUALITY: float = float(os.getenv("IMAGE_WEIGHT_QUALITY", "0.35"))
    IMAGE_WEIGHT_IMPORTANCE: float = float(os.getenv("IMAGE_WEIGHT_IMPORTANCE", "0.55"))

    # screenshot / technical: page location matters slightly more than pure quality
    IMAGE_WEIGHT_QUALITY_SCREENSHOT: float = float(os.getenv("IMAGE_WEIGHT_QUALITY_SCREENSHOT", "0.25"))
    IMAGE_WEIGHT_IMPORTANCE_SCREENSHOT: float = float(os.getenv("IMAGE_WEIGHT_IMPORTANCE_SCREENSHOT", "0.65"))

    # photo / unknown: page location is the primary signal
    IMAGE_WEIGHT_QUALITY_PHOTO: float = float(os.getenv("IMAGE_WEIGHT_QUALITY_PHOTO", "0.20"))
    IMAGE_WEIGHT_IMPORTANCE_PHOTO: float = float(os.getenv("IMAGE_WEIGHT_IMPORTANCE_PHOTO", "0.70"))

    # Shared position weight across all content types
    IMAGE_WEIGHT_POSITION: float = float(os.getenv("IMAGE_WEIGHT_POSITION", "0.10"))  # Location proximity weight

    # ===== Image Content Detection =====
    # Threshold for meaningful content detection (diagrams, charts, text)
    IMAGE_MEANINGFUL_CONTENT_THRESHOLD: float = float(os.getenv("IMAGE_MEANINGFUL_CONTENT_THRESHOLD", "0.8"))
    # Bonus score for detected high-value content
    IMAGE_DIAGRAM_BONUS: float = float(os.getenv("IMAGE_DIAGRAM_BONUS", "0.10"))

    # ===== Image Aspect Ratio Bounds =====
    # Valid aspect ratio range (width/height)
    IMAGE_ASPECT_RATIO_MIN: float = float(os.getenv("IMAGE_ASPECT_RATIO_MIN", "0.3"))  # Very tall
    IMAGE_ASPECT_RATIO_MAX: float = float(os.getenv("IMAGE_ASPECT_RATIO_MAX", "3.0"))  # Very wide

    # ===== Vector DB =====
    VECTOR_DB_PATH: Path = resolve_config_path("VECTOR_DB_PATH", "vector_db", DATA_DIR)
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # ===== RAG Cache =====
    RAG_CACHE_PATH: Path = resolve_config_path("RAG_CACHE_PATH", "rag_cache", DATA_DIR)
    RAG_CACHE_TTL: int = int(os.getenv("RAG_CACHE_TTL", "86400"))  # 24 hours in seconds
    RAG_CACHE_MAX_SIZE: int = int(os.getenv("RAG_CACHE_MAX_SIZE", "1000"))  # Max number of cached queries

    # ===== RAG Query Settings =====
    # Default number of documents to retrieve per query
    RAG_DEFAULT_RESULTS: int = int(os.getenv("RAG_DEFAULT_RESULTS", "10"))
    # Top-k results for context building
    RAG_TOP_K_RESULTS: int = int(os.getenv("RAG_TOP_K_RESULTS", "5"))
    # Q&A mode: dual-query retrieval count (original + translated each)
    RAG_QA_N_RESULTS: int = int(os.getenv("RAG_QA_N_RESULTS", "15"))
    # Q&A mode: top-k after merge and re-ranking
    RAG_QA_TOP_K: int = int(os.getenv("RAG_QA_TOP_K", "12"))
    # Content generation: RAG retrieval count per section query
    RAG_CONTENT_N_RESULTS: int = int(os.getenv("RAG_CONTENT_N_RESULTS", "10"))

    # ===== RAG Similarity & Diversity =====
    # Minimum similarity score to include a result (L2 distance based)
    RAG_SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))
    # Number of top results to keep when all results fall below threshold
    RAG_MIN_FALLBACK_RESULTS: int = int(os.getenv("RAG_MIN_FALLBACK_RESULTS", "3"))
    # Maximum chunks allowed from the same source-page in diversity selection
    RAG_MAX_CHUNKS_PER_SOURCE_PAGE: int = int(os.getenv("RAG_MAX_CHUNKS_PER_SOURCE_PAGE", "3"))

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

    # Content quality metric constants
    # Reading speed used for completeness check (expected content volume)
    CONTENT_READING_WPM: int = int(os.getenv("CONTENT_READING_WPM", "250"))
    # Fraction of lecture time expected to be covered by text (completeness)
    CONTENT_TIME_COVERAGE: float = float(os.getenv("CONTENT_TIME_COVERAGE", "0.7"))
    # Minutes per code block baseline (1 code block expected per N minutes)
    CONTENT_CODE_PER_MINUTES: int = int(os.getenv("CONTENT_CODE_PER_MINUTES", "30"))
    # Words per minute bounds for time-alignment score
    CONTENT_WPM_MIN: int = int(os.getenv("CONTENT_WPM_MIN", "150"))
    CONTENT_WPM_MAX: int = int(os.getenv("CONTENT_WPM_MAX", "250"))
    # Minimum number of sections for structural checks
    CONTENT_MIN_SECTIONS: int = int(os.getenv("CONTENT_MIN_SECTIONS", "3"))

    # ===== Content Generation - Section Structure =====
    # Content distribution ratios for section parts (should sum to 1.0)
    CONTENT_INTRO_RATIO: float = float(os.getenv("CONTENT_INTRO_RATIO", "0.10"))  # 10% intro
    CONTENT_MAIN_RATIO: float = float(os.getenv("CONTENT_MAIN_RATIO", "0.70"))  # 70% main content
    CONTENT_SUMMARY_RATIO: float = float(os.getenv("CONTENT_SUMMARY_RATIO", "0.20"))  # 20% summary

    # Content quality improvement thresholds
    CONTENT_MIN_QUALITY_IMPROVEMENT: int = int(os.getenv("CONTENT_MIN_QUALITY_IMPROVEMENT", "3"))  # Minimum score improvement
    CONTENT_MAX_EXPANSION_ITERATIONS: int = int(os.getenv("CONTENT_MAX_EXPANSION_ITERATIONS", "2"))  # Max expansion attempts

    # ===== Slide Generation =====
    MAX_ITEMS_PER_SLIDE: int = int(os.getenv("MAX_ITEMS_PER_SLIDE", "6"))  # Maximum content blocks per slide

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

        # Validate numeric ranges
        if not 0.0 <= cls.TEMPERATURE <= 1.0:
            errors.append(
                f"❌ TEMPERATURE must be between 0.0 and 1.0, got {cls.TEMPERATURE}"
            )
        if not 0 <= cls.QUALITY_THRESHOLD <= 100:
            errors.append(
                f"❌ QUALITY_THRESHOLD must be between 0 and 100, got {cls.QUALITY_THRESHOLD}"
            )
        if not 0 <= cls.QUALITY_THRESHOLD_SECTION <= 100:
            errors.append(
                f"❌ QUALITY_THRESHOLD_SECTION must be between 0 and 100, got {cls.QUALITY_THRESHOLD_SECTION}"
            )
        if not 1 <= cls.MAX_ITERATIONS <= 10:
            errors.append(
                f"❌ MAX_ITERATIONS must be between 1 and 10, got {cls.MAX_ITERATIONS}"
            )
        if cls.CHUNK_SIZE <= 0:
            errors.append(
                f"❌ CHUNK_SIZE must be positive, got {cls.CHUNK_SIZE}"
            )
        if not 0 <= cls.CHUNK_OVERLAP < cls.CHUNK_SIZE:
            errors.append(
                f"❌ CHUNK_OVERLAP must be >= 0 and < CHUNK_SIZE ({cls.CHUNK_SIZE}), got {cls.CHUNK_OVERLAP}"
            )

        # Validate weight constants sum to 1.0 for each content-type group
        for group_name, q_weight, imp_weight in [
            ("diagram/chart", cls.IMAGE_WEIGHT_QUALITY, cls.IMAGE_WEIGHT_IMPORTANCE),
            ("screenshot/technical", cls.IMAGE_WEIGHT_QUALITY_SCREENSHOT, cls.IMAGE_WEIGHT_IMPORTANCE_SCREENSHOT),
            ("photo/unknown", cls.IMAGE_WEIGHT_QUALITY_PHOTO, cls.IMAGE_WEIGHT_IMPORTANCE_PHOTO),
        ]:
            weight_sum = q_weight + imp_weight + cls.IMAGE_WEIGHT_POSITION
            if abs(weight_sum - 1.0) > 0.01:
                errors.append(
                    f"❌ IMAGE_WEIGHT_* values for {group_name} must sum to 1.0, got {weight_sum:.3f}\n"
                    "   Check IMAGE_WEIGHT_QUALITY/IMPORTANCE/POSITION variants in .env"
                )

        content_ratio_sum = (
            cls.CONTENT_INTRO_RATIO
            + cls.CONTENT_MAIN_RATIO
            + cls.CONTENT_SUMMARY_RATIO
        )
        if abs(content_ratio_sum - 1.0) > 0.01:
            errors.append(
                f"❌ CONTENT_*_RATIO values must sum to 1.0, got {content_ratio_sum:.3f}\n"
                "   Check CONTENT_INTRO_RATIO, CONTENT_MAIN_RATIO, CONTENT_SUMMARY_RATIO in .env"
            )

        if errors:
            # Import here to avoid circular dependency
            from lecture_forge.exceptions import ConfigurationError

            raise ConfigurationError("\n" + "\n".join(errors))

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
