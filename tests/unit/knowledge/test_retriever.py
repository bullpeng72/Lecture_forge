"""
Unit tests for RAGRetriever.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lecture_forge.knowledge.retriever import RAGRetriever


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for retriever tests."""
    store = MagicMock()
    store.query.return_value = {
        "documents": [["chunk1 content", "chunk2 content"]],
        "metadatas": [[{"source": "test.pdf", "page": 1}, {"source": "test.pdf", "page": 2}]],
        "distances": [[0.1, 0.3]],
    }
    return store


@pytest.fixture
def retriever(mock_vector_store, tmp_path):
    """RAGRetriever with mocked VectorStore and tmp cache path."""
    return RAGRetriever(vector_store=mock_vector_store, cache_path=tmp_path / "rag_cache")


def test_initialization(retriever, mock_vector_store):
    """RAGRetriever initializes with vector store and cache settings."""
    assert retriever.vector_store is mock_vector_store
    assert retriever.cache_path is not None
    assert retriever.cache_ttl > 0
    assert retriever.cache_max_size > 0


def test_cache_key_deterministic(retriever):
    """Same query and k always produce the same cache key."""
    key1 = retriever._get_cache_key("test query", 5)
    key2 = retriever._get_cache_key("test query", 5)
    assert key1 == key2


def test_cache_key_differs_by_query(retriever):
    """Different queries produce different cache keys."""
    key1 = retriever._get_cache_key("query A", 5)
    key2 = retriever._get_cache_key("query B", 5)
    assert key1 != key2


def test_cache_key_differs_by_k(retriever):
    """Different k values produce different cache keys."""
    key1 = retriever._get_cache_key("same query", 5)
    key2 = retriever._get_cache_key("same query", 10)
    assert key1 != key2


def test_retrieve_queries_vector_store(retriever, mock_vector_store):
    """retrieve() queries the vector store on cache miss."""
    docs = retriever.retrieve("machine learning", k=5)

    mock_vector_store.query.assert_called_once_with("machine learning", n_results=5)
    assert len(docs) == 2  # Two documents from mock


def test_retrieve_returns_correct_format(retriever):
    """retrieve() returns list of dicts with content, metadata, distance."""
    docs = retriever.retrieve("test query", k=5)

    assert isinstance(docs, list)
    assert len(docs) > 0
    for doc in docs:
        assert "content" in doc
        assert "metadata" in doc
        assert "distance" in doc


def test_retrieve_cache_hit(retriever, mock_vector_store):
    """Second call with same query returns cached result without querying VectorStore."""
    query = "neural networks"
    docs1 = retriever.retrieve(query, k=5)
    docs2 = retriever.retrieve(query, k=5)

    # VectorStore should only be called once
    assert mock_vector_store.query.call_count == 1
    assert docs1 == docs2


def test_retrieve_cache_miss_different_query(retriever, mock_vector_store):
    """Different queries each hit the VectorStore."""
    retriever.retrieve("query A", k=5)
    retriever.retrieve("query B", k=5)

    assert mock_vector_store.query.call_count == 2


def test_retrieve_cache_miss_different_k(retriever, mock_vector_store):
    """Same query with different k values each hit the VectorStore."""
    retriever.retrieve("same query", k=5)
    retriever.retrieve("same query", k=10)

    assert mock_vector_store.query.call_count == 2


def test_cache_hit_counter(retriever):
    """Cache hit counter increments on cache hits."""
    retriever.retrieve("test", k=5)
    retriever.retrieve("test", k=5)  # Cache hit

    assert retriever._cache_hits == 1
    assert retriever._cache_misses == 1


def test_cache_miss_counter(retriever, mock_vector_store):
    """Cache miss counter increments on new queries."""
    retriever.retrieve("query 1", k=5)
    retriever.retrieve("query 2", k=5)

    assert retriever._cache_misses == 2
    assert retriever._cache_hits == 0


def test_clear_cache(retriever):
    """clear_cache empties the cache and resets counters."""
    retriever.retrieve("test query", k=5)
    retriever.clear_cache()

    # After clearing, next call is a cache miss
    retriever.retrieve("test query", k=5)
    assert retriever._cache_misses == 1  # Only the post-clear miss counts


def test_get_cache_stats_structure(retriever):
    """get_cache_stats returns dict with expected keys."""
    stats = retriever.get_cache_stats()

    assert "cache_hits" in stats
    assert "cache_misses" in stats
    assert "cache_size" in stats
    assert "hit_rate_percent" in stats
    assert "cache_path" in stats
    assert "cache_ttl_seconds" in stats


def test_get_cache_stats_hit_rate(retriever):
    """hit_rate_percent is calculated correctly."""
    retriever.retrieve("q1", k=5)  # miss
    retriever.retrieve("q1", k=5)  # hit
    retriever.retrieve("q2", k=5)  # miss

    stats = retriever.get_cache_stats()
    # 1 hit out of 3 total = 33.33%
    assert abs(stats["hit_rate_percent"] - 33.33) < 1.0


def test_get_cache_stats_no_queries(retriever):
    """hit_rate_percent is 0 when no queries made."""
    stats = retriever.get_cache_stats()
    assert stats["hit_rate_percent"] == 0.0


def test_format_context_basic(retriever):
    """format_context formats documents with source and content."""
    documents = [
        {"content": "Machine learning is...", "metadata": {"source": "ml.pdf", "page": 1}},
        {"content": "Deep learning uses...", "metadata": {"source": "dl.pdf"}},
    ]
    context = retriever.format_context(documents)

    assert "ml.pdf" in context
    assert "Machine learning is..." in context
    assert "Deep learning uses..." in context
    assert "Document 1" in context
    assert "Document 2" in context


def test_format_context_with_page(retriever):
    """format_context includes page number when available."""
    documents = [
        {"content": "Content here", "metadata": {"source": "test.pdf", "page": 5}},
    ]
    context = retriever.format_context(documents)

    assert "Page: 5" in context


def test_format_context_empty(retriever):
    """format_context with empty list returns empty string."""
    context = retriever.format_context([])
    assert context == ""


def test_retrieve_uses_default_k(retriever, mock_vector_store):
    """retrieve() uses Config.RAG_TOP_K_RESULTS when k is None."""
    from lecture_forge.config import Config

    retriever.retrieve("test query")
    mock_vector_store.query.assert_called_once_with("test query", n_results=Config.RAG_TOP_K_RESULTS)
