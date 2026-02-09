"""
Smoke tests for ContentCollectorAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.content_collector import ContentCollectorAgent


@pytest.fixture
def content_collector(test_env_vars, mock_vector_store):
    """Create a ContentCollectorAgent instance with mocked dependencies."""
    with patch("lecture_forge.agents.content_collector.VectorStore") as mock_vs_class:
        mock_vs_class.return_value = mock_vector_store
        agent = ContentCollectorAgent(session_id="test_session")
        agent.vector_store = mock_vector_store
        return agent


def test_content_collector_initialization(content_collector):
    """Test that ContentCollectorAgent initializes correctly."""
    assert content_collector is not None
    assert content_collector.agent_name == "ContentCollectorAgent"
    assert content_collector.vector_store is not None


def test_collect_from_pdfs_with_mock(content_collector, sample_pdf_path):
    """Test PDF content collection with mocked PDF parser."""
    with patch("lecture_forge.agents.content_collector.PDFParserTool") as mock_pdf_tool:
        # Mock the PDF parser response
        mock_parser = MagicMock()
        mock_parser.run.return_value = {
            "success": True,
            "text": "Sample PDF content about machine learning.",
            "pages": [
                {"page_number": 1, "text": "Sample PDF content about machine learning.", "word_count": 6}
            ],
            "metadata": {"total_pages": 1, "title": "ML Tutorial"},
            "error": None,
        }
        mock_pdf_tool.return_value = mock_parser

        # Reinitialize agent with mock
        content_collector.pdf_parser = mock_parser

        # Test collection
        result = content_collector.collect(
            sources={"pdfs": [str(sample_pdf_path)], "urls": [], "keywords": []},
            topic="Machine Learning",
        )

        # Assertions
        assert result is not None
        assert "success" in result or "documents" in result


def test_collect_with_keywords(content_collector):
    """Test content collection with search keywords."""
    with patch("lecture_forge.agents.content_collector.SerperSearchTool") as mock_search:
        # Mock search results
        mock_search_instance = MagicMock()
        mock_search_instance.run.return_value = {
            "success": True,
            "results": [
                {
                    "title": "Machine Learning Guide",
                    "snippet": "Comprehensive ML tutorial covering supervised learning.",
                    "url": "https://example.com/ml",
                    "type": "organic",
                }
            ],
            "total_results": 1,
            "error": None,
        }
        mock_search.return_value = mock_search_instance

        # Reinitialize agent with mock
        content_collector.search_tool = mock_search_instance

        # Test collection
        result = content_collector.collect(
            sources={"pdfs": [], "urls": [], "keywords": ["machine learning basics"]},
            topic="Machine Learning",
        )

        # Assertions
        assert result is not None


def test_collect_handles_empty_sources(content_collector):
    """Test that collect handles empty sources gracefully."""
    result = content_collector.collect(
        sources={"pdfs": [], "urls": [], "keywords": []},
        topic="Test Topic",
    )

    # Should complete without errors even with no sources
    assert result is not None
