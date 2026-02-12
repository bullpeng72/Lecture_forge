"""
LectureForge Pro - AI-Powered Lecture Material Generator

A LangChain-based multi-agent system for generating high-quality lecture materials
from various sources (PDF, URLs, web search).
"""

from lecture_forge.__version__ import __version__

# Import commonly used exceptions for convenience
from lecture_forge.exceptions import (
    LectureForgeError,
    ContentCollectionError,
    RAGError,
    ImageProcessingError,
    ContentGenerationError,
    QualityEvaluationError,
    ConfigurationError,
    MissingAPIKeyError,
    ValidationError,
)

__all__ = [
    "__version__",
    # Exceptions
    "LectureForgeError",
    "ContentCollectionError",
    "RAGError",
    "ImageProcessingError",
    "ContentGenerationError",
    "QualityEvaluationError",
    "ConfigurationError",
    "MissingAPIKeyError",
    "ValidationError",
]
