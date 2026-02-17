"""
Unit tests for HTMLLectureParser.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from lecture_forge.slides.parser import HTMLLectureParser


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
  <h1 class="lecture-title">Introduction to Python</h1>
  <p class="lecture-subtitle">Beginner Level</p>

  <section id="sec_1">
    <h2>1. Python Basics</h2>
    <h3>Variables and Types</h3>
    <p>Python is a dynamically typed language with clean syntax and readability.</p>
    <ul>
      <li>Integers and floats</li>
      <li>Strings</li>
      <li>Booleans</li>
    </ul>
    <pre><code class="language-python">x = 42
print(x)</code></pre>
  </section>

  <section id="sec_2">
    <h2>2. Control Flow</h2>
    <p>Control flow determines the order of execution in a program flow.</p>
  </section>
</body>
</html>"""


@pytest.fixture
def parser():
    """Create an HTMLLectureParser instance."""
    return HTMLLectureParser()


@pytest.fixture
def sample_html_file(tmp_path):
    """Write sample HTML to a temp file."""
    html_file = tmp_path / "lecture.html"
    html_file.write_text(SAMPLE_HTML, encoding="utf-8")
    return html_file


def test_parser_initialization(parser):
    """Parser initializes with converted_paragraphs=0."""
    assert parser.converted_paragraphs == 0


def test_parse_returns_dict(parser, sample_html_file):
    """parse() returns a dict with expected keys."""
    result = parser.parse(sample_html_file)

    assert isinstance(result, dict)
    assert "title" in result
    assert "subtitle" in result
    assert "sections" in result
    assert "converted_paragraphs" in result


def test_parse_extracts_title(parser, sample_html_file):
    """parse() extracts the lecture title."""
    result = parser.parse(sample_html_file)
    assert result["title"] == "Introduction to Python"


def test_parse_extracts_subtitle(parser, sample_html_file):
    """parse() extracts the lecture subtitle."""
    result = parser.parse(sample_html_file)
    assert result["subtitle"] == "Beginner Level"


def test_parse_extracts_sections(parser, sample_html_file):
    """parse() extracts correct number of sections."""
    result = parser.parse(sample_html_file)
    assert len(result["sections"]) == 2


def test_parse_section_title_numbering_stripped(parser, sample_html_file):
    """parse() strips leading numbering from section titles."""
    result = parser.parse(sample_html_file)
    assert result["sections"][0]["title"] == "Python Basics"
    assert result["sections"][1]["title"] == "Control Flow"


def test_parse_section_has_blocks(parser, sample_html_file):
    """parse() populates content blocks for each section."""
    result = parser.parse(sample_html_file)
    first_section = result["sections"][0]
    assert len(first_section["blocks"]) > 0


def test_extract_title_missing(parser):
    """_extract_title returns default when no h1.lecture-title found."""
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    title = parser._extract_title(soup)
    assert title == "Lecture Slides"


def test_extract_subtitle_missing(parser):
    """_extract_subtitle returns empty string when no subtitle element found."""
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    subtitle = parser._extract_subtitle(soup)
    assert subtitle == ""


def test_process_list_unordered(parser):
    """_process_list returns unordered list block."""
    html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.find("ul")
    block = parser._process_list(ul)

    assert block is not None
    assert block["type"] == "list"
    assert block["ordered"] is False
    assert "Item 1" in block["items"]
    assert "Item 2" in block["items"]


def test_process_list_ordered(parser):
    """_process_list returns ordered list block."""
    html = "<ol><li>Step 1</li><li>Step 2</li></ol>"
    soup = BeautifulSoup(html, "html.parser")
    ol = soup.find("ol")
    block = parser._process_list(ol)

    assert block is not None
    assert block["ordered"] is True


def test_process_list_empty(parser):
    """_process_list returns None for empty list."""
    html = "<ul></ul>"
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.find("ul")
    block = parser._process_list(ul)
    assert block is None


def test_process_code_block(parser):
    """_process_code_block extracts code and language."""
    html = '<pre><code class="language-python">print("hello")</code></pre>'
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    block = parser._process_code_block(pre)

    assert block is not None
    assert block["type"] == "code"
    assert block["language"] == "python"
    assert 'print("hello")' in block["content"]


def test_process_code_block_no_code_elem(parser):
    """_process_code_block returns None when no <code> inside <pre>."""
    html = "<pre>bare text</pre>"
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    block = parser._process_code_block(pre)
    assert block is None


def test_process_image(parser):
    """_process_image extracts src, alt, and caption."""
    html = """<figure>
        <img src="/images/test.png" alt="Test image">
        <figcaption>Figure 1</figcaption>
    </figure>"""
    soup = BeautifulSoup(html, "html.parser")
    figure = soup.find("figure")
    block = parser._process_image(figure)

    assert block is not None
    assert block["type"] == "image"
    assert block["src"] == "/images/test.png"
    assert block["alt"] == "Test image"
    assert block["caption"] == "Figure 1"


def test_process_diagram(parser):
    """_process_diagram extracts Mermaid code."""
    html = '<div class="mermaid">flowchart TD\n  A --> B</div>'
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div")
    block = parser._process_diagram(div)

    assert block is not None
    assert block["type"] == "diagram"
    assert "flowchart" in block["content"]


def test_parse_no_subtitle(parser, tmp_path):
    """parse() returns empty string for missing subtitle."""
    html = '<html><body><h1 class="lecture-title">Title</h1></body></html>'
    html_file = tmp_path / "no_subtitle.html"
    html_file.write_text(html, encoding="utf-8")

    result = parser.parse(html_file)
    assert result["subtitle"] == ""


def test_section_without_h2_skipped(parser, tmp_path):
    """Section without h2 is skipped during parsing."""
    html = """<html><body>
        <h1 class="lecture-title">T</h1>
        <section id="sec_1"><!-- no h2 --><p>Content</p></section>
        <section id="sec_2"><h2>Valid Section</h2></section>
    </body></html>"""
    f = tmp_path / "test.html"
    f.write_text(html, encoding="utf-8")
    result = parser.parse(f)
    # Only sec_2 should be extracted (sec_1 has no h2)
    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "Valid Section"


def test_extract_content_blocks_h3_h4(parser):
    """_extract_content_blocks handles h3 and h4 elements."""
    html = """<section id="s1">
        <h2>Title</h2>
        <h3>Subsection</h3>
        <h4>Sub-sub</h4>
        <h4></h4>
    </section>"""
    soup = BeautifulSoup(html, "html.parser")
    section_elem = soup.find("section")
    blocks = parser._extract_content_blocks(section_elem)
    types = [b["type"] for b in blocks]
    assert "subsection" in types
    assert "subsubsection" in types


def test_extract_content_blocks_with_figure_and_diagram(parser):
    """_extract_content_blocks includes image and diagram blocks."""
    html = """<section id="s1">
        <h2>Title</h2>
        <figure><img src="/img.png" alt="alt"><figcaption>Cap</figcaption></figure>
        <div class="mermaid">flowchart TD\n    A-->B</div>
    </section>"""
    soup = BeautifulSoup(html, "html.parser")
    section_elem = soup.find("section")
    blocks = parser._extract_content_blocks(section_elem)
    types = [b["type"] for b in blocks]
    assert "image" in types
    assert "diagram" in types


def test_process_paragraph_short_returns_none(parser):
    """_process_paragraph returns None for very short text."""
    html = "<p>Short</p>"
    soup = BeautifulSoup(html, "html.parser")
    p = soup.find("p")
    block = parser._process_paragraph(p)
    assert block is None


def test_process_paragraph_single_bullet(parser):
    """_process_paragraph returns paragraph block for single bullet point.
    Text < 100 chars returns [text] from convert_to_bullet_points → single item → type=paragraph."""
    html = "<p>This is exactly one bullet point text that is short enough.</p>"
    soup = BeautifulSoup(html, "html.parser")
    p = soup.find("p")
    block = parser._process_paragraph(p)
    assert block is not None
    # Short text (< 100 chars) returns [text] → single bullet → paragraph
    assert block["type"] == "paragraph"


def test_process_paragraph_multiple_bullets_returns_list(parser):
    """Line 157: _process_paragraph returns list when convert_to_bullet_points yields >1 item."""
    from unittest.mock import patch
    long_text = "A" * 150  # > 100 chars so convert_to_bullet_points is called
    html = f"<p>{long_text}</p>"
    soup = BeautifulSoup(html, "html.parser")
    p = soup.find("p")
    with patch("lecture_forge.slides.parser.convert_to_bullet_points", return_value=["Bullet 1", "Bullet 2", "Bullet 3"]):
        block = parser._process_paragraph(p)
    assert block is not None
    assert block["type"] == "list"
    assert len(block["items"]) == 3


def test_process_image_no_img(parser):
    """_process_image returns None when no img tag in figure."""
    html = "<figure><figcaption>Only caption</figcaption></figure>"
    soup = BeautifulSoup(html, "html.parser")
    figure = soup.find("figure")
    block = parser._process_image(figure)
    assert block is None


def test_process_image_no_src(parser):
    """_process_image returns None when img has no src."""
    html = "<figure><img alt='alt'></figure>"
    soup = BeautifulSoup(html, "html.parser")
    figure = soup.find("figure")
    block = parser._process_image(figure)
    assert block is None


def test_process_image_no_figcaption(parser):
    """_process_image returns empty string caption when no figcaption."""
    html = "<figure><img src='/img.png' alt='alt'></figure>"
    soup = BeautifulSoup(html, "html.parser")
    figure = soup.find("figure")
    block = parser._process_image(figure)
    assert block is not None
    assert block["caption"] == ""


def test_process_code_block_empty_code(parser):
    """_process_code_block returns None when code element is empty."""
    html = "<pre><code></code></pre>"
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    block = parser._process_code_block(pre)
    assert block is None


def test_process_code_block_no_language_class(parser):
    """_process_code_block defaults language to python when no class."""
    html = "<pre><code>x = 1</code></pre>"
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    block = parser._process_code_block(pre)
    assert block is not None
    assert block["language"] == "python"


def test_process_diagram_empty_returns_none(parser):
    """_process_diagram returns None when mermaid div is empty."""
    html = '<div class="mermaid"></div>'
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div")
    block = parser._process_diagram(div)
    assert block is None
