"""
RAG retriever for querying knowledge base with caching.
"""

import hashlib
from typing import Dict, List

from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import logger


class RAGRetriever:
    """Retriever for RAG (Retrieval Augmented Generation) with query caching."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize RAG retriever with caching.

        Args:
            vector_store: Vector store instance
        """
        self.vector_store = vector_store
        self._query_cache: Dict[str, List[Dict]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Initializing RAG retriever with query cache")

    def _get_cache_key(self, query: str, k: int) -> str:
        """
        Generate cache key from query and k parameter.

        Args:
            query: Query text
            k: Number of results

        Returns:
            MD5 hash of query:k combination
        """
        cache_string = f"{query}:{k}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve relevant documents for a query with caching.

        Args:
            query: Query text
            k: Number of documents to retrieve

        Returns:
            List of retrieved documents with metadata
        """
        # Check cache first
        cache_key = self._get_cache_key(query, k)

        if cache_key in self._query_cache:
            self._cache_hits += 1
            logger.debug(
                f"Cache HIT for query: {query[:50]}... "
                f"(hits: {self._cache_hits}, misses: {self._cache_misses})"
            )
            return self._query_cache[cache_key]

        # Cache miss - query vector store
        self._cache_misses += 1
        logger.debug(
            f"Cache MISS for query: {query[:50]}... "
            f"(hits: {self._cache_hits}, misses: {self._cache_misses})"
        )

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

        # Store in cache
        self._query_cache[cache_key] = documents

        return documents

    def clear_cache(self) -> None:
        """Clear the query cache."""
        self._query_cache.clear()
        logger.info(
            f"Query cache cleared (had {self._cache_hits} hits, {self._cache_misses} misses)"
        )
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache hits, misses, and size
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._query_cache),
            "hit_rate_percent": round(hit_rate, 2),
        }

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
