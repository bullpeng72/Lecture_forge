"""
Integration tests for knowledge base pipeline.
"""

import pytest
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.knowledge.chunker import TextChunker
from lecture_forge.knowledge.retriever import RAGRetriever


@pytest.mark.integration
class TestKnowledgePipeline:
    """Test the complete knowledge base pipeline."""

    def test_end_to_end_knowledge_flow(self, temp_dir, sample_text_content):
        """Test complete flow: chunk -> store -> retrieve."""
        # Setup
        collection_name = "test_collection"

        # 1. Chunk text
        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        chunks = chunker.chunk_text(sample_text_content)

        assert len(chunks) > 0, "Chunking should produce at least one chunk"

        # 2. Create vector store and add documents
        vector_store = VectorStore(collection_name=collection_name)

        # Add chunks with metadata
        vector_store.add_documents(
            documents=chunks,
            metadatas=[{"source": "test", "chunk_id": i} for i in range(len(chunks))],
            ids=[f"chunk_{i}" for i in range(len(chunks))],
        )

        # 3. Query vector store
        retriever = RAGRetriever(vector_store=vector_store)
        results = retriever.retrieve("machine learning types", k=3)

        # Assertions
        assert len(results) > 0, "Should retrieve at least one document"
        assert all("content" in doc for doc in results), "All results should have content"
        assert all("metadata" in doc for doc in results), "All results should have metadata"

        # Check that relevant content is retrieved
        all_content = " ".join(doc["content"] for doc in results)
        assert any(keyword in all_content.lower() for keyword in ["machine", "learning", "supervised"])

    def test_vector_store_persistence(self, temp_dir, sample_text_content):
        """Test that vector store persists across instances."""
        collection_name = "persist_test"

        # Create and populate vector store
        vector_store1 = VectorStore(collection_name=collection_name)
        vector_store1.add_documents(
            documents=["Test document 1", "Test document 2"],
            metadatas=[{"source": "test1"}, {"source": "test2"}],
            ids=["doc_1", "doc_2"],
        )

        # Create new instance with same collection name
        vector_store2 = VectorStore(collection_name=collection_name)

        # Query second instance
        results = vector_store2.query("test document", n_results=2)

        assert len(results["documents"][0]) > 0, "Should retrieve persisted documents"

    def test_retriever_relevance_ranking(self, temp_dir):
        """Test that retriever ranks results by relevance."""
        collection_name = "ranking_test"

        # Create vector store with diverse content
        vector_store = VectorStore(collection_name=collection_name)

        documents = [
            "Python is a programming language used for machine learning.",
            "JavaScript is used for web development.",
            "Machine learning with Python is very popular.",
            "CSS is used for styling web pages.",
        ]

        vector_store.add_documents(
            documents=documents,
            metadatas=[{"id": i} for i in range(len(documents))],
            ids=[f"doc_{i}" for i in range(len(documents))],
        )

        # Query for Python ML content
        retriever = RAGRetriever(vector_store=vector_store)
        results = retriever.retrieve("Python machine learning", k=2)

        # Check that most relevant documents are returned
        top_contents = [doc["content"].lower() for doc in results[:2]]
        assert any(
            "python" in content and "machine learning" in content for content in top_contents
        ), "Top results should contain both Python and machine learning"


@pytest.mark.integration
@pytest.mark.slow
class TestKnowledgeBaseScale:
    """Test knowledge base with larger datasets."""

    def test_large_document_processing(self, temp_dir):
        """Test processing a large number of documents."""
        collection_name = "scale_test"

        vector_store = VectorStore(collection_name=collection_name)

        # Create 100 documents
        documents = [f"This is test document number {i} about topic {i % 10}" for i in range(100)]
        metadatas = [{"doc_id": i, "topic": i % 10} for i in range(100)]
        ids = [f"doc_{i}" for i in range(100)]

        vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

        # Query and verify
        retriever = RAGRetriever(vector_store=vector_store)
        results = retriever.retrieve("document 42", k=5)

        assert len(results) > 0, "Should retrieve results from large dataset"
        assert len(results) <= 5, "Should respect k parameter"
