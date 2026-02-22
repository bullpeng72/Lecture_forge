"""
Vector store wrapper for ChromaDB.
"""

import os
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings

from lecture_forge.config import Config
from lecture_forge.utils import logger, timestamp

# Disable ChromaDB telemetry to avoid PostHog capture() errors
os.environ["ANONYMIZED_TELEMETRY"] = "False"


class VectorStore:
    """Wrapper for ChromaDB vector database."""

    def __init__(self, collection_name: str = None):
        """
        Initialize vector store.

        Args:
            collection_name: Name for the collection (auto-generated if None)
        """
        self.collection_name = collection_name or f"lecture_{timestamp()}"
        self.db_path = Config.VECTOR_DB_PATH / self.collection_name

        logger.info(f"Initializing vector store: {self.collection_name}")

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        # Create or get collection (with error recovery)
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "LectureForge knowledge base"},
            )
        except (KeyError, ValueError) as e:
            # Handle ChromaDB version compatibility issues
            logger.warning(f"Collection compatibility issue: {e}")
            logger.warning(f"Recreating collection: {self.collection_name}")

            try:
                # Try to delete the old collection
                self.client.delete_collection(name=self.collection_name)
                logger.info("Old collection deleted")
            except Exception as delete_error:
                logger.debug(f"Could not delete collection: {delete_error}")

            # Create fresh collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "LectureForge knowledge base"},
            )
            logger.info("New collection created")

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
    ) -> None:
        """
        Add documents to vector store.

        Args:
            documents: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
        """
        logger.info(f"Adding {len(documents)} documents to vector store")

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ) -> Dict:
        """
        Query the vector store.

        Args:
            query_text: Query text
            n_results: Number of results to return
            where: Filter conditions

        Returns:
            Query results
        """
        logger.debug(f"Querying vector store: {query_text[:50]}...")

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

        return results

    def get_stats(self) -> Dict:
        """Get statistics about the collection."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "document_count": count,
            "db_path": str(self.db_path),
        }

    def get_total_chunk_count(self) -> int:
        """Return total number of chunks stored in the collection."""
        return self.collection.count()

    def get_unused_chunks(self, used_ids: set, n: int = 50) -> tuple:
        """
        Return chunks that have not been used in content generation.

        Args:
            used_ids: Set of chunk IDs already referenced during writing
            n: Maximum number of unused chunks to return

        Returns:
            Tuple of (documents, metadatas) for unused chunks
        """
        try:
            all_items = self.collection.get(include=["documents", "metadatas"])
        except Exception as e:
            logger.warning(f"get_unused_chunks failed: {e}")
            return [], []

        all_docs = all_items.get("documents") or []
        all_metas = all_items.get("metadatas") or []
        all_ids = all_items.get("ids") or []

        unused_docs = []
        unused_metas = []
        for doc, meta, cid in zip(all_docs, all_metas, all_ids):
            if cid not in used_ids:
                unused_docs.append(doc)
                unused_metas.append(meta)
                if len(unused_docs) >= n:
                    break

        return unused_docs, unused_metas
