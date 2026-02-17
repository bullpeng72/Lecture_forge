"""
Unit tests for SlideConverter.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.slides.converter import SlideConverter


@pytest.fixture
def converter():
    return SlideConverter()


@pytest.fixture
def sample_html_file(tmp_path):
    """Create a minimal HTML file for testing."""
    html = """<!DOCTYPE html>
<html><head><title>Test Lecture</title></head>
<body>
<h1>Python Basics</h1>
<section><h2>Introduction</h2><p>Welcome to Python.</p></section>
</body></html>"""
    path = tmp_path / "lecture.html"
    path.write_text(html, encoding="utf-8")
    return path


def test_converter_initialization(converter):
    """SlideConverter initializes parser, template, and console."""
    from lecture_forge.slides.parser import HTMLLectureParser
    from lecture_forge.slides.templates import RevealJsTemplate
    assert isinstance(converter.parser, HTMLLectureParser)
    assert isinstance(converter.template, RevealJsTemplate)
    assert converter.console is not None


def test_converter_with_custom_console():
    """SlideConverter accepts a custom console."""
    from rich.console import Console
    console = Console()
    converter = SlideConverter(console=console)
    assert converter.console is console


def test_convert_success(tmp_path, sample_html_file):
    """convert() returns True and writes output file on success."""
    output_path = tmp_path / "slides.html"
    converter = SlideConverter()

    result = converter.convert(sample_html_file, output_path)

    assert result is True
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert len(content) > 100  # Should produce real HTML


def test_convert_output_contains_revealjs(tmp_path, sample_html_file):
    """Output file contains Reveal.js structure."""
    output_path = tmp_path / "slides.html"
    converter = SlideConverter()
    converter.convert(sample_html_file, output_path)

    content = output_path.read_text(encoding="utf-8")
    # RevealJS template should be present
    assert "reveal" in content.lower() or "slides" in content.lower() or "section" in content.lower()


def test_convert_failure_returns_false(tmp_path):
    """convert() returns False when source file doesn't exist."""
    converter = SlideConverter()
    missing_path = tmp_path / "nonexistent.html"
    output_path = tmp_path / "slides.html"

    result = converter.convert(missing_path, output_path)

    assert result is False


def test_convert_uses_parser_and_template(tmp_path, sample_html_file):
    """convert() calls parser.parse() and template.generate()."""
    output_path = tmp_path / "slides.html"
    converter = SlideConverter()

    mock_parser = MagicMock()
    mock_parser.parse.return_value = {
        "title": "Test",
        "subtitle": "Sub",
        "sections": [],
        "converted_paragraphs": 0,
    }
    mock_template = MagicMock()
    mock_template.generate.return_value = "<html>slides</html>"
    converter.parser = mock_parser
    converter.template = mock_template

    result = converter.convert(sample_html_file, output_path)

    assert result is True
    mock_parser.parse.assert_called_once_with(sample_html_file)
    mock_template.generate.assert_called_once()
    assert output_path.read_text() == "<html>slides</html>"
