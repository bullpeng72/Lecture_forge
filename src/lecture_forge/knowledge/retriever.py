"""
RAG retriever for querying knowledge base.
"""

from typing import Dict, List

from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import logger


class RAGRetriever:
    """Retriever for RAG (Retrieval Augmented Generation)."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize RAG retriever.

        Args:
            vector_store: Vector store instance
        """
        self.vector_store = vector_store
        logger.info("Initializing RAG retriever")

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Query text
            k: Number of documents to retrieve

        Returns:
            List of retrieved documents with metadata
        """
        logger.debug(f"Retrieving {k} documents for query: {query[:50]}...")

        results = self.vector_store.query(query, n_results=k)

        # Format results
        documents = []
        if results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                documents.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i]
                        if results.get("metadatas")
                        else {},
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else None,
                    }
                )

        return documents

    def format_context(self, documents: List[Dict]) -> str:
        """
        Format retrieved documents as context string.

        Args:
            documents: List of retrieved documents

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, doc in enumerate(documents, 1):
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "Unknown")
            page = metadata.get("page")

            context_parts.append(f"[Document {i} - Source: {source}")
            if page:
                context_parts.append(f", Page: {page}")
            context_parts.append("]\n")
            context_parts.append(doc["content"])
            context_parts.append("\n\n")

        return "".join(context_parts)
