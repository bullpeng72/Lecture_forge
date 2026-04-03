"""
Unit tests for slides/notes.py — SlideNotesGenerator and helpers.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_SLIDES_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Slides</title></head>
<body>
  <div class="slides">
    <section>
      <h2>Introduction</h2>
      <p>This is the intro slide content.</p>
    </section>
    <section>
      <h2>Main Topic</h2>
      <p>This is the main topic content.</p>
    </section>
  </div>
</body>
</html>"""

NO_SLIDES_DIV_HTML = """<!DOCTYPE html>
<html><body><p>No slides here.</p></body></html>"""

NO_SECTIONS_HTML = """<!DOCTYPE html>
<html><body><div class="slides"></div></body></html>"""

MERMAID_SLIDES_HTML = """<!DOCTYPE html>
<html><body>
  <div class="slides">
    <section>
      <h2>Diagram Slide</h2>
      <div class="mermaid">graph TD\nA --> B\nB --> C</div>
    </section>
  </div>
</body></html>"""

HEADING_SLIDES_HTML = """<!DOCTYPE html>
<html><body>
  <div class="slides">
    <section><h1>H1 Title</h1><p>content</p></section>
    <section><h2>H2 Title</h2><p>content</p></section>
    <section><h3>H3 Title</h3><p>content</p></section>
    <section><p>No heading</p></section>
  </div>
</body></html>"""


@pytest.fixture
def generator(test_env_vars):
    from lecture_forge.slides.notes import SlideNotesGenerator
    return SlideNotesGenerator()


def _make_mock_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# _parse_notes_response
# ---------------------------------------------------------------------------

class TestParseNotesResponse:
    def test_parses_single_note(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_0===\nThis is the first note."
        result = _parse_notes_response(response, 1)
        assert result == ["This is the first note."]

    def test_parses_multiple_notes(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_0===\nNote zero.\n===SLIDE_1===\nNote one."
        result = _parse_notes_response(response, 2)
        assert result[0] == "Note zero."
        assert result[1] == "Note one."

    def test_missing_slide_returns_empty_string(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_0===\nOnly first."
        result = _parse_notes_response(response, 3)
        assert result[1] == ""
        assert result[2] == ""

    def test_out_of_range_index_ignored(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_5===\nOut of range."
        result = _parse_notes_response(response, 2)
        assert result == ["", ""]

    def test_invalid_index_ignored(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_abc===\nBad index."
        result = _parse_notes_response(response, 1)
        assert result == [""]

    def test_empty_response_returns_empty_strings(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        result = _parse_notes_response("", 3)
        assert result == ["", "", ""]

    def test_content_stripped(self, test_env_vars):
        from lecture_forge.slides.notes import _parse_notes_response
        response = "===SLIDE_0===\n\n  Padded note.  \n"
        result = _parse_notes_response(response, 1)
        assert result[0] == "Padded note."


# ---------------------------------------------------------------------------
# _process_notes_batch
# ---------------------------------------------------------------------------

class TestProcessNotesBatch:
    def test_calls_llm_and_returns_notes(self, test_env_vars):
        from lecture_forge.slides.notes import _process_notes_batch
        slide_infos = [
            {"title": "Intro", "text": "Introduction to Python."},
            {"title": "Body", "text": "Main content about loops."},
        ]
        mock_resp = _make_mock_response(
            "===SLIDE_0===\nIntro note.\n===SLIDE_1===\nBody note."
        )
        with patch("lecture_forge.slides.notes._invoke_notes_llm", return_value=mock_resp):
            result = _process_notes_batch(slide_infos)
        assert len(result) == 2
        assert result[0] == "Intro note."
        assert result[1] == "Body note."

    def test_exception_returns_empty_strings(self, test_env_vars):
        from lecture_forge.slides.notes import _process_notes_batch
        slide_infos = [{"title": "X", "text": "Y"}]
        with patch("lecture_forge.slides.notes._invoke_notes_llm", side_effect=Exception("fail")):
            result = _process_notes_batch(slide_infos)
        assert result == [""]

    def test_text_truncated_to_max_chars(self, test_env_vars):
        from lecture_forge.slides.notes import _process_notes_batch, _MAX_CONTENT_CHARS
        long_text = "A" * 1000
        slide_infos = [{"title": "Long", "text": long_text}]
        captured = []

        def fake_invoke(messages):
            captured.append(messages[0].content)
            resp = MagicMock()
            resp.content = "===SLIDE_0===\nNote."
            return resp

        with patch("lecture_forge.slides.notes._invoke_notes_llm", side_effect=fake_invoke):
            _process_notes_batch(slide_infos)

        # The prompt should contain at most _MAX_CONTENT_CHARS of the long text
        assert long_text[:_MAX_CONTENT_CHARS] in captured[0]
        assert long_text[_MAX_CONTENT_CHARS + 1:] not in captured[0]


# ---------------------------------------------------------------------------
# SlideNotesGenerator.generate
# ---------------------------------------------------------------------------

class TestSlideNotesGeneratorGenerate:
    def test_no_slides_div_returns_original(self, generator):
        result = generator.generate(NO_SLIDES_DIV_HTML)
        assert result == NO_SLIDES_DIV_HTML

    def test_no_sections_returns_original(self, generator):
        result = generator.generate(NO_SECTIONS_HTML)
        assert result == NO_SECTIONS_HTML

    def test_notes_injected_into_sections(self, generator):
        mock_resp = _make_mock_response(
            "===SLIDE_0===\nNote for intro.\n===SLIDE_1===\nNote for main."
        )
        with patch("lecture_forge.slides.notes._invoke_notes_llm", return_value=mock_resp):
            result = generator.generate(SIMPLE_SLIDES_HTML)
        assert '<aside class="notes">' in result
        assert "Note for intro." in result
        assert "Note for main." in result

    def test_empty_notes_not_injected(self, generator):
        # Both notes empty → no aside injected
        mock_resp = _make_mock_response("")
        with patch("lecture_forge.slides.notes._invoke_notes_llm", return_value=mock_resp):
            result = generator.generate(SIMPLE_SLIDES_HTML)
        assert '<aside class="notes">' not in result

    def test_mermaid_syntax_preserved(self, generator):
        mock_resp = _make_mock_response("===SLIDE_0===\nDiagram note.")
        with patch("lecture_forge.slides.notes._invoke_notes_llm", return_value=mock_resp):
            result = generator.generate(MERMAID_SLIDES_HTML)
        # Mermaid arrow should NOT be HTML-escaped
        assert "A --> B" in result
        assert "&gt;" not in result

    def test_existing_aside_removed_before_text_extraction(self, generator):
        """Existing <aside> elements are stripped before slide text is extracted."""
        html = """<html><body><div class="slides">
        <section>
          <h2>Title</h2>
          <aside>Old note</aside>
          <p>Slide text.</p>
        </section></div></body></html>"""
        captured_infos = []

        def fake_batch(slide_infos):
            captured_infos.extend(slide_infos)
            return ["New note."]

        with patch("lecture_forge.slides.notes._process_notes_batch", side_effect=fake_batch):
            generator.generate(html)

        assert "Old note" not in captured_infos[0]["text"]

    def test_returns_string(self, generator):
        mock_resp = _make_mock_response("===SLIDE_0===\nA note.")
        with patch("lecture_forge.slides.notes._invoke_notes_llm", return_value=mock_resp):
            result = generator.generate(SIMPLE_SLIDES_HTML)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# SlideNotesGenerator._extract_title
# ---------------------------------------------------------------------------

class TestExtractTitle:
    def test_h2_preferred(self, generator):
        from bs4 import BeautifulSoup
        html = "<section><h2>H2</h2><h3>H3</h3></section>"
        sec = BeautifulSoup(html, "html.parser").find("section")
        assert generator._extract_title(sec) == "H2"

    def test_h3_fallback(self, generator):
        from bs4 import BeautifulSoup
        html = "<section><h3>Only H3</h3></section>"
        sec = BeautifulSoup(html, "html.parser").find("section")
        assert generator._extract_title(sec) == "Only H3"

    def test_h1_fallback(self, generator):
        from bs4 import BeautifulSoup
        html = "<section><h1>Title</h1></section>"
        sec = BeautifulSoup(html, "html.parser").find("section")
        assert generator._extract_title(sec) == "Title"

    def test_no_heading_returns_empty(self, generator):
        from bs4 import BeautifulSoup
        html = "<section><p>No heading.</p></section>"
        sec = BeautifulSoup(html, "html.parser").find("section")
        assert generator._extract_title(sec) == ""

    def test_heading_text_stripped(self, generator):
        from bs4 import BeautifulSoup
        html = "<section><h2>  Padded  </h2></section>"
        sec = BeautifulSoup(html, "html.parser").find("section")
        assert generator._extract_title(sec) == "Padded"
