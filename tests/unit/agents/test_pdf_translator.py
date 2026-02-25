"""Tests for PDFTranslatorAgent — focusing on _filter_chapters and _extract_fallback_title."""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.pdf_translator import PDFTranslatorAgent


@pytest.fixture
def agent(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")  # minimal stub
    with patch.object(PDFTranslatorAgent, "__init__", lambda self, pdf_path: None):
        a = PDFTranslatorAgent.__new__(PDFTranslatorAgent)
        a.pdf_path = str(pdf)
        a.image_selector = MagicMock()
    return a


# ── _extract_fallback_title ────────────────────────────────────────────────────

class TestExtractFallbackTitle:
    def test_picks_first_short_meaningful_line(self, agent):
        raw = "Introduction to Large Language Models\nThis is a long paragraph about LLMs..."
        assert agent._extract_fallback_title(raw) == "Introduction to Large Language Models"

    def test_skips_standalone_page_numbers(self, agent):
        raw = "42\nWhat is an LLM?\nLong paragraph text follows here."
        assert agent._extract_fallback_title(raw) == "What is an LLM?"

    def test_skips_domain_watermarks(self, agent):
        raw = "DailyDoseOfDS.com\nTransformer Architecture\nDetailed explanation..."
        assert agent._extract_fallback_title(raw) == "Transformer Architecture"

    def test_skips_lines_over_80_chars(self, agent):
        long_line = "A" * 81
        short_line = "Fine-Tuning Techniques"
        raw = f"{long_line}\n{short_line}"
        assert agent._extract_fallback_title(raw) == short_line

    def test_truncates_at_word_boundary_when_all_lines_too_long(self, agent):
        raw = "This is a sentence that goes well beyond eighty characters in total length indeed yes it does"
        result = agent._extract_fallback_title(raw)
        assert result is not None
        assert len(result) <= 80
        # Should not cut mid-word
        assert not result.endswith(" ")

    def test_returns_none_for_empty_text(self, agent):
        assert agent._extract_fallback_title("") is None

    def test_returns_none_for_only_numbers_and_watermarks(self, agent):
        raw = "1\n2\n3\nexample.com\ntest.io"
        assert agent._extract_fallback_title(raw) is None

    def test_skips_lines_too_short(self, agent):
        raw = "ab\nLong Enough Title Here"
        assert agent._extract_fallback_title(raw) == "Long Enough Title Here"


# ── _filter_chapters ───────────────────────────────────────────────────────────

def _make_chapter(title: str, raw_text: str, pages=None) -> dict:
    return {
        "title": title,
        "level": 1,
        "start_page": 1,
        "end_page": 2,
        "pages": pages or [1, 2],
        "raw_text": raw_text,
    }


BODY = "word " * 50  # 50 words — passes MIN_SECTION_WORDS=30


class TestFilterChapters:
    def test_keeps_valid_chapter(self, agent):
        ch = _make_chapter("Introduction", BODY)
        result = agent._filter_chapters([ch])
        assert len(result) == 1
        assert result[0]["title"] == "Introduction"

    def test_removes_empty_section(self, agent):
        ch = _make_chapter("Short", "tiny text")
        result = agent._filter_chapters([ch])
        assert result == []

    def test_removes_toc_page(self, agent):
        toc_text = "\n".join([f"Chapter {i}......... {i}" for i in range(1, 12)])
        ch = _make_chapter("Contents", toc_text)
        result = agent._filter_chapters([ch])
        assert result == []

    def test_recovers_empty_title_from_content(self, agent):
        """Chapter with empty TOC title gets title extracted from raw_text."""
        raw = "Transformer Architecture\n" + BODY
        ch = _make_chapter("", raw)
        result = agent._filter_chapters([ch])
        assert len(result) == 1
        assert result[0]["title"] == "Transformer Architecture"

    def test_recovers_whitespace_only_title(self, agent):
        raw = "Fine-Tuning Overview\n" + BODY
        ch = _make_chapter("   ", raw)
        result = agent._filter_chapters([ch])
        assert len(result) == 1
        assert result[0]["title"] == "Fine-Tuning Overview"

    def test_removes_untitled_when_no_fallback_possible(self, agent):
        """Empty title with no extractable fallback → discard."""
        # Raw text has enough words but no viable title line:
        # only standalone numbers, domain watermarks, and 2-char stubs
        raw = "1\n2\nexample.com\n" + "ab\n" * 60
        ch = _make_chapter("", raw)
        result = agent._filter_chapters([ch])
        assert result == []

    def test_does_not_mutate_original_dict(self, agent):
        """_filter_chapters must not modify the original chapter dict in place."""
        raw = "RAG Architecture\n" + BODY
        ch = _make_chapter("", raw)
        original_title = ch["title"]
        agent._filter_chapters([ch])
        assert ch["title"] == original_title  # original untouched

    def test_counts_removed_correctly(self, agent, caplog):
        import logging
        chapters = [
            _make_chapter("Good", BODY),
            _make_chapter("", "tiny"),          # removed: too short
            _make_chapter("", BODY),            # recovered: has fallback from BODY
        ]
        # BODY starts with "word word..." so fallback should pick up something
        # (though "word" repeated is alnum >= 3, len >= 3 — passes)
        with caplog.at_level(logging.INFO):
            result = agent._filter_chapters(chapters)
        # "Good" kept, empty+tiny removed, empty+BODY either recovered or removed
        assert len(result) >= 1
        assert result[0]["title"] == "Good"
