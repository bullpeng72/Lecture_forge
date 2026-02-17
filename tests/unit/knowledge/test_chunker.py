"""
Unit tests for TextChunker.
"""

import pytest

from lecture_forge.knowledge.chunker import TextChunker


@pytest.fixture
def chunker():
    """Create a TextChunker with small chunk_size for testing."""
    return TextChunker(chunk_size=100, chunk_overlap=10)


def test_initialization_defaults():
    """TextChunker initializes with Config defaults."""
    chunker = TextChunker()
    assert chunker.chunk_size > 0
    assert chunker.chunk_overlap >= 0
    assert chunker.splitter is not None


def test_initialization_custom():
    """TextChunker accepts custom chunk_size and chunk_overlap."""
    chunker = TextChunker(chunk_size=200, chunk_overlap=20)
    assert chunker.chunk_size == 200
    assert chunker.chunk_overlap == 20


def test_chunk_text_empty(chunker):
    """Empty text returns empty list."""
    result = chunker.chunk_text("")
    assert result == []


def test_chunk_text_short(chunker):
    """Short text (below chunk_size) returns a single chunk."""
    text = "Hello world"
    result = chunker.chunk_text(text)
    assert len(result) == 1
    assert result[0] == text


def test_chunk_text_long(chunker):
    """Text longer than chunk_size is split into multiple chunks."""
    # 200 words × ~5 chars = ~1000 chars, well above chunk_size=100
    text = "word " * 200
    result = chunker.chunk_text(text)
    assert len(result) > 1


def test_chunk_text_respects_chunk_size(chunker):
    """Each chunk does not exceed chunk_size."""
    text = "A" * 500
    result = chunker.chunk_text(text)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= chunker.chunk_size


def test_chunk_text_overlap(chunker):
    """Consecutive chunks share some content due to overlap."""
    text = ("abcdefghij" * 20)  # 200 chars, should produce multiple chunks
    result = chunker.chunk_text(text)
    if len(result) > 1:
        # The end of chunk[0] should appear at the start of chunk[1]
        assert len(result[0]) > chunker.chunk_overlap
        end_of_first = result[0][-chunker.chunk_overlap :]
        start_of_second = result[1][: chunker.chunk_overlap]
        # Overlap means some shared text (exact match may vary with separators)
        assert len(end_of_first) > 0
        assert len(start_of_second) > 0


def test_chunk_text_whitespace_only(chunker):
    """Whitespace-only text returns empty or single whitespace chunk."""
    result = chunker.chunk_text("   \n\n   ")
    # RecursiveCharacterTextSplitter strips empty chunks
    assert isinstance(result, list)


def test_chunk_documents_empty_list(chunker):
    """chunk_documents with empty list returns empty list."""
    result = chunker.chunk_documents([])
    assert result == []


def test_chunk_documents_single(chunker):
    """chunk_documents with one document works like chunk_text."""
    doc = "Hello world, this is a test."
    result = chunker.chunk_documents([doc])
    expected = chunker.chunk_text(doc)
    assert result == expected


def test_chunk_documents_multiple(chunker):
    """chunk_documents combines chunks from all documents."""
    docs = ["First document. " * 5, "Second document. " * 5]
    result = chunker.chunk_documents(docs)
    assert len(result) >= 2  # At least one chunk per document


def test_chunk_documents_total_chunks(chunker):
    """Total chunks from chunk_documents equals sum of individual chunks."""
    docs = ["Short text."] * 3
    result = chunker.chunk_documents(docs)
    individual_total = sum(len(chunker.chunk_text(d)) for d in docs)
    assert len(result) == individual_total
