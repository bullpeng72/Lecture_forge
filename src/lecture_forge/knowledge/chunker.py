"""
Text chunking utilities.
"""

from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter

from lecture_forge.config import Config
from lecture_forge.utils import logger


class TextChunker:
    """Text chunker for splitting documents."""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize text chunker.

        Args:
            chunk_size: Size of each chunk (default: Config.CHUNK_SIZE)
            chunk_overlap: Overlap between chunks (default: Config.CHUNK_OVERLAP)
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

        logger.info(
            f"Initializing text chunker (size: {self.chunk_size}, overlap: {self.chunk_overlap})"
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        logger.debug(f"Chunking text of length {len(text)}")
        chunks = self.splitter.split_text(text)
        logger.debug(f"Created {len(chunks)} chunks")
        return chunks

    def chunk_documents(self, documents: List[str]) -> List[str]:
        """
        Split multiple documents into chunks.

        Args:
            documents: List of documents

        Returns:
            List of all chunks
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_text(doc)
            all_chunks.extend(chunks)

        logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} chunks")
        return all_chunks
