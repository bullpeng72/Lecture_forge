"""
Unit tests for LectureForge exception hierarchy.
"""

import pytest

from lecture_forge.exceptions import (
    AgentExecutionError,
    CacheError,
    ConfigurationError,
    ContentCollectionError,
    ContentGenerationError,
    DiagramGenerationError,
    EmbeddingError,
    FileValidationError,
    HTMLAssemblyError,
    ImageExtractionError,
    ImageProcessingError,
    ImageQualityError,
    ImageSearchError,
    InvalidConfigurationError,
    InvalidInputError,
    LectureForgeError,
    LLMAPIError,
    MetricsCalculationError,
    MissingAPIKeyError,
    PDFParsingError,
    QualityEvaluationError,
    RAGError,
    RetrievalError,
    RevisionError,
    SearchAPIError,
    TemplateError,
    TemplateNotFoundError,
    ValidationError,
    VectorDBError,
    WebScrapingError,
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_base_exception(self):
        e = LectureForgeError("base error")
        assert isinstance(e, Exception)
        assert str(e) == "base error"

    # --- Content Collection ---
    def test_content_collection_error(self):
        e = ContentCollectionError("collect fail")
        assert isinstance(e, LectureForgeError)

    def test_pdf_parsing_error(self):
        e = PDFParsingError("pdf fail")
        assert isinstance(e, ContentCollectionError)
        assert isinstance(e, LectureForgeError)

    def test_web_scraping_error(self):
        e = WebScrapingError("scrape fail")
        assert isinstance(e, ContentCollectionError)

    def test_search_api_error(self):
        e = SearchAPIError("search fail")
        assert isinstance(e, ContentCollectionError)

    # --- RAG ---
    def test_rag_error(self):
        e = RAGError("rag fail")
        assert isinstance(e, LectureForgeError)

    def test_vector_db_error(self):
        e = VectorDBError("db fail")
        assert isinstance(e, RAGError)

    def test_embedding_error(self):
        e = EmbeddingError("embed fail")
        assert isinstance(e, RAGError)

    def test_retrieval_error(self):
        e = RetrievalError("retrieve fail")
        assert isinstance(e, RAGError)

    def test_cache_error(self):
        e = CacheError("cache fail")
        assert isinstance(e, RAGError)

    # --- Image Processing ---
    def test_image_processing_error(self):
        e = ImageProcessingError("image fail")
        assert isinstance(e, LectureForgeError)

    def test_image_extraction_error(self):
        e = ImageExtractionError("extract fail")
        assert isinstance(e, ImageProcessingError)

    def test_image_quality_error(self):
        e = ImageQualityError("quality fail")
        assert isinstance(e, ImageProcessingError)

    def test_image_search_error(self):
        e = ImageSearchError("search fail")
        assert isinstance(e, ImageProcessingError)

    # --- Content Generation ---
    def test_content_generation_error(self):
        e = ContentGenerationError("gen fail")
        assert isinstance(e, LectureForgeError)

    def test_llm_api_error(self):
        e = LLMAPIError("llm fail")
        assert isinstance(e, ContentGenerationError)

    def test_diagram_generation_error(self):
        e = DiagramGenerationError("diagram fail")
        assert isinstance(e, ContentGenerationError)

    def test_html_assembly_error(self):
        e = HTMLAssemblyError("html fail")
        assert isinstance(e, ContentGenerationError)

    # --- Quality Evaluation ---
    def test_quality_evaluation_error(self):
        e = QualityEvaluationError("qual fail")
        assert isinstance(e, LectureForgeError)

    def test_metrics_calculation_error(self):
        e = MetricsCalculationError("metrics fail")
        assert isinstance(e, QualityEvaluationError)

    def test_revision_error(self):
        e = RevisionError("revision fail")
        assert isinstance(e, QualityEvaluationError)

    # --- Configuration ---
    def test_configuration_error(self):
        e = ConfigurationError("config fail")
        assert isinstance(e, LectureForgeError)

    def test_missing_api_key_error(self):
        e = MissingAPIKeyError("OPENAI_API_KEY")
        assert isinstance(e, ConfigurationError)
        assert "OPENAI_API_KEY" in str(e)
        assert e.key_name == "OPENAI_API_KEY"
        assert e.service_url is None

    def test_missing_api_key_error_with_url(self):
        e = MissingAPIKeyError("PEXELS_API_KEY", service_url="https://pexels.com/api")
        assert "pexels.com" in str(e)
        assert e.service_url == "https://pexels.com/api"

    def test_invalid_configuration_error(self):
        e = InvalidConfigurationError("QUALITY_THRESHOLD", 150, "must be 0-100")
        assert isinstance(e, ConfigurationError)
        assert e.config_name == "QUALITY_THRESHOLD"
        assert e.value == 150
        assert e.reason == "must be 0-100"

    # --- Template ---
    def test_template_error(self):
        e = TemplateError("tmpl fail")
        assert isinstance(e, LectureForgeError)

    def test_template_not_found_error(self):
        e = TemplateNotFoundError("my_template")
        assert isinstance(e, TemplateError)
        assert e.template_name == "my_template"
        assert e.search_paths is None

    def test_template_not_found_with_paths(self):
        e = TemplateNotFoundError("t.html", search_paths=["/a", "/b"])
        assert "/a" in str(e)

    # --- Agent Execution ---
    def test_agent_execution_error(self):
        e = AgentExecutionError("ContentWriter", "LLM call failed")
        assert isinstance(e, LectureForgeError)
        assert "ContentWriter" in str(e)
        assert e.agent_name == "ContentWriter"
        assert e.original_error is None

    def test_agent_execution_error_with_original(self):
        orig = ValueError("network error")
        e = AgentExecutionError("QAAgent", "retrieval failed", original_error=orig)
        assert e.original_error is orig
        assert "ValueError" in str(e)

    # --- Validation ---
    def test_validation_error(self):
        e = ValidationError("val fail")
        assert isinstance(e, LectureForgeError)

    def test_invalid_input_error(self):
        e = InvalidInputError("bad input")
        assert isinstance(e, ValidationError)

    def test_file_validation_error(self):
        e = FileValidationError("/path/to/file.pdf", "file not found")
        assert isinstance(e, ValidationError)
        assert e.file_path == "/path/to/file.pdf"
        assert e.reason == "file not found"
        assert "/path/to/file.pdf" in str(e)


class TestExceptionRaising:
    """Test raising and catching exceptions."""

    def test_catch_as_base(self):
        with pytest.raises(LectureForgeError):
            raise PDFParsingError("test")

    def test_catch_as_specific(self):
        with pytest.raises(PDFParsingError):
            raise PDFParsingError("test")

    def test_exception_message(self):
        msg = "specific error message"
        try:
            raise LLMAPIError(msg)
        except LLMAPIError as e:
            assert str(e) == msg

    def test_exception_chaining(self):
        original = ValueError("original error")
        try:
            raise ContentGenerationError("wrapped") from original
        except ContentGenerationError as e:
            assert e.__cause__ is original
