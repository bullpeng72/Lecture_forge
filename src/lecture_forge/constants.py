"""
Internal algorithm constants for LectureForge.

These are fixed algorithm parameters that are **not** user-configurable.
User-configurable settings live in config.py (overridable via .env).
"""


class QualitySeverity:
    """Score thresholds that map dimension scores to issue severity levels.

    Usage in evaluator._identify_issues():
        score < QualitySeverity.HIGH   → "high" severity issue
        score < QualitySeverity.MEDIUM → "medium" severity issue
        score < QualitySeverity.LOW    → "low" severity issue
    Also used in _determine_strategy() for revision routing.
    """

    HIGH: int = 60    # below this → high-severity issue / major revision
    MEDIUM: int = 70  # below this → medium-severity issue / consult user
    LOW: int = 80     # below this → low-severity issue / auto revision


# ---------------------------------------------------------------------------
# Image quality scoring – pixel size tiers
# ---------------------------------------------------------------------------


class ImageSizeScore:
    """Pixel dimension tiers for image quality scoring (25-point scale).

    Tiers (width × height → score contribution):
        LARGE  (800 × 600)  → 0.25
        MEDIUM (600 × 400)  → 0.20
        SMALL  (400 × 300)  → 0.15
        TINY   (200 × 200)  → 0.08
        below TINY          → reject (return 0.0)
    """

    LARGE_W: int = 800
    LARGE_H: int = 600

    MEDIUM_W: int = 600
    MEDIUM_H: int = 400

    SMALL_W: int = 400
    SMALL_H: int = 300

    TINY_W: int = 200
    TINY_H: int = 200

    # Max dimension when downscaling images for content analysis
    THUMBNAIL_MAX: int = 400


# ---------------------------------------------------------------------------
# Image quality scoring – file-size tiers
# ---------------------------------------------------------------------------


class ImageFileSizeScore:
    """File size tiers for image quality scoring in bytes (15-point scale).

    Tiers:
        >= HIGH   (100 KB) → 0.15
        >= MEDIUM  (50 KB) → 0.12
        >= LOW     (10 KB) → 0.08
        below LOW          → 0.00 (likely icon/logo)
    """

    HIGH: int = 100_000    # 100 KB
    MEDIUM: int = 50_000   # 50 KB
    LOW: int = 10_000      # 10 KB


# ---------------------------------------------------------------------------
# Image quality scoring – aspect-ratio tiers
# ---------------------------------------------------------------------------


class ImageAspectScore:
    """Intermediate aspect-ratio (width/height) tiers for quality scoring.

    Extreme bounds (0.3 / 3.0) are in Config.IMAGE_ASPECT_RATIO_MIN/MAX.

    Tiers (aspect_ratio → score contribution):
        IDEAL  [0.7, 1.5] → 0.20  (portrait-to-square range)
        OK     [0.5, 2.0] → 0.15  (standard widescreen range)
        EXTREME [0.3, 3.0] (via Config) → 0.08
        outside EXTREME   → reject
    """

    IDEAL_MIN: float = 0.7
    IDEAL_MAX: float = 1.5

    OK_MIN: float = 0.5
    OK_MAX: float = 2.0


# ---------------------------------------------------------------------------
# Image quality scoring – compression-ratio tiers
# ---------------------------------------------------------------------------


class ImageCompressionScore:
    """Bytes-per-pixel tiers for compression quality scoring (15-point scale).

    Note: SOLID_COLOR, GOOD_MIN, GOOD_MAX mirror Config.IMAGE_COMPRESSION_*
    and are kept here so the scoring function is self-contained.

    Tiers (bytes/pixel → score contribution):
        GOOD  [0.2, 1.5]  → 0.15  (good compression, meaningful content)
        OK    [0.1, 2.0]  → 0.10  (acceptable range)
        < SOLID_COLOR     → reject (solid color / empty image)
        otherwise         → 0.05
    """

    GOOD_MIN: float = 0.2    # = Config.IMAGE_COMPRESSION_LOW
    GOOD_MAX: float = 1.5    # = Config.IMAGE_COMPRESSION_HIGH
    OK_MIN: float = 0.1
    OK_MAX: float = 2.0
    SOLID_COLOR: float = 0.05  # = Config.IMAGE_COMPRESSION_SOLID


# ---------------------------------------------------------------------------
# Image content analysis – color diversity scoring
# ---------------------------------------------------------------------------


class ColorDiversityScore:
    """Unique-color count and concentration tiers for color diversity scoring.

    Unique colors (50 % of subscore):
        >= MANY    (20) → 0.5
        >= MEDIUM  (10) → 0.3
        >= FEW      (5) → 0.15
        below FEW       → 0.0

    Color concentration (50 % of subscore):
        < GOOD   (0.3)  → 0.5  (well distributed)
        < MEDIUM (0.5)  → 0.3
        < POOR   (0.7)  → 0.15
        >= POOR         → reject (solid color)
    """

    MANY: int = 20
    MEDIUM_COLORS: int = 10
    FEW: int = 5

    CONCENTRATION_GOOD: float = 0.3
    CONCENTRATION_MEDIUM: float = 0.5
    CONCENTRATION_POOR: float = 0.7


# ---------------------------------------------------------------------------
# Image content analysis – edge detection
# ---------------------------------------------------------------------------


EDGE_PIXEL_THRESHOLD: int = 30
"""Pixel brightness threshold (0–255) used to classify a pixel as an edge.

Applied as: ``(edge_array > EDGE_PIXEL_THRESHOLD).sum()``

Edge density thresholds (0.15 / 0.08 / 0.04 / 0.02) are in
Config.IMAGE_EDGE_DENSITY_HIGH / MEDIUM / LOW / MINIMAL.
"""


# ---------------------------------------------------------------------------
# Image content analysis – Shannon entropy tiers
# ---------------------------------------------------------------------------


class ContentEntropyScore:
    """Shannon entropy tiers for content-complexity scoring.

    Max entropy for an 8-bit image channel = 8 bits.

    Tiers (avg_entropy → score):
        >= VERY_HIGH (6.0) → 1.0
        >= HIGH      (5.0) → 0.8
        >= MEDIUM    (4.0) → 0.6
        >= LOW       (3.0) → 0.4
        >= VERY_LOW  (2.0) → 0.2
        below VERY_LOW     → 0.0
    """

    VERY_HIGH: float = 6.0
    HIGH: float = 5.0
    MEDIUM: float = 4.0
    LOW: float = 3.0
    VERY_LOW: float = 2.0


# ---------------------------------------------------------------------------
# Image content analysis – std-dev fallback tiers (when scipy unavailable)
# ---------------------------------------------------------------------------


class StdDevScore:
    """Pixel standard-deviation tiers used as a complexity proxy when scipy
    is not available.

    Tiers (avg_std → score):
        >= HIGH         (60) → 1.0
        >= MEDIUM_HIGH  (40) → 0.7
        >= MEDIUM       (20) → 0.4
        >= LOW          (10) → 0.2
        below LOW            → 0.0
    """

    HIGH: int = 60
    MEDIUM_HIGH: int = 40
    MEDIUM: int = 20
    LOW: int = 10


# ---------------------------------------------------------------------------
# Q&A agent algorithm parameters
# ---------------------------------------------------------------------------


class QAConfig:
    """Algorithm parameters for the Q&A agent answer generation and ranking.

    These values tune internal scoring and prompt construction; they are not
    exposed as environment variables because they reflect model behaviour
    that users should not need to change.
    """

    MIN_ANSWER_WORDS: int = 400     # Minimum word count for a structured answer
    MIN_CONTEXT_REFS: int = 4       # Minimum context chunks the answer must reference
    MAX_SOURCES_RETURNED: int = 5   # Maximum unique sources shown in the response

    # Re-ranking score adjustments (applied to L2-distance→similarity score)
    SAME_LANG_BONUS: float = 0.10    # +10 %: query language == chunk language
    TRANSLATED_PENALTY: float = 0.05  # -5 %: result came from translated query
    CROSS_LINGUAL_BONUS: float = 0.05  # +5 %: cross-lingual match found


# ---------------------------------------------------------------------------
# Quality metrics – section balance
# ---------------------------------------------------------------------------


class SectionBalance:
    """Word-count balance thresholds used in quality metrics calculations.

    A section is "balanced" if its word count falls within
    [MIN_RATIO × avg, MAX_RATIO × avg].

    TOLERANCE is the relative deviation threshold:
        abs(wc - avg) / avg < TOLERANCE  →  section is balanced
    """

    TOLERANCE: float = 0.5   # 50 % deviation allowed in logical-flow scoring
    MIN_RATIO: float = 0.5   # 0.5× average (lower bound for time-alignment)
    MAX_RATIO: float = 2.0   # 2.0× average (upper bound for time-alignment)


# ---------------------------------------------------------------------------
# Quality metrics – expected word counts by difficulty level
# ---------------------------------------------------------------------------


class WordCountExpected:
    """Expected word counts per section by audience difficulty level.

    Used in level-appropriateness scoring to check if section length matches
    the target audience.
    """

    BY_LEVEL: dict = {
        "beginner": 2500,
        "intermediate": 2000,
        "advanced": 1800,
    }

    # Acceptable variation around expected count (±30 %)
    VARIATION_MIN: float = 0.7   # lower bound: 0.7 × expected
    VARIATION_MAX: float = 1.3   # upper bound: 1.3 × expected


# ---------------------------------------------------------------------------
# Quality metrics – code complexity thresholds by level
# ---------------------------------------------------------------------------


class CodeComplexity:
    """Average lines-per-code-block thresholds for level-appropriateness scoring.

    Beginner:      avg_lines <= BEGINNER_MAX        (simpler code)
    Intermediate:  INTERMEDIATE_MIN <= avg_lines <= INTERMEDIATE_MAX
    Advanced:      avg_lines >= ADVANCED_MIN        (more complex code)
    """

    BEGINNER_MAX: int = 30
    INTERMEDIATE_MIN: int = 20
    INTERMEDIATE_MAX: int = 50
    ADVANCED_MIN: int = 30
