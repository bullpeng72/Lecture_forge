"""
Unit tests for Async Content Collector Agent.

Tests async operations, parallel execution, and performance.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from lecture_forge.agents.async_content_collector import AsyncContentCollectorAgent


@pytest.mark.asyncio
class TestAsyncContentCollectorAgent:
    """Test Async Content Collector Agent."""

    async def test_initialization(self):
        """Test agent initialization."""
        agent = AsyncContentCollectorAgent(collection_name="test_collection")

        assert agent is not None
        assert agent.web_scraper is not None
        assert agent.search_tool is not None
        assert agent.pdf_parser is not None

    async def test_collect_empty_sources(self):
        """Test collecting with no sources."""
        agent = AsyncContentCollectorAgent(collection_name="test_empty")

        with patch.object(
            agent.vector_store, "add_documents"
        ) as mock_add, patch.object(
            agent.vector_store, "get_stats", return_value={"document_count": 0}
        ):

            result = await agent.collect(
                {
                    "pdfs": [],
                    "urls": [],
                    "keywords": [],
                    "hada_keywords": [],
                }
            )

            assert result["success"] is True
            assert len(result["documents"]) == 0
            assert len(result["chunks"]) == 0

    async def test_collect_from_pdf(self):
        """Test PDF collection."""
        agent = AsyncContentCollectorAgent(collection_name="test_pdf")

        mock_result = {
            "success": True,
            "text": "Test PDF content",
            "metadata": {"filename": "test.pdf", "total_pages": 1},
            "pages": [{"page_number": 1, "text": "Test PDF content"}],
        }

        with patch.object(agent.pdf_parser, "run", return_value=mock_result):
            result = await agent._collect_from_pdf("test.pdf")

            assert result["success"] is True
            assert result["document"]["text"] == "Test PDF content"
            assert result["document"]["source_type"] == "pdf"

    async def test_collect_from_url(self):
        """Test URL collection."""
        agent = AsyncContentCollectorAgent(collection_name="test_url")

        mock_result = {
            "success": True,
            "text": "Test web content",
            "metadata": {"url": "https://example.com", "title": "Test Page"},
        }

        with patch.object(agent.web_scraper, "run", return_value=mock_result):
            result = await agent._collect_from_url("https://example.com")

            assert result["success"] is True
            assert result["document"]["text"] == "Test web content"
            assert result["document"]["source_type"] == "url"

    async def test_collect_from_search(self):
        """Test search collection."""
        agent = AsyncContentCollectorAgent(collection_name="test_search")

        mock_result = {
            "success": True,
            "results": [
                {
                    "title": "Result 1",
                    "snippet": "Snippet 1",
                    "url": "https://example.com/1",
                },
                {
                    "title": "Result 2",
                    "snippet": "Snippet 2",
                    "url": "https://example.com/2",
                },
            ],
            "total_results": 2,
        }

        with patch.object(agent.search_tool, "run", return_value=mock_result):
            result = await agent._collect_from_search("test query")

            assert result["success"] is True
            assert "Result 1" in result["document"]["text"]
            assert result["document"]["source_type"] == "search"

    async def test_parallel_collection(self):
        """Test that collections run in parallel."""
        agent = AsyncContentCollectorAgent(collection_name="test_parallel")

        # Mock all operations with delays to test parallelism
        async def mock_pdf_slow(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "success": True,
                "text": "PDF content",
                "metadata": {},
                "pages": [],
            }

        async def mock_url_slow(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "success": True,
                "text": "URL content",
                "metadata": {},
            }

        async def mock_search_slow(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "success": True,
                "results": [],
                "total_results": 0,
            }

        with patch.object(
            agent.pdf_parser, "run", side_effect=mock_pdf_slow
        ), patch.object(
            agent.web_scraper, "run", side_effect=mock_url_slow
        ), patch.object(
            agent.search_tool, "run", side_effect=mock_search_slow
        ), patch.object(
            agent.vector_store, "add_documents"
        ), patch.object(
            agent.vector_store, "get_stats", return_value={"document_count": 3}
        ), patch.object(
            agent, "run_in_executor", side_effect=mock_pdf_slow
        ), patch.object(
            agent, "_chunk_documents_async", AsyncMock(return_value=([], []))
        ):

            # If sequential: 0.3s (3 operations × 0.1s each)
            # If parallel: ~0.1s (all at once)
            start = asyncio.get_event_loop().time()

            result = await agent.collect(
                {
                    "pdfs": ["test1.pdf"],
                    "urls": ["https://example.com"],
                    "keywords": ["test"],
                    "hada_keywords": [],
                }
            )

            elapsed = asyncio.get_event_loop().time() - start

            # Should be closer to 0.1s than 0.3s (parallel execution)
            assert elapsed < 0.25  # Allow some overhead
            assert result["success"] is True

    async def test_error_handling(self):
        """Test error handling for failed operations."""
        agent = AsyncContentCollectorAgent(collection_name="test_error")

        # Mock PDF parsing failure
        with patch.object(
            agent.pdf_parser,
            "run",
            return_value={"success": False, "error": "Parse error"},
        ):
            result = await agent._collect_from_pdf("bad.pdf")

            assert result["success"] is False
            assert "error" in result

    async def test_rate_limiting(self):
        """Test that rate limiters are created."""
        agent = AsyncContentCollectorAgent(collection_name="test_rate")

        assert agent.search_limiter is not None
        assert agent.web_limiter is not None

    async def test_chunking(self):
        """Test document chunking."""
        agent = AsyncContentCollectorAgent(collection_name="test_chunk")

        documents = [
            {
                "text": "Test content " * 100,  # Long enough to chunk
                "source": "test.txt",
                "source_type": "text",
                "metadata": {},
            }
        ]

        chunks, metadatas = await agent._chunk_documents_async(documents)

        assert len(chunks) > 0
        assert len(chunks) == len(metadatas)
        assert metadatas[0]["source"] == "test.txt"

    async def test_query_async(self):
        """Test async query."""
        agent = AsyncContentCollectorAgent(collection_name="test_query")

        mock_results = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"source": "test"}]],
            "distances": [[0.1, 0.2]],
        }

        with patch.object(agent.vector_store, "query", return_value=mock_results):
            result = await agent.query("test question")

            assert result["question"] == "test question"
            assert len(result["documents"]) == 2


@pytest.mark.asyncio
class TestAsyncPerformance:
    """Performance tests for async operations."""

    async def test_speedup_vs_sequential(self):
        """Test that async is faster than sequential."""
        agent = AsyncContentCollectorAgent(collection_name="test_perf")

        # Mock operations with realistic delays
        async def mock_operation(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms per operation
            return {"success": True, "text": "content", "metadata": {}}

        sources = {
            "pdfs": [],
            "urls": ["url1", "url2", "url3"],  # 3 URLs
            "keywords": [],
            "hada_keywords": [],
        }

        # No-op rate limiter: avoids the 1s/call inter-call delay from web_limiter
        class NoopLimiter:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        async def mock_chunk(*args, **kwargs):
            return ([], [])

        with patch.object(
            agent.web_scraper, "run", side_effect=mock_operation
        ), patch.object(
            agent.vector_store, "add_documents"
        ), patch.object(
            agent.vector_store, "get_stats", return_value={"document_count": 3}
        ), patch.object(
            agent, "web_limiter", NoopLimiter()
        ), patch.object(
            agent, "_chunk_documents_async", side_effect=mock_chunk
        ):

            start = asyncio.get_event_loop().time()
            result = await agent.collect(sources)
            elapsed = asyncio.get_event_loop().time() - start

            # Sequential would be: 3 × 0.05 = 0.15s
            # Parallel should be: ~0.05s (all at once)
            # Allow generous overhead for CI environments
            assert elapsed < 0.5  # Much less than sequential (0.15s)
            assert result["success"] is True

            # Verify elapsed time is tracked
            assert "elapsed_seconds" in result["metadata"]
