"""
Unit tests for ContentEnhancer and parse_html_to_lecture (utils/html_parser.py).
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup


# ===== Fixtures =====

MINIMAL_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
<!-- lf:topic: Python Basics -->
<!-- lf:duration: 60 -->
<!-- lf:audience_level: beginner -->
<!-- lf:vector_db_path: /tmp/test_kb -->
<h1>Python Basics</h1>
<div class="bg-blue-50">
  <ul>
    <li>Understand variables</li>
    <li>Write functions</li>
  </ul>
</div>
<section id="intro">
  <h2>1. Introduction</h2>
  <p>Python is a high-level language.</p>
  <p>It is easy to learn.</p>
</section>
<section id="advanced">
  <h2>2. Advanced Topics</h2>
  <p>Decorators and generators.</p>
  <pre><code>def hello(): pass</code></pre>
  <div class="mermaid">flowchart TD\n  A --> B</div>
</section>
<aside id="sidebar">
  <div class="space-y-1">
    <div>📝 500단어</div>
    <div>🖼 이미지 2개</div>
    <div>📊 다이어그램 1개</div>
    <div>🕐 2026-01-01 00:00</div>
  </div>
</aside>
<header>
  <span class="bg-green-100">📝 500단어</span>
  <span class="bg-yellow-100">🖼 이미지 2개</span>
  <span class="bg-red-100">📊 다이어그램 1개</span>
</header>
<footer>
  <p>LectureForge · 2026-01-01 00:00</p>
</footer>
</body>
</html>
"""

MINIMAL_HTML_NO_META = """\
<html>
<body>
<h1>No Meta Lecture</h1>
<section id="s1"><h2>Section One</h2><p>Content here.</p></section>
</body>
</html>
"""


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    f = tmp_path / "lecture.html"
    f.write_text(MINIMAL_HTML, encoding="utf-8")
    return f


@pytest.fixture
def html_file_no_meta(tmp_path: Path) -> Path:
    f = tmp_path / "no_meta.html"
    f.write_text(MINIMAL_HTML_NO_META, encoding="utf-8")
    return f


@pytest.fixture
def enhancer():
    from lecture_forge.agents.content_enhancer import ContentEnhancer
    return ContentEnhancer()


# ===== _extract_html_metadata =====

class TestExtractHtmlMetadata:
    def test_parses_all_meta_fields(self, enhancer, html_file):
        meta = enhancer._extract_html_metadata(html_file)
        assert meta["topic"] == "Python Basics"
        assert meta["duration"] == "60"
        assert meta["audience_level"] == "beginner"
        assert meta["vector_db_path"] == "/tmp/test_kb"

    def test_missing_meta_returns_empty_strings(self, enhancer, html_file_no_meta):
        meta = enhancer._extract_html_metadata(html_file_no_meta)
        assert meta["topic"] == ""
        assert meta["duration"] == ""
        assert meta["audience_level"] == ""
        assert meta["vector_db_path"] == ""

    def test_nonexistent_file_returns_defaults(self, enhancer, tmp_path):
        meta = enhancer._extract_html_metadata(tmp_path / "missing.html")
        assert meta == {
            "vector_db_path": "",
            "topic": "",
            "duration": "",
            "audience_level": "",
        }

    def test_returns_dict(self, enhancer, html_file):
        meta = enhancer._extract_html_metadata(html_file)
        assert isinstance(meta, dict)


# ===== _compute_updated_stats =====

class TestComputeUpdatedStats:
    def test_counts_words_in_sections(self, enhancer):
        html = '<section id="s1"><p>Hello world</p></section>'
        soup = BeautifulSoup(html, "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert stats["total_words"] == 2

    def test_counts_images(self, enhancer):
        html = '<section id="s1"><img src="a.png"/><img src="b.png"/></section>'
        soup = BeautifulSoup(html, "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert stats["total_images"] == 2

    def test_counts_mermaid_diagrams(self, enhancer):
        html = (
            '<section id="s1">'
            '<div class="mermaid">graph TD; A-->B</div>'
            '<div class="mermaid">graph LR; C-->D</div>'
            '</section>'
        )
        soup = BeautifulSoup(html, "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert stats["total_diagrams"] == 2

    def test_stats_has_required_keys(self, enhancer):
        soup = BeautifulSoup('<section id="s1"><p>x</p></section>', "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert "total_words" in stats
        assert "total_images" in stats
        assert "total_diagrams" in stats
        assert "updated_at" in stats

    def test_empty_html_returns_zeros(self, enhancer):
        soup = BeautifulSoup("<html></html>", "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert stats["total_words"] == 0
        assert stats["total_images"] == 0
        assert stats["total_diagrams"] == 0


# ===== _update_stats_in_html =====

class TestUpdateStatsInHtml:
    def _make_soup(self):
        return BeautifulSoup(MINIMAL_HTML, "html.parser")

    def test_updates_sidebar_word_count(self, enhancer):
        soup = self._make_soup()
        enhancer._update_stats_in_html(soup, {"total_words": 1234, "total_images": 0, "total_diagrams": 0, "updated_at": "2026-01-01 12:00"})
        sidebar = soup.find("aside", id="sidebar")
        text = sidebar.get_text()
        assert "1,234단어" in text

    def test_updates_sidebar_images(self, enhancer):
        soup = self._make_soup()
        enhancer._update_stats_in_html(soup, {"total_words": 0, "total_images": 5, "total_diagrams": 0, "updated_at": "2026-01-01 12:00"})
        sidebar = soup.find("aside", id="sidebar")
        assert "이미지 5개" in sidebar.get_text()

    def test_updates_sidebar_diagrams(self, enhancer):
        soup = self._make_soup()
        enhancer._update_stats_in_html(soup, {"total_words": 0, "total_images": 0, "total_diagrams": 3, "updated_at": "2026-01-01 12:00"})
        sidebar = soup.find("aside", id="sidebar")
        assert "다이어그램 3개" in sidebar.get_text()

    def test_updates_header_badges(self, enhancer):
        soup = self._make_soup()
        enhancer._update_stats_in_html(soup, {"total_words": 999, "total_images": 4, "total_diagrams": 2, "updated_at": "2026-02-01 09:00"})
        header = soup.find("header")
        header_text = header.get_text()
        assert "999단어" in header_text
        assert "이미지 4개" in header_text
        assert "다이어그램 2개" in header_text


# ===== parse_html_to_lecture (utils/html_parser.py) =====

class TestParseHtmlToLecture:
    def test_returns_lecture_object(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        assert lecture is not None

    def test_extracts_title(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        assert lecture.title == "Python Basics"

    def test_extracts_learning_objectives(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        assert len(lecture.learning_objectives) == 2
        assert "Understand variables" in lecture.learning_objectives

    def test_extracts_sections(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        assert len(lecture.sections) == 2

    def test_section_title_strips_number_prefix(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        titles = [s.title for s in lecture.sections]
        assert "Introduction" in titles
        assert "Advanced Topics" in titles

    def test_extracts_code_blocks(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        advanced = next(s for s in lecture.sections if s.section_id == "advanced")
        assert len(advanced.code_blocks) == 1

    def test_extracts_mermaid_diagrams(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        advanced = next(s for s in lecture.sections if s.section_id == "advanced")
        assert len(advanced.diagrams) == 1
        assert "flowchart" in advanced.diagrams[0].mermaid_code

    def test_missing_file_returns_none(self, tmp_path):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        result = parse_html_to_lecture(str(tmp_path / "missing.html"))
        assert result is None

    def test_section_word_count_positive(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        for section in lecture.sections:
            assert section.word_count >= 0

    def test_default_duration_and_level(self, html_file):
        from lecture_forge.utils.html_parser import parse_html_to_lecture
        lecture = parse_html_to_lecture(str(html_file))
        assert lecture.duration == 180
        assert lecture.audience_level == "intermediate"
