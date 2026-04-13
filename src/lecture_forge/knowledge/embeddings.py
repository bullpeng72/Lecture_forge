"""
Embedding generation and management.
"""

from typing import List

from lecture_forge.config import Config
from lecture_forge.utils import logger


class EmbeddingManager:
    """Manager for generating embeddings."""

    def __init__(self, model: str = None):
        """
        Initialize embedding manager.

        Automatically selects the embedding backend based on LLM_PROVIDER:
          - openai  → OpenAIEmbeddings (text-embedding-3-small by default)
          - ollama  → OllamaEmbeddings (nomic-embed-text by default)

        Args:
            model: Embedding model name (default: provider-specific default)
        """
        if Config.LLM_PROVIDER == "ollama":
            self.model = model or Config.OLLAMA_EMBEDDING_MODEL
            logger.info(f"Initializing Ollama embedding manager with model: {self.model}")
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError as exc:
                raise ImportError(
                    "langchain-ollama is required for Ollama support.\n"
                    "Install with: pip install langchain-ollama"
                ) from exc
            self.embeddings = OllamaEmbeddings(
                model=self.model,
                base_url=Config.OLLAMA_BASE_URL,
            )
        else:
            from langchain_openai import OpenAIEmbeddings
            self.model = model or Config.EMBEDDING_MODEL
            logger.info(f"Initializing OpenAI embedding manager with model: {self.model}")
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
