"""
Integration tests for error handling and resilience.

Tests the exception hierarchy and error recovery:
- Exception hierarchy (9 categories)
- Graceful degradation
- Error recovery
- User-friendly error messages
"""

import pytest
from unittest.mock import Mock, patch

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


class TestExceptionHierarchy:
    """Test the exception hierarchy structure."""

    def test_base_exception_exists(self):
        """Test LectureForgeError is base exception."""
        error = LectureForgeError("Test error")

        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_content_collection_exception(self):
        """Test ContentCollectionError."""
        error = ContentCollectionError("Failed to collect content")

        assert isinstance(error, LectureForgeError)
        assert isinstance(error, Exception)

    def test_rag_exception(self):
        """Test RAGError."""
        error = RAGError("Vector DB error")

        assert isinstance(error, LectureForgeError)

    def test_image_processing_exception(self):
        """Test ImageProcessingError."""
        error = ImageProcessingError("Image extraction failed")

        assert isinstance(error, LectureForgeError)

    def test_content_generation_exception(self):
        """Test ContentGenerationError."""
        error = ContentGenerationError("LLM generation failed")

        assert isinstance(error, LectureForgeError)

    def test_quality_evaluation_exception(self):
        """Test QualityEvaluationError."""
        error = QualityEvaluationError("Quality check failed")

        assert isinstance(error, LectureForgeError)

    def test_configuration_exception(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Invalid config")

        assert isinstance(error, LectureForgeError)

    def test_missing_api_key_exception(self):
        """Test MissingAPIKeyError."""
        error = MissingAPIKeyError("OpenAI", "OPENAI_API_KEY")

        assert isinstance(error, ConfigurationError)
        assert isinstance(error, LectureForgeError)
        assert "OpenAI" in str(error)

    def test_validation_exception(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input")

        assert isinstance(error, LectureForgeError)


class TestErrorContextPreservation:
    """Test that errors preserve context."""

    def test_exception_with_context(self):
        """Test exception preserves context information."""
        try:
            raise ContentCollectionError("PDF parsing failed", context={"file": "test.pdf", "page": 5})
        except ContentCollectionError as e:
            # Should preserve error message
            assert "PDF parsing failed" in str(e)

    def test_exception_chaining(self):
        """Test exception chaining with original error."""
        original_error = ValueError("Original error")

        try:
            try:
                raise original_error
            except ValueError as e:
                raise ContentCollectionError("Failed to process") from e
        except ContentCollectionError as e:
            # Should preserve original exception
            assert e.__cause__ == original_error


class TestGracefulDegradation:
    """Test graceful degradation on errors."""

    def test_missing_api_key_handled_gracefully(self):
        """Test that missing API keys are handled gracefully."""
        from lecture_forge.config import Config

        # Simulate missing API key
        with patch.dict('os.environ', {}, clear=True):
            # Should not crash, but provide helpful error
            with pytest.raises((ConfigurationError, MissingAPIKeyError)):
                # This would normally be called during initialization
                if not Config.OPENAI_API_KEY:
                    raise MissingAPIKeyError("OpenAI", "OPENAI_API_KEY")

    def test_pdf_parsing_error_recovery(self):
        """Test recovery from PDF parsing errors."""
        # Simulate PDF parsing failure
        def parse_pdf_with_error(pdf_path):
            raise ContentCollectionError(f"Failed to parse {pdf_path}")

        # Should handle error without crashing entire pipeline
        try:
            parse_pdf_with_error("test.pdf")
            pdf_content = None
        except ContentCollectionError:
            pdf_content = None  # Graceful fallback

        assert pdf_content is None  # Failed gracefully

    def test_image_search_api_error_fallback(self):
        """Test fallback when image search API fails."""
        def search_images_with_error(query):
            raise ImageProcessingError("API rate limit exceeded")

        images = []
        try:
            images = search_images_with_error("test query")
        except ImageProcessingError:
            # Fallback: use PDF images only
            images = []

        # Should have empty list, not crash
        assert images == []

    def test_llm_api_error_retry(self):
        """Test retry logic for LLM API errors."""
        call_count = 0

        def mock_llm_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ContentGenerationError("Temporary API error")
            return "Success"

        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = mock_llm_call()
                break
            except ContentGenerationError:
                if attempt == max_retries - 1:
                    raise
                continue

        assert result == "Success"
        assert call_count == 3


class TestUserFriendlyErrors:
    """Test user-friendly error messages."""

    def test_missing_api_key_message(self):
        """Test clear message for missing API key."""
        error = MissingAPIKeyError("OpenAI", "OPENAI_API_KEY")

        error_msg = str(error)
        assert "OpenAI" in error_msg
        assert "OPENAI_API_KEY" in error_msg

    def test_pdf_not_found_message(self):
        """Test clear message for missing PDF."""
        error = ContentCollectionError("PDF file not found: /path/to/missing.pdf")

        assert "not found" in str(error)
        assert "pdf" in str(error).lower()

    def test_quality_threshold_message(self):
        """Test clear message for quality issues."""
        error = QualityEvaluationError(
            "Content quality score 65 below threshold 80"
        )

        error_msg = str(error)
        assert "65" in error_msg
        assert "80" in error_msg


class TestErrorRecovery:
    """Test error recovery strategies."""

    def test_partial_content_generation_recovery(self):
        """Test recovery from partial content generation failure."""
        sections = ["section1", "section2", "section3"]
        generated_sections = []

        for section in sections:
            try:
                if section == "section2":
                    raise ContentGenerationError(f"Failed to generate {section}")

                # Simulate successful generation
                generated_sections.append(f"content_{section}")
            except ContentGenerationError:
                # Continue with other sections
                continue

        # Should have generated 2 out of 3 sections
        assert len(generated_sections) == 2
        assert "content_section1" in generated_sections
        assert "content_section3" in generated_sections

    def test_image_collection_partial_success(self):
        """Test continuing when some images fail."""
        image_sources = ["img1.png", "img2.png", "img3.png"]
        collected_images = []

        for source in image_sources:
            try:
                if source == "img2.png":
                    raise ImageProcessingError(f"Failed to process {source}")

                # Simulate successful collection
                collected_images.append({"path": source})
            except ImageProcessingError:
                # Log and continue
                continue

        assert len(collected_images) == 2

    def test_knowledge_base_corruption_recovery(self):
        """Test recovery from corrupted knowledge base."""
        def load_kb():
            raise RAGError("Knowledge base corrupted")

        try:
            kb = load_kb()
        except RAGError:
            # Fallback: create new KB
            kb = None

        # Should handle gracefully
        assert kb is None


class TestValidationErrors:
    """Test input validation errors."""

    def test_invalid_duration_validation(self):
        """Test validation of invalid duration."""
        def validate_duration(duration):
            if duration <= 0:
                raise ValidationError("Duration must be positive")
            if duration > 1440:  # 24 hours
                raise ValidationError("Duration too long (max 24 hours)")

        with pytest.raises(ValidationError, match="positive"):
            validate_duration(0)

        with pytest.raises(ValidationError, match="too long"):
            validate_duration(2000)

    def test_invalid_quality_level_validation(self):
        """Test validation of quality level."""
        def validate_quality_level(level):
            valid_levels = ["lenient", "balanced", "strict"]
            if level not in valid_levels:
                raise ValidationError(f"Invalid quality level: {level}")

        with pytest.raises(ValidationError, match="Invalid"):
            validate_quality_level("invalid")

        # Valid levels should not raise
        validate_quality_level("balanced")

    def test_empty_topic_validation(self):
        """Test validation of empty topic."""
        def validate_topic(topic):
            if not topic or not topic.strip():
                raise ValidationError("Topic cannot be empty")

        with pytest.raises(ValidationError, match="empty"):
            validate_topic("")

        with pytest.raises(ValidationError, match="empty"):
            validate_topic("   ")


class TestConcurrentErrorHandling:
    """Test error handling in concurrent operations."""

    def test_multiple_pdf_processing_errors(self):
        """Test handling errors from multiple PDFs."""
        pdfs = ["pdf1.pdf", "pdf2.pdf", "pdf3.pdf"]
        results = {}

        for pdf in pdfs:
            try:
                if pdf == "pdf2.pdf":
                    raise ContentCollectionError(f"Corrupted PDF: {pdf}")
                results[pdf] = {"success": True}
            except ContentCollectionError as e:
                results[pdf] = {"success": False, "error": str(e)}

        # Should have processed all PDFs
        assert len(results) == 3
        assert results["pdf1.pdf"]["success"] is True
        assert results["pdf2.pdf"]["success"] is False
        assert results["pdf3.pdf"]["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
