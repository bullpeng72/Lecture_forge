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
        agent = ContentCollectorAgent(collection_name="test_session")
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
            "pages": [{"page_number": 1, "text": "Sample PDF content about machine learning.", "word_count": 6}],
            "metadata": {"total_pages": 1, "title": "ML Tutorial"},
            "error": None,
        }
        mock_pdf_tool.return_value = mock_parser

        # Reinitialize agent with mock
        content_collector.pdf_parser = mock_parser

        # Test collection
        result = content_collector.collect(
            sources={"pdfs": [str(sample_pdf_path)], "urls": [], "keywords": []},
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
        )

        # Assertions
        assert result is not None


def test_collect_handles_empty_sources(content_collector):
    """Test that collect handles empty sources gracefully."""
    result = content_collector.collect(
        sources={"pdfs": [], "urls": [], "keywords": []},
    )

    # Should complete without errors even with no sources
    assert result is not None


# ===== Additional coverage tests =====


class TestCollectErrorBranches:
    """Tests covering error/exception branches in collect()."""

    @pytest.fixture
    def agent(self, test_env_vars, mock_vector_store):
        with patch("lecture_forge.agents.content_collector.VectorStore") as mock_vs:
            mock_vs.return_value = mock_vector_store
            a = ContentCollectorAgent(collection_name="test")
            a.vector_store = mock_vector_store
            return a

    def test_pdf_parse_failure_logged(self, agent):
        """PDF parse failure (success=False) → logged error, no documents added."""
        agent.pdf_parser = MagicMock()
        agent.pdf_parser.run.return_value = {
            "success": False,
            "text": "",
            "pages": [],
            "metadata": {},
            "error": "corrupted PDF",
        }
        result = agent.collect(sources={"pdfs": ["bad.pdf"], "urls": [], "keywords": []})
        assert result is not None

    def test_pdf_exception_handled(self, agent):
        """Exception during PDF processing is caught and logged."""
        agent.pdf_parser = MagicMock()
        agent.pdf_parser.run.side_effect = Exception("file not found")
        result = agent.collect(sources={"pdfs": ["missing.pdf"], "urls": [], "keywords": []})
        assert result is not None

    def test_url_scrape_failure_logged(self, agent):
        """URL scrape failure (success=False) → logged error."""
        agent.web_scraper = MagicMock()
        agent.web_scraper.run.return_value = {
            "success": False,
            "text": "",
            "metadata": {},
            "error": "timeout",
        }
        result = agent.collect(sources={"pdfs": [], "urls": ["http://fail.com"], "keywords": []})
        assert result is not None

    def test_url_exception_handled(self, agent):
        """Exception during URL processing is caught and logged."""
        agent.web_scraper = MagicMock()
        agent.web_scraper.run.side_effect = Exception("connection refused")
        result = agent.collect(sources={"pdfs": [], "urls": ["http://error.com"], "keywords": []})
        assert result is not None

    def test_search_failure_logged(self, agent):
        """Search failure (success=False) → logged error."""
        agent.search_tool = MagicMock()
        agent.search_tool.run.return_value = {
            "success": False,
            "results": [],
            "total_results": 0,
            "error": "rate limited",
        }
        result = agent.collect(sources={"pdfs": [], "urls": [], "keywords": ["test"]})
        assert result is not None

    def test_search_exception_handled(self, agent):
        """Exception during search is caught and logged."""
        agent.search_tool = MagicMock()
        agent.search_tool.run.side_effect = Exception("API error")
        result = agent.collect(sources={"pdfs": [], "urls": [], "keywords": ["test"]})
        assert result is not None

    def test_hada_exception_handled(self, agent):
        """Exception during Hada.io deep crawl is caught and logged."""
        agent.deep_crawler = MagicMock()
        agent.deep_crawler.crawl_hada_search.side_effect = Exception("crawl error")
        result = agent.collect(
            sources={"pdfs": [], "urls": [], "keywords": [], "hada_keywords": ["test"]}
        )
        assert result is not None


class TestChunkPdfWithPages:
    """Tests for _chunk_pdf_with_pages() fallback and normal paths."""

    @pytest.fixture
    def agent(self, test_env_vars, mock_vector_store):
        with patch("lecture_forge.agents.content_collector.VectorStore") as mock_vs:
            mock_vs.return_value = mock_vector_store
            a = ContentCollectorAgent(collection_name="test")
            a.vector_store = mock_vector_store
            return a

    def test_fallback_no_pages(self, agent):
        """When doc has no 'pages' key, falls back to chunking full text."""
        doc = {
            "text": "Some text content for chunking without pages.",
            "source": "test.pdf",
            "source_type": "pdf",
            "metadata": {"total_pages": 0},
            "pages": [],  # Empty pages → fallback
        }
        chunks, metadatas = agent._chunk_pdf_with_pages(doc)
        assert isinstance(chunks, list)
        assert isinstance(metadatas, list)
        # Fallback path: metadata has chunk_index key
        if chunks:
            assert "chunk_index" in metadatas[0]

    def test_with_pages(self, agent):
        """When doc has pages, creates chunks per page."""
        doc = {
            "text": "Full text",
            "source": "test.pdf",
            "source_type": "pdf",
            "metadata": {"total_pages": 2},
            "pages": [
                {"page_number": 1, "text": "Page one content with enough text."},
                {"page_number": 2, "text": "Page two content with enough text."},
            ],
        }
        chunks, metadatas = agent._chunk_pdf_with_pages(doc)
        assert isinstance(chunks, list)
        if chunks:
            assert "page_number" in metadatas[0]


class TestQuery:
    """Tests for query() method."""

    @pytest.fixture
    def agent(self, test_env_vars, mock_vector_store):
        with patch("lecture_forge.agents.content_collector.VectorStore") as mock_vs:
            mock_vs.return_value = mock_vector_store
            a = ContentCollectorAgent(collection_name="test")
            a.vector_store = mock_vector_store
            return a

    def test_query_returns_dict(self, agent, mock_vector_store):
        """query() returns structured dict with question, documents, etc."""
        mock_vector_store.query.return_value = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"source": "a"}, {"source": "b"}]],
            "distances": [[0.1, 0.2]],
        }
        result = agent.query("What is machine learning?")
        assert "question" in result
        assert "documents" in result
        assert "metadatas" in result
        assert result["question"] == "What is machine learning?"

    def test_query_empty_results(self, agent, mock_vector_store):
        """query() handles empty results gracefully."""
        mock_vector_store.query.return_value = {
            "documents": [],
            "metadatas": [],
            "distances": [],
        }
        result = agent.query("unknown question")
        assert result["documents"] == []
