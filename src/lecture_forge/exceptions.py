"""
Custom exceptions for LectureForge.

This module defines a hierarchy of domain-specific exceptions to provide
better error handling, debugging, and user feedback throughout the application.
"""


class LectureForgeError(Exception):
    """
    Base exception for all LectureForge errors.

    All custom exceptions in LectureForge inherit from this class.
    This allows catching all LectureForge-specific errors with a single except clause.
    """

    def __init__(self, message="", context=None, **kwargs):
        super().__init__(message, **kwargs)
        self.context = context or {}


# ===== Content Collection Errors =====


class ContentCollectionError(LectureForgeError):
    """
    Error during content collection from various sources.

    This includes failures from:
    - PDF parsing
    - Web scraping
    - Search API calls
    - File I/O operations
    """

    pass


class PDFParsingError(ContentCollectionError):
    """Error during PDF file parsing or text extraction."""

    pass


class WebScrapingError(ContentCollectionError):
    """Error during web page scraping or HTML parsing."""

    pass


class SearchAPIError(ContentCollectionError):
    """Error during search API calls (Serper, etc.)."""

    pass


# ===== RAG & Vector Database Errors =====


class RAGError(LectureForgeError):
    """
    Error during RAG (Retrieval Augmented Generation) operations.

    This includes failures from:
    - Vector database operations
    - Embedding generation
    - Document retrieval
    - Cache operations
    """

    pass


class VectorDBError(RAGError):
    """Error during vector database operations (ChromaDB)."""

    pass


class EmbeddingError(RAGError):
    """Error during text embedding generation."""

    pass


class RetrievalError(RAGError):
    """Error during document retrieval or query execution."""

    pass


class CacheError(RAGError):
    """Error during cache read/write operations."""

    pass


# ===== Image Processing Errors =====


class ImageProcessingError(LectureForgeError):
    """
    Error during image processing operations.

    This includes failures from:
    - Image extraction from PDFs/web pages
    - Image quality analysis
    - Image search API calls
    - Image format conversion
    - Image file I/O
    """

    pass


class ImageExtractionError(ImageProcessingError):
    """Error during image extraction from PDF or web page."""

    pass


class ImageQualityError(ImageProcessingError):
    """Error during image quality analysis."""

    pass


class ImageSearchError(ImageProcessingError):
    """Error during image search API calls (Pexels, Unsplash)."""

    pass


# ===== Content Generation Errors =====


class ContentGenerationError(LectureForgeError):
    """
    Error during lecture content generation.

    This includes failures from:
    - LLM API calls
    - Content writing
    - Diagram generation
    - HTML assembly
    """

    pass


class LLMAPIError(ContentGenerationError):
    """Error during LLM API calls (OpenAI)."""

    pass


class DiagramGenerationError(ContentGenerationError):
    """Error during Mermaid diagram generation or validation."""

    pass


class HTMLAssemblyError(ContentGenerationError):
    """Error during HTML template rendering or assembly."""

    pass


# ===== Quality Assurance Errors =====


class QualityEvaluationError(LectureForgeError):
    """
    Error during quality evaluation or revision.

    This includes failures from:
    - Quality metric calculation
    - Content evaluation
    - Revision planning
    """

    pass


class MetricsCalculationError(QualityEvaluationError):
    """Error during quality metrics calculation."""

    pass


class RevisionError(QualityEvaluationError):
    """Error during content revision or improvement."""

    pass


# ===== Configuration Errors =====


class ConfigurationError(LectureForgeError):
    """
    Error in configuration or environment setup.

    This includes failures from:
    - Missing .env file
    - Invalid API keys
    - Missing required configuration
    - Invalid configuration values
    """

    pass


class MissingAPIKeyError(ConfigurationError):
    """Required API key is missing from configuration."""

    def __init__(self, key_name: str, service_url: str = None):
        """
        Initialize MissingAPIKeyError.

        Args:
            key_name: Name of the missing API key (e.g., "OPENAI_API_KEY")
            service_url: Optional URL where user can obtain the key
        """
        message = f"Missing required API key: {key_name}"
        if service_url:
            message += f"\nGet your key from: {service_url}"
        super().__init__(message)
        self.key_name = key_name
        self.service_url = service_url


class InvalidConfigurationError(ConfigurationError):
    """Configuration value is invalid or out of acceptable range."""

    def __init__(self, config_name: str, value: any, reason: str):
        """
        Initialize InvalidConfigurationError.

        Args:
            config_name: Name of the configuration parameter
            value: The invalid value
            reason: Explanation of why the value is invalid
        """
        message = f"Invalid configuration '{config_name}': {value}\nReason: {reason}"
        super().__init__(message)
        self.config_name = config_name
        self.value = value
        self.reason = reason


# ===== Template & Output Errors =====


class TemplateError(LectureForgeError):
    """
    Error during template processing or rendering.

    This includes failures from:
    - Template file not found
    - Template syntax errors
    - Variable substitution errors
    """

    pass


class TemplateNotFoundError(TemplateError):
    """Template file not found."""

    def __init__(self, template_name: str, search_paths: list = None):
        """
        Initialize TemplateNotFoundError.

        Args:
            template_name: Name of the missing template
            search_paths: Optional list of paths that were searched
        """
        message = f"Template not found: {template_name}"
        if search_paths:
            message += f"\nSearched in: {', '.join(str(p) for p in search_paths)}"
        super().__init__(message)
        self.template_name = template_name
        self.search_paths = search_paths


# ===== Agent Execution Errors =====


class AgentExecutionError(LectureForgeError):
    """
    Error during agent execution.

    Base class for errors that occur during agent operations.
    """

    def __init__(self, agent_name: str, message: str, original_error: Exception = None):
        """
        Initialize AgentExecutionError.

        Args:
            agent_name: Name of the agent that encountered the error
            message: Error message
            original_error: Optional original exception that was caught
        """
        full_message = f"[{agent_name}] {message}"
        if original_error:
            full_message += f"\nCaused by: {type(original_error).__name__}: {str(original_error)}"
        super().__init__(full_message)
        self.agent_name = agent_name
        self.original_error = original_error


# ===== Validation Errors =====


class ValidationError(LectureForgeError):
    """
    Error during input or data validation.

    This includes failures from:
    - Invalid file paths
    - Invalid curriculum structure
    - Invalid lecture metadata
    """

    pass


class InvalidInputError(ValidationError):
    """User input is invalid or malformed."""

    pass


class FileValidationError(ValidationError):
    """File does not exist, is not readable, or has invalid format."""

    def __init__(self, file_path: str, reason: str):
        """
        Initialize FileValidationError.

        Args:
            file_path: Path to the invalid file
            reason: Explanation of the validation failure
        """
        message = f"File validation failed: {file_path}\nReason: {reason}"
        super().__init__(message)
        self.file_path = file_path
        self.reason = reason
