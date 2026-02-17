"""
Unit tests for PDFParserTool.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.tools.pdf_parser import PDFParserTool


@pytest.fixture
def parser():
    return PDFParserTool()


def test_initialization(parser):
    assert parser.name == "PDF Parser"
    assert "PDF" in parser.description


def test_run_file_not_found(tmp_path, parser):
    """Returns error dict when file doesn't exist."""
    result = parser.run(str(tmp_path / "nonexistent.pdf"))
    assert result["success"] is False
    assert "not found" in result["error"].lower() or "File not found" in result["error"]
    assert result["text"] == ""


def test_run_success(tmp_path, parser):
    """Returns parsed content when PDF is valid."""
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Hello world from page 1."

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=2)
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page, mock_page]))
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)
    mock_doc.metadata = {"title": "Test PDF", "author": "Test"}

    # Create a real file for path.exists() check
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with patch("lecture_forge.tools.pdf_parser.fitz.open", return_value=mock_doc):
        result = parser.run(str(pdf_path))

    assert result["success"] is True
    assert result["text"] != ""
    assert "metadata" in result
    assert result["metadata"]["title"] == "Test PDF"
    assert len(result["pages"]) == 2


def test_run_returns_page_info(tmp_path, parser):
    """Each page in result includes page_number, text, word_count."""
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Python is a great language."

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)
    mock_doc.metadata = {}

    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    with patch("lecture_forge.tools.pdf_parser.fitz.open", return_value=mock_doc):
        result = parser.run(str(pdf_path))

    page = result["pages"][0]
    assert page["page_number"] == 1
    assert "Python" in page["text"]
    assert page["word_count"] == len("Python is a great language.".split())


def test_run_exception_returns_error(tmp_path, parser):
    """Returns error dict when fitz raises an exception."""
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"not a real pdf")

    with patch("lecture_forge.tools.pdf_parser.fitz.open", side_effect=Exception("Invalid PDF")):
        result = parser.run(str(pdf_path))

    assert result["success"] is False
    assert "error" in result
    assert result["text"] == ""
