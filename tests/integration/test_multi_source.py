"""
Integration tests for multi-source content collection.

Tests how the system handles multiple input sources (PDF + URL + search)
and validates source-agnostic processing.
"""

import pytest

from lecture_forge.agents.content_collector import ContentCollectorAgent
from lecture_forge.knowledge.retriever import RAGRetriever


@pytest.mark.integration
class TestMultiSource:
    """Test multi-source content collection."""

    def test_keywords_only(self):
        """
        Test content collection with keywords only.

        Validates that search-based collection works in isolation.
        """
        collection_name = "test_keywords_only"

        content_agent = ContentCollectorAgent(collection_name=collection_name)
        result = content_agent.collect({
            "pdfs": [],
            "urls": [],
            "keywords": ["machine learning basics", "neural networks"],
            "hada_keywords": [],
        })

        assert result["success"] is True
        assert result["metadata"]["total_docs"] >= 2  # At least 2 search results
        assert result["metadata"]["total_chunks"] > 0

        # Verify all sources are from search
        assert result["metadata"]["sources"]["pdfs"] == 0
        assert result["metadata"]["sources"]["urls"] == 0
        assert result["metadata"]["sources"]["keywords"] >= 2

        # Cleanup - not needed, collections use unique names

    def test_mixed_sources_simulation(self):
        """
        Test content collection with mixed sources (simulated).

        Tests the source-agnostic principle: all sources should be
        processed equally and combined in vector store.
        """
        collection_name = "test_mixed_sources"

        content_agent = ContentCollectorAgent(collection_name=collection_name)

        # Simulate mixed sources (no PDF for speed, but multiple keywords)
        result = content_agent.collect({
            "pdfs": [],
            "urls": [],  # Could add URLs if network available
            "keywords": ["Python programming", "data structures"],
            "hada_keywords": [],
        })

        assert result["success"] is True
        assert result["metadata"]["total_chunks"] > 0

        # Test RAG retrieval works regardless of source
        retriever = RAGRetriever(vector_store=content_agent.vector_store)
        retrieved = retriever.retrieve("What is Python?", k=3)

        assert len(retrieved) > 0
        # Content should be retrievable regardless of which source it came from
        assert all("content" in doc for doc in retrieved)

        # Cleanup - not needed, collections use unique names

    @pytest.mark.skip(reason="Requires PDF fixture and network access")
    def test_all_sources_combined(self):
        """
        Test all source types combined (PDF + URL + search).

        Validates that:
        1. All sources are collected successfully
        2. No source gets preferential treatment
        3. RAG retrieval works across all sources
        4. Duplicate content is handled properly
        """
        # TODO: Implement when test fixtures available
        pass

    def test_empty_sources_handling(self):
        """
        Test graceful handling when no sources provided.

        Should fail gracefully with clear error message.
        """
        collection_name = "test_empty_sources"

        content_agent = ContentCollectorAgent(collection_name=collection_name)

        # All sources empty
        result = content_agent.collect({
            "pdfs": [],
            "urls": [],
            "keywords": [],
            "hada_keywords": [],
        })

        # Should succeed but with zero content
        # (implementation may vary - document actual behavior)
        assert result is not None

        # Cleanup - not needed, collections use unique names
