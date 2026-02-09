"""
Embedding generation and management.
"""

from typing import List

from langchain_openai import OpenAIEmbeddings

from lecture_forge.config import Config
from lecture_forge.utils import logger


class EmbeddingManager:
    """Manager for generating embeddings."""

    def __init__(self, model: str = None):
        """
        Initialize embedding manager.

        Args:
            model: Embedding model name (default: Config.EMBEDDING_MODEL)
        """
        self.model = model or Config.EMBEDDING_MODEL
        logger.info(f"Initializing embedding manager with model: {self.model}")

        self.embeddings = OpenAIEmbeddings(
            model=self.model,
            openai_api_key=Config.OPENAI_API_KEY,
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        logger.debug(f"Generating embeddings for {len(texts)} documents")
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query.

        Args:
            text: Query text

        Returns:
            Embedding vector
        """
        logger.debug(f"Generating embedding for query: {text[:50]}...")
        return self.embeddings.embed_query(text)
