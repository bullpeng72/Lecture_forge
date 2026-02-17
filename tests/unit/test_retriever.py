"""
Tests for RAG retriever.
"""

from lecture_forge.knowledge.retriever import RAGRetriever


def test_retriever_initialization(mock_vector_store):
    """Test RAGRetriever initialization."""
    retriever = RAGRetriever(vector_store=mock_vector_store)
    assert retriever.vector_store == mock_vector_store


def test_retriever_retrieve(mock_vector_store):
    """Test retrieving documents."""
    retriever = RAGRetriever(vector_store=mock_vector_store)

    results = retriever.retrieve("test query", k=2)

    assert len(results) == 2
    assert all("content" in doc for doc in results)
    assert all("metadata" in doc for doc in results)


def test_retriever_format_context(mock_vector_store):
    """Test formatting retrieved documents as context."""
    retriever = RAGRetriever(vector_store=mock_vector_store)

    documents = [
        {"content": "This is document 1", "metadata": {"source": "test.pdf", "page": 1}},
        {"content": "This is document 2", "metadata": {"source": "test.pdf", "page": 2}},
    ]

    context = retriever.format_context(documents)

    assert "Document 1" in context
    assert "Document 2" in context
    assert "test.pdf" in context
    assert "This is document 1" in context
    assert "This is document 2" in context


def test_retriever_handles_empty_results(mock_vector_store):
    """Test retriever handles empty results gracefully."""
    mock_vector_store.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    retriever = RAGRetriever(vector_store=mock_vector_store)
    results = retriever.retrieve("test query", k=5)

    assert len(results) == 0


def test_retriever_custom_k_value(mock_vector_store, tmp_path):
    """Test retriever respects custom k value."""
    # Use tmp_path to avoid cache hits from previous test runs
    retriever = RAGRetriever(vector_store=mock_vector_store, cache_path=tmp_path / "rag_cache")

    retriever.retrieve("test query", k=10)

    # Check that vector_store.query was called with correct n_results
    mock_vector_store.query.assert_called_with("test query", n_results=10)
