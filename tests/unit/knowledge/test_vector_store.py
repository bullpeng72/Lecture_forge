"""
Unit tests for VectorStore.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.knowledge.vector_store import VectorStore


@pytest.fixture
def mock_collection():
    """Mock ChromaDB collection."""
    collection = MagicMock()
    collection.count.return_value = 0
    collection.query.return_value = {
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"source": "a"}, {"source": "b"}]],
        "distances": [[0.1, 0.2]],
    }
    return collection


@pytest.fixture
def mock_client(mock_collection):
    """Mock ChromaDB PersistentClient."""
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def vector_store(mock_client):
    """VectorStore with mocked ChromaDB client."""
    with patch("lecture_forge.knowledge.vector_store.chromadb.PersistentClient", return_value=mock_client):
        store = VectorStore(collection_name="test_collection")
    return store


def test_initialization(vector_store):
    """VectorStore initializes with correct collection name."""
    assert vector_store.collection_name == "test_collection"
    assert vector_store.client is not None
    assert vector_store.collection is not None


def test_initialization_default_name():
    """VectorStore auto-generates collection name when none given."""
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = MagicMock()

    with patch("lecture_forge.knowledge.vector_store.chromadb.PersistentClient", return_value=mock_client):
        store = VectorStore()

    assert store.collection_name.startswith("lecture_")


def test_add_documents(vector_store, mock_collection):
    """add_documents calls collection.add with correct arguments."""
    documents = ["doc1", "doc2"]
    metadatas = [{"source": "a"}, {"source": "b"}]
    ids = ["id1", "id2"]

    vector_store.add_documents(documents, metadatas, ids)

    mock_collection.add.assert_called_once_with(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )


def test_query_returns_results(vector_store, mock_collection):
    """query returns ChromaDB query results."""
    results = vector_store.query("test query", n_results=5)

    mock_collection.query.assert_called_once_with(
        query_texts=["test query"],
        n_results=5,
        where=None,
    )
    assert "documents" in results
    assert "metadatas" in results


def test_query_with_where_filter(vector_store, mock_collection):
    """query passes where filter to collection."""
    where = {"source": "pdf"}
    vector_store.query("test query", where=where)

    mock_collection.query.assert_called_once_with(
        query_texts=["test query"],
        n_results=5,
        where=where,
    )


def test_get_stats(vector_store, mock_collection):
    """get_stats returns dict with collection info."""
    mock_collection.count.return_value = 42

    stats = vector_store.get_stats()

    assert stats["collection_name"] == "test_collection"
    assert stats["document_count"] == 42
    assert "db_path" in stats


def test_get_stats_document_count(vector_store, mock_collection):
    """get_stats document_count matches collection count."""
    mock_collection.count.return_value = 100

    stats = vector_store.get_stats()

    assert stats["document_count"] == 100


def test_collection_error_recovery():
    """VectorStore handles collection compatibility errors gracefully."""
    mock_client = MagicMock()
    # Simulate KeyError on first get_or_create_collection (version incompatibility)
    mock_client.get_or_create_collection.side_effect = [
        KeyError("compat error"),
        MagicMock(),  # Succeeds on second call after delete
    ]
    mock_client.delete_collection.return_value = None

    with patch("lecture_forge.knowledge.vector_store.chromadb.PersistentClient", return_value=mock_client):
        # Should not raise, should use create_collection as fallback
        mock_client.create_collection.return_value = MagicMock()
        store = VectorStore(collection_name="recovery_test")

    # After KeyError, it should have called create_collection
    mock_client.create_collection.assert_called_once()


def test_collection_recovery_delete_fails():
    """Lines 54-55: delete_collection raises Exception but recovery continues."""
    from unittest.mock import MagicMock, patch
    from lecture_forge.knowledge.vector_store import VectorStore

    mock_client = MagicMock()
    # First get_or_create_collection raises KeyError
    # delete_collection also raises (line 54-55)
    mock_client.get_or_create_collection.side_effect = [
        KeyError("compat error"),
        MagicMock(),
    ]
    mock_client.delete_collection.side_effect = Exception("cannot delete")

    with patch("lecture_forge.knowledge.vector_store.chromadb.PersistentClient", return_value=mock_client):
        mock_client.create_collection.return_value = MagicMock()
        store = VectorStore(collection_name="recovery_fail_test")

    # Should still have called create_collection despite delete failure
    mock_client.create_collection.assert_called_once()
