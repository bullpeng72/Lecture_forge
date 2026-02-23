"""
RAG retriever for querying knowledge base with caching.
"""

import hashlib
import shelve
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import logger


class RAGRetriever:
    """Retriever for RAG (Retrieval Augmented Generation) with persistent query caching."""

    def __init__(self, vector_store: VectorStore, cache_path: Optional[Path] = None):
        """
        Initialize RAG retriever with persistent caching.

        Args:
            vector_store: Vector store instance
            cache_path: Path to cache directory (default from Config)
        """
        self.vector_store = vector_store

        # Setup persistent cache
        self.cache_path = cache_path if cache_path is not None else Config.RAG_CACHE_PATH
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # Cache settings
        self.cache_ttl = Config.RAG_CACHE_TTL
        self.cache_max_size = Config.RAG_CACHE_MAX_SIZE

        # Shelve database for persistent cache
        self._cache_file = str(self.cache_path / "query_cache.db")

        # Statistics (in-memory)
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(
            f"Initializing RAG retriever with persistent cache "
            f"(path: {self.cache_path}, TTL: {self.cache_ttl}s, max: {self.cache_max_size})"
        )

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

    def retrieve(self, query: str, k: int = None) -> List[Dict]:
        """
        Retrieve relevant documents for a query with persistent caching.

        Args:
            query: Query text
            k: Number of documents to retrieve (default from Config)

        Returns:
            List of retrieved documents with metadata
        """
        # Use default from Config if not specified
        if k is None:
            k = Config.RAG_TOP_K_RESULTS

        # Check cache first
        cache_key = self._get_cache_key(query, k)

        with shelve.open(self._cache_file) as cache:
            if cache_key in cache:
                cached_data = cache[cache_key]
                timestamp = cached_data.get("timestamp", 0)
                current_time = time.time()

                # Check if cache entry is still valid (TTL)
                if current_time - timestamp < self.cache_ttl:
                    self._cache_hits += 1
                    logger.debug(
                        f"Cache HIT for query: {query[:50]}... "
                        f"(age: {int(current_time - timestamp)}s, "
                        f"hits: {self._cache_hits}, misses: {self._cache_misses})"
                    )
                    return cached_data["documents"]
                else:
                    # Expired - remove from cache
                    logger.debug(f"Cache entry expired for query: {query[:50]}...")
                    del cache[cache_key]

        # Cache miss - query vector store
        self._cache_misses += 1
        logger.debug(f"Cache MISS for query: {query[:50]}... " f"(hits: {self._cache_hits}, misses: {self._cache_misses})")

        results = self.vector_store.query(query, n_results=k)

        # Format results
        documents = []
        if results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                documents.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None,
                    }
                )

        # Store in persistent cache
        with shelve.open(self._cache_file) as cache:
            # Check cache size limit
            if len(cache) >= self.cache_max_size:
                # Remove oldest entries (simple LRU)
                self._evict_oldest(cache)

            cache[cache_key] = {"timestamp": time.time(), "documents": documents}

        return documents

    def _evict_oldest(self, cache: shelve.Shelf) -> None:
        """
        Evict oldest cache entries when cache is full.

        Args:
            cache: Shelve cache instance
        """
        # Get all entries with timestamps
        entries = [(key, data["timestamp"]) for key, data in cache.items()]

        # Sort by timestamp (oldest first)
        entries.sort(key=lambda x: x[1])

        # Remove oldest 10% of entries
        remove_count = max(1, len(entries) // 10)
        for key, _ in entries[:remove_count]:
            del cache[key]

        logger.debug(f"Evicted {remove_count} oldest cache entries")

    def clear_cache(self) -> None:
        """Clear the persistent query cache."""
        with shelve.open(self._cache_file) as cache:
            cache.clear()

        logger.info(f"Persistent cache cleared (had {self._cache_hits} hits, {self._cache_misses} misses)")
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache hits, misses, size, and hit rate
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0.0

        # Get cache size from disk
        try:
            with shelve.open(self._cache_file) as cache:
                cache_size = len(cache)
        except (OSError, IOError, KeyError) as e:
            # Cache file doesn't exist or can't be read - not a critical error for stats
            logger.debug(f"Could not read cache size: {e}")
            cache_size = 0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": cache_size,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_path": str(self.cache_path),
            "cache_ttl_seconds": self.cache_ttl,
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
