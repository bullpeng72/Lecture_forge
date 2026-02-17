"""
Unit tests for EmbeddingManager.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_embeddings():
    """Mock OpenAIEmbeddings instance."""
    mock = MagicMock()
    mock.embed_documents.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock.embed_query.return_value = [0.7, 0.8, 0.9]
    return mock


@pytest.fixture
def embedding_manager(test_env_vars, mock_embeddings):
    """EmbeddingManager with mocked OpenAIEmbeddings."""
    with patch("lecture_forge.knowledge.embeddings.OpenAIEmbeddings", return_value=mock_embeddings):
        from lecture_forge.knowledge.embeddings import EmbeddingManager
        manager = EmbeddingManager()
        manager._mock_embeddings = mock_embeddings
        return manager


def test_initialization(test_env_vars, mock_embeddings):
    """EmbeddingManager initializes with default model."""
    with patch("lecture_forge.knowledge.embeddings.OpenAIEmbeddings", return_value=mock_embeddings):
        from lecture_forge.knowledge.embeddings import EmbeddingManager
        manager = EmbeddingManager()
        assert manager.model is not None
        assert manager.embeddings is mock_embeddings


def test_initialization_custom_model(test_env_vars, mock_embeddings):
    """EmbeddingManager accepts custom model name."""
    with patch("lecture_forge.knowledge.embeddings.OpenAIEmbeddings", return_value=mock_embeddings):
        from lecture_forge.knowledge.embeddings import EmbeddingManager
        manager = EmbeddingManager(model="text-embedding-3-large")
        assert manager.model == "text-embedding-3-large"


def test_embed_documents(embedding_manager):
    """embed_documents returns list of embedding vectors."""
    texts = ["Hello world", "Python programming"]
    result = embedding_manager.embed_documents(texts)
    assert isinstance(result, list)
    assert len(result) == 2


def test_embed_documents_calls_underlying(embedding_manager):
    """embed_documents delegates to OpenAIEmbeddings."""
    texts = ["doc1", "doc2"]
    embedding_manager.embed_documents(texts)
    embedding_manager._mock_embeddings.embed_documents.assert_called_once_with(texts)


def test_embed_query(embedding_manager):
    """embed_query returns a single embedding vector."""
    result = embedding_manager.embed_query("What is Python?")
    assert isinstance(result, list)
    assert len(result) == 3  # mock returns [0.7, 0.8, 0.9]


def test_embed_query_calls_underlying(embedding_manager):
    """embed_query delegates to OpenAIEmbeddings."""
    query = "test query"
    embedding_manager.embed_query(query)
    embedding_manager._mock_embeddings.embed_query.assert_called_once_with(query)
