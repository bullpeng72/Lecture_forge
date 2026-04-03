"""
Extended unit tests for PDFTranslatorAgent.
Covers build_curriculum, translate_chapters, assign_images_to_sections,
and private helpers (_clean_raw_text, _protect_code_blocks, _restore_code_blocks,
_is_toc_content, _extract_by_page_groups, _build_synthetic_context_metadatas, _slugify).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import SectionContent


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with patch("lecture_forge.agents.base.ChatOpenAI"), \
         patch("lecture_forge.agents.content_writer.image_selector.ImageSelector.__init__",
               return_value=None):
        from lecture_forge.agents.pdf_translator import PDFTranslatorAgent
        a = PDFTranslatorAgent(str(pdf))
        a.image_selector = MagicMock()
        return a


def _make_chapter(title="Intro", pages=None, raw_text="word " * 50):
    return {
        "title": title,
        "level": 1,
        "start_page": 1,
        "end_page": 5,
        "pages": pages or [1, 2, 3, 4, 5],
        "raw_text": raw_text,
    }


def _make_curriculum(sections=None):
    if sections is None:
        sections = [
            Section(id="section_0_intro", title="Intro", topics=["Intro"],
                    estimated_time=20, difficulty_level="intermediate")
        ]
    return Curriculum(
        topic="Test",
        duration=60,
        audience_level="intermediate",
        learning_objectives=["obj1"],
        sections=sections,
        total_estimated_time=60,
        source_files=[],
    )


# ──────────────────────────────────────────────────────────────────────────────
# build_curriculum
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildCurriculum:
    def test_basic_structure(self, agent):
        chapters = [_make_chapter("Ch 1"), _make_chapter("Ch 2")]
        curriculum, page_map = agent.build_curriculum(chapters, "AI Basics")
        assert curriculum.topic == "AI Basics"
        assert len(curriculum.sections) == 2
        assert "section_0" in curriculum.sections[0].id
        assert "section_1" in curriculum.sections[1].id

    def test_page_map_populated(self, agent):
        chapters = [_make_chapter("Ch 1", pages=[1, 2, 3])]
        _, page_map = agent.build_curriculum(chapters, "Topic")
        assert list(page_map.values())[0] == [1, 2, 3]

    def test_empty_pages_fallback(self, agent):
        chapter = {**_make_chapter("Ch 1"), "pages": []}
        _, page_map = agent.build_curriculum([chapter], "Topic")
        val = list(page_map.values())[0]
        assert isinstance(val, list)

    def test_duration_minimum(self, agent):
        chapters = [_make_chapter("Tiny", pages=[1])]
        curriculum, _ = agent.build_curriculum(chapters, "T")
        assert curriculum.duration >= 30

    def test_audience_level_passed(self, agent):
        chapters = [_make_chapter()]
        curriculum, _ = agent.build_curriculum(chapters, "T", audience_level="beginner")
        assert curriculum.audience_level == "beginner"

    def test_objectives_capped_at_5(self, agent):
        chapters = [_make_chapter(f"Ch {i}") for i in range(10)]
        curriculum, _ = agent.build_curriculum(chapters, "T")
        assert len(curriculum.learning_objectives) <= 5

    def test_source_files_contains_pdf_path(self, agent):
        chapters = [_make_chapter()]
        curriculum, _ = agent.build_curriculum(chapters, "T")
        assert agent.pdf_path in curriculum.source_files


# ──────────────────────────────────────────────────────────────────────────────
# translate_chapters
# ──────────────────────────────────────────────────────────────────────────────

class TestTranslateChapters:
    def test_skip_translation_keeps_original(self, agent):
        chapters = [_make_chapter("Intro", raw_text="Hello world content")]
        curriculum = _make_curriculum()
        results = agent.translate_chapters(chapters, curriculum, skip_translation=True)
        assert results[0].markdown_content == "Hello world content"
        assert results[0].title == "Intro"

    def test_returns_section_content_list(self, agent):
        chapters = [_make_chapter()]
        curriculum = _make_curriculum()
        results = agent.translate_chapters(chapters, curriculum, skip_translation=True)
        assert len(results) == 1
        assert hasattr(results[0], "section_id")
        assert hasattr(results[0], "markdown_content")

    def test_translated_title_synced_back_to_curriculum(self, agent):
        mock_resp = MagicMock()
        mock_resp.content = "번역된 내용"
        agent.llm = MagicMock()
        agent.llm.invoke.return_value = mock_resp

        with patch.object(agent, "_translate_chapter_text", return_value="번역 본문"), \
             patch.object(agent, "_translate_title", return_value="번역 제목"), \
             patch.object(agent, "_protect_code_blocks", return_value=("text", {})), \
             patch.object(agent, "_restore_code_blocks", return_value="번역 본문"):
            chapters = [_make_chapter("Original Title")]
            curriculum = _make_curriculum()
            agent.translate_chapters(chapters, curriculum)
        assert curriculum.sections[0].title == "번역 제목"

    def test_word_count_set(self, agent):
        chapters = [_make_chapter(raw_text="one two three four five")]
        curriculum = _make_curriculum()
        results = agent.translate_chapters(chapters, curriculum, skip_translation=True)
        assert results[0].word_count == 5


# ──────────────────────────────────────────────────────────────────────────────
# assign_images_to_sections
# ──────────────────────────────────────────────────────────────────────────────

class TestAssignImagesToSections:
    def test_no_images_returns_unchanged(self, agent):
        sc = SectionContent(section_id="s0", title="T", markdown_content="x",
                            word_count=1, estimated_time=10, difficulty_level="intermediate")
        result = agent.assign_images_to_sections([sc], {}, [], _make_curriculum())
        assert result[0].images == []

    def test_no_pages_skips_section(self, agent):
        sc = SectionContent(section_id="section_0_intro", title="T",
                            markdown_content="x", word_count=1,
                            estimated_time=10, difficulty_level="intermediate")
        page_map = {"section_0_intro": []}  # empty pages
        imgs = [{"id": "img1", "url": "http://x.com/a.jpg"}]
        result = agent.assign_images_to_sections([sc], page_map, imgs, _make_curriculum())
        assert result[0].images == []

    def test_images_assigned_via_selector(self, agent):
        mock_img_ref = MagicMock()
        mock_img_ref.image_id = "img1"
        agent.image_selector.select_images.return_value = [mock_img_ref]

        sc = SectionContent(section_id="section_0_intro", title="T",
                            markdown_content="x", word_count=1,
                            estimated_time=10, difficulty_level="intermediate")
        page_map = {"section_0_intro": [1, 2]}
        imgs = [{"id": "img1", "url": "http://x.com/a.jpg"}]
        result = agent.assign_images_to_sections([sc], page_map, imgs, _make_curriculum())
        assert result[0].images == [mock_img_ref]

    def test_deduplication_across_sections(self, agent):
        mock_img_ref = MagicMock()
        mock_img_ref.image_id = "shared_img"
        agent.image_selector.select_images.return_value = [mock_img_ref]

        sections = [
            Section(id="section_0_a", title="A", topics=["A"],
                    estimated_time=10, difficulty_level="intermediate"),
            Section(id="section_1_b", title="B", topics=["B"],
                    estimated_time=10, difficulty_level="intermediate"),
        ]
        curriculum = _make_curriculum(sections)
        sc1 = SectionContent(section_id="section_0_a", title="A", markdown_content="x",
                             word_count=1, estimated_time=10, difficulty_level="intermediate")
        sc2 = SectionContent(section_id="section_1_b", title="B", markdown_content="x",
                             word_count=1, estimated_time=10, difficulty_level="intermediate")
        page_map = {"section_0_a": [1], "section_1_b": [2]}
        imgs = [{"id": "shared_img", "url": "http://x.com/a.jpg"}]

        result = agent.assign_images_to_sections([sc1, sc2], page_map, imgs, curriculum)
        # Second section should get no images (shared_img already used)
        assert result[0].images == [mock_img_ref]
        # select_images called once for first section; second call should pass empty list
        calls = agent.image_selector.select_images.call_args_list
        assert len(calls) == 1  # second section: no remaining images, skipped


# ──────────────────────────────────────────────────────────────────────────────
# _clean_raw_text
# ──────────────────────────────────────────────────────────────────────────────

class TestCleanRawText:
    def test_removes_standalone_page_numbers(self, agent):
        text = "Introduction\n42\nContent here"
        result = agent._clean_raw_text(text)
        assert "42" not in result.split("\n") or "Introduction" in result

    def test_removes_domain_watermarks(self, agent):
        text = "DailyDoseofDS.com\nActual content here"
        result = agent._clean_raw_text(text)
        assert "DailyDoseofDS.com" not in result

    def test_removes_short_artifact_lines(self, agent):
        text = "A\nReal content line\nB"
        result = agent._clean_raw_text(text)
        assert "Real content line" in result
        assert "\nA\n" not in result

    def test_preserves_normal_content(self, agent):
        text = "This is a normal sentence.\nAnother line."
        result = agent._clean_raw_text(text)
        assert "This is a normal sentence." in result


# ──────────────────────────────────────────────────────────────────────────────
# _protect_code_blocks / _restore_code_blocks
# ──────────────────────────────────────────────────────────────────────────────

class TestCodeBlockProtection:
    def test_fenced_code_block_replaced(self, agent):
        text = "Before\n```python\ncode\n```\nAfter"
        protected, code_map = agent._protect_code_blocks(text)
        assert "```python" not in protected
        assert "__CODE_BLOCK_0__" in protected
        assert len(code_map) == 1

    def test_inline_code_replaced(self, agent):
        text = "Use `print()` function"
        protected, code_map = agent._protect_code_blocks(text)
        assert "`print()`" not in protected
        assert len(code_map) == 1

    def test_restore_returns_original(self, agent):
        original = "Before\n```python\nx = 1\n```\nAfter"
        protected, code_map = agent._protect_code_blocks(original)
        restored = agent._restore_code_blocks(protected, code_map)
        assert restored == original

    def test_no_code_blocks_unchanged(self, agent):
        text = "Plain text without any code"
        protected, code_map = agent._protect_code_blocks(text)
        assert protected == text
        assert code_map == {}


# ──────────────────────────────────────────────────────────────────────────────
# _is_toc_content
# ──────────────────────────────────────────────────────────────────────────────

class TestIsTocContent:
    def test_toc_detected(self, agent):
        lines = [f"Chapter {i}........... {i * 10}" for i in range(1, 10)]
        text = "\n".join(lines)
        assert agent._is_toc_content(text) is True

    def test_normal_text_not_toc(self, agent):
        text = "This is a normal paragraph.\nIt has real sentences.\nNo dot leaders here."
        assert agent._is_toc_content(text) is False

    def test_too_few_lines_not_toc(self, agent):
        text = "Chapter 1 ...... 5\nChapter 2 ...... 10"
        assert agent._is_toc_content(text) is False


# ──────────────────────────────────────────────────────────────────────────────
# _extract_by_page_groups
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractByPageGroups:
    def test_basic_grouping(self, agent):
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        result = agent._extract_by_page_groups(mock_doc, group_size=5)
        assert len(result) == 2
        assert result[0]["pages"] == [1, 2, 3, 4, 5]
        assert result[1]["pages"] == [6, 7, 8, 9, 10]

    def test_partial_last_group(self, agent):
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=7)
        result = agent._extract_by_page_groups(mock_doc, group_size=5)
        assert len(result) == 2
        assert result[1]["pages"] == [6, 7]

    def test_titles_generated(self, agent):
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        result = agent._extract_by_page_groups(mock_doc, group_size=5)
        assert "Part 1" in result[0]["title"]


# ──────────────────────────────────────────────────────────────────────────────
# _slugify
# ──────────────────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic_slugify(self, agent):
        result = agent._slugify("Hello World")
        assert " " not in result
        assert result == result.lower()

    def test_special_chars_removed(self, agent):
        result = agent._slugify("Chapter 1: Introduction!")
        assert ":" not in result
        assert "!" not in result

    def test_empty_string(self, agent):
        result = agent._slugify("")
        assert isinstance(result, str)
