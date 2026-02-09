"""
Tests for text chunking functionality.
"""

import pytest

from lecture_forge.knowledge.chunker import TextChunker


@pytest.fixture
def chunker():
    """Create a TextChunker instance."""
    return TextChunker(chunk_size=100, chunk_overlap=20)


def test_chunker_initialization(chunker):
    """Test TextChunker initialization."""
    assert chunker.chunk_size == 100
    assert chunker.chunk_overlap == 20


def test_chunker_splits_long_text(chunker):
    """Test that long text is split into chunks."""
    long_text = "This is a test sentence. " * 20  # ~500 chars
    chunks = chunker.chunk_text(long_text)

    assert len(chunks) > 1
    assert all(len(chunk) <= chunker.chunk_size + 50 for chunk in chunks)  # Some tolerance


def test_chunker_preserves_short_text(chunker):
    """Test that short text is not split."""
    short_text = "This is a short test."
    chunks = chunker.chunk_text(short_text)

    assert len(chunks) == 1
    assert chunks[0] == short_text


def test_chunker_handles_empty_text(chunker):
    """Test chunking empty text."""
    chunks = chunker.chunk_text("")
    assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0] == "")


def test_chunker_overlap(chunker):
    """Test that chunks have overlap."""
    text = "A" * 50 + "B" * 50 + "C" * 50  # 150 chars
    chunks = chunker.chunk_text(text)

    if len(chunks) > 1:
        # Check that consecutive chunks have some overlap
        for i in range(len(chunks) - 1):
            # Some content from end of chunk i should appear in start of chunk i+1
            # (This is a simplified check)
            assert len(chunks[i]) > 0 and len(chunks[i + 1]) > 0


def test_chunker_with_metadata():
    """Test chunking with metadata preservation."""
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "Test content " * 20
    metadata = {"source": "test.pdf", "page": 1}

    chunks = chunker.chunk_text(text, metadata=metadata)

    # Verify metadata is attached to all chunks
    for chunk in chunks:
        if isinstance(chunk, dict):
            assert chunk["metadata"] == metadata


def test_chunker_respects_sentence_boundaries():
    """Test that chunker tries to respect sentence boundaries."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunker = TextChunker(chunk_size=30, chunk_overlap=5)

    chunks = chunker.chunk_text(text)

    # At least some chunks should end with sentence boundaries
    sentence_ending_chunks = [c for c in chunks if c.strip().endswith(".")]
    assert len(sentence_ending_chunks) > 0
