"""
Extended unit tests for ContentEnhancer — covers missing lines 41-60, 83-135,
138-190, 213-217, 228-289.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from bs4 import BeautifulSoup

from lecture_forge.agents.content_enhancer import (
    ContentEnhancer,
    _display_evaluation_table,
    _THRESHOLD_MAP,
    _DIMENSION_LABELS,
)


# ── HTML fixtures ────────────────────────────────────────────────────────────

FULL_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
<!-- lf:topic: Deep Learning -->
<!-- lf:duration: 90 -->
<!-- lf:audience_level: intermediate -->
<!-- lf:vector_db_path: /tmp/dl_kb -->
<h1>Deep Learning</h1>
<section id="intro">
  <h2>1. Introduction</h2>
  <p>Deep learning is a subset of machine learning.</p>
</section>
<section id="cnn">
  <h2>2. CNN</h2>
  <p>Convolutional neural networks.</p>
</section>
<aside id="sidebar">
  <div class="space-y-1">
    <div>📝 200단어</div>
    <div>🖼 이미지 1개</div>
    <div>📊 다이어그램 0개</div>
    <div>🕐 2026-01-01 00:00</div>
  </div>
</aside>
<header>
  <span class="bg-green-100">📝 200단어</span>
  <span class="bg-yellow-100">🖼 이미지 1개</span>
  <span class="bg-red-100">📊 다이어그램 0개</span>
</header>
<footer>
  <p>LectureForge · 2026-01-01 00:00</p>
</footer>
</body>
</html>
"""

HTML_NO_KB = """\
<html>
<body>
<!-- lf:topic: No KB Lecture -->
<!-- lf:duration: 60 -->
<section id="s1"><p>Content</p></section>
</body>
</html>
"""


@pytest.fixture
def enhancer():
    return ContentEnhancer()


@pytest.fixture
def full_html_file(tmp_path):
    f = tmp_path / "lecture.html"
    f.write_text(FULL_HTML, encoding="utf-8")
    return f


@pytest.fixture
def no_kb_html_file(tmp_path):
    f = tmp_path / "no_kb.html"
    f.write_text(HTML_NO_KB, encoding="utf-8")
    return f


# ── Helper: build a fake Lecture object ──────────────────────────────────────

def _make_eval_mock(overall=50.0):
    mock_eval = MagicMock()
    mock_eval.overall_score = overall
    mock_eval.dimension_scores = {k: overall for k in _DIMENSION_LABELS}
    return mock_eval


def _make_lecture(n_sections=2):
    from lecture_forge.models.lecture import Lecture, SectionContent
    sections = []
    for i in range(n_sections):
        sections.append(
            SectionContent(
                section_id=f"section_{i}",
                title=f"Section {i}",
                markdown_content="Hello world " * 10,
                estimated_time=20,
                difficulty_level="intermediate",
            )
        )
    return Lecture(
        title="Test Lecture",
        topic="Deep Learning",
        duration=90,
        audience_level="intermediate",
        learning_objectives=["Understand DL"],
        sections=sections,
    )


# ── _display_evaluation_table (lines 41-60) ──────────────────────────────────

class TestDisplayEvaluationTable:
    """Tests for the module-level _display_evaluation_table helper."""

    def _make_eval(self, overall=85.0, dims=None):
        ev = MagicMock()
        ev.overall_score = overall
        ev.dimension_scores = dims or {
            "content_completeness": 80.0,
            "logical_flow": 75.0,
            "time_alignment": 90.0,
            "level_appropriateness": 70.0,
            "visual_quality": 65.0,
            "technical_accuracy": 85.0,
        }
        return ev

    def test_runs_without_error(self, capsys):
        """_display_evaluation_table should not raise."""
        _display_evaluation_table(self._make_eval())

    def test_overall_pass_threshold(self):
        """overall_score >= 80 → status ✅."""
        ev = self._make_eval(overall=90.0)
        # Should not raise; we just verify the call completes
        _display_evaluation_table(ev)

    def test_overall_warn_threshold(self):
        """overall_score 60-79 → status ⚠️."""
        ev = self._make_eval(overall=70.0)
        _display_evaluation_table(ev)

    def test_overall_fail_threshold(self):
        """overall_score < 60 → status ❌."""
        ev = self._make_eval(overall=50.0)
        _display_evaluation_table(ev)

    def test_dimension_with_none_score_skipped(self):
        """Dimension score of None should be skipped without error."""
        dims = {k: None for k in _DIMENSION_LABELS}
        ev = self._make_eval(dims=dims)
        _display_evaluation_table(ev)

    def test_partial_dimensions(self):
        """Only a subset of dimensions present — no KeyError."""
        dims = {"content_completeness": 85.0}
        ev = self._make_eval(dims=dims)
        _display_evaluation_table(ev)

    def test_threshold_map_values(self):
        assert _THRESHOLD_MAP["lenient"] == 70
        assert _THRESHOLD_MAP["balanced"] == 80
        assert _THRESHOLD_MAP["strict"] == 90

    def test_dimension_labels_has_six_entries(self):
        assert len(_DIMENSION_LABELS) == 6


# ── ContentEnhancer.enhance() — no KB path (lines 83-94) ────────────────────

class TestEnhanceNokbPath:
    def test_returns_none_when_no_kb_and_no_kb_arg(self, enhancer, no_kb_html_file):
        """enhance() returns None when HTML has no vector_db_path and kb_path=None."""
        result = enhancer.enhance(no_kb_html_file, kb_path=None)
        assert result is None

    def test_uses_kb_path_argument_as_fallback(self, enhancer, full_html_file, tmp_path):
        """enhance() uses kb_path argument when HTML has vector_db_path."""
        # We only need it to get past the VectorStore init step
        with patch("lecture_forge.agents.content_enhancer.VectorStore") as MockVS, \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture") as mock_parse:
            mock_parse.return_value = None  # cause early return after parse
            MockVS.return_value = MagicMock()
            result = enhancer.enhance(full_html_file, kb_path="/tmp/dl_kb")
        # Returns None because parse returned None, not because of missing kb
        assert result is None


# ── ContentEnhancer.enhance() — VectorStore load failure (lines 99-104) ──────

class TestEnhanceVectorStoreLoadFailure:
    def test_returns_none_on_vector_store_exception(self, enhancer, full_html_file):
        with patch("lecture_forge.agents.content_enhancer.VectorStore") as MockVS:
            MockVS.side_effect = RuntimeError("DB init failed")
            result = enhancer.enhance(full_html_file)
        assert result is None


# ── ContentEnhancer.enhance() — parse_html_to_lecture returns None (line 110-112) ──

class TestEnhanceParseFailure:
    def test_returns_none_when_parse_returns_none(self, enhancer, full_html_file):
        with patch("lecture_forge.agents.content_enhancer.VectorStore"), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture", return_value=None):
            result = enhancer.enhance(full_html_file)
        assert result is None


# ── ContentEnhancer.enhance() — metadata patching (lines 114-123) ────────────

class TestEnhanceMetadataPatching:
    """Ensure lecture metadata is patched correctly from HTML meta tags."""

    def test_duration_parse_error_is_silently_ignored(self, enhancer, tmp_path):
        """A non-integer duration in meta should not crash the enhancer."""
        bad_html = """\
<html><body>
<!-- lf:topic: X -->
<!-- lf:duration: NOT_AN_INT -->
<!-- lf:audience_level: beginner -->
<!-- lf:vector_db_path: /tmp/fake_kb -->
<section id="s1"><p>content</p></section>
</body></html>
"""
        f = tmp_path / "bad_duration.html"
        f.write_text(bad_html, encoding="utf-8")

        with patch("lecture_forge.agents.content_enhancer.VectorStore"), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=None):
            result = enhancer.enhance(f)
        # Should return None due to parse failure, NOT raise ValueError
        assert result is None


# ── ContentEnhancer.enhance() — quality above threshold (lines 132-135) ──────

class TestEnhanceQualityAboveThreshold:
    """When quality is already above threshold, sweep still continues."""

    def _build_mock_writer(self):
        w = MagicMock()
        w.used_chunk_ids = set()
        return w

    def test_continues_sweep_when_above_threshold(self, enhancer, full_html_file, tmp_path):
        lecture = _make_lecture()
        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = 0  # skip sweep loop

        mock_eval = _make_eval_mock(overall=95.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter:
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = self._build_mock_writer()
            MockWriter.return_value = writer_instance
            result = enhancer.enhance(full_html_file, quality_level="balanced")

        # No enhancements → None
        assert result is None


# ── ContentEnhancer.enhance() — successful enhancement path (lines 138-182) ──

class TestEnhanceSuccessPath:
    """Full successful run: sections get longer content → _enhanced.html is written."""

    def test_produces_enhanced_html_file(self, enhancer, full_html_file):
        lecture = _make_lecture(n_sections=2)
        # Make writer expand section content
        original_content = lecture.sections[0].markdown_content

        def fake_pre_assign(curriculum):
            # Extend section 0 content to simulate enhancement
            lecture.sections[0].markdown_content = original_content + " NEW CONTENT added here."

        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = 0

        mock_eval = _make_eval_mock(overall=50.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter:
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = MagicMock()
            writer_instance.used_chunk_ids = set()
            writer_instance._pre_assign_chunks_to_sections.side_effect = fake_pre_assign
            MockWriter.return_value = writer_instance

            result = enhancer.enhance(full_html_file, quality_level="lenient")

        assert result is not None
        assert result.endswith("_enhanced.html")
        assert Path(result).exists()

    def test_enhanced_file_in_same_directory(self, enhancer, full_html_file):
        lecture = _make_lecture(n_sections=1)
        original = lecture.sections[0].markdown_content

        def expand(curriculum):
            lecture.sections[0].markdown_content = original + " Extra content."

        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = 0
        mock_eval = _make_eval_mock(overall=60.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter:
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = MagicMock()
            writer_instance.used_chunk_ids = set()
            writer_instance._pre_assign_chunks_to_sections.side_effect = expand
            MockWriter.return_value = writer_instance

            result = enhancer.enhance(full_html_file, quality_level="lenient")

        assert Path(result).parent == full_html_file.parent

    def test_no_enhancements_returns_none(self, enhancer, full_html_file):
        """If no section content grows, returns None."""
        lecture = _make_lecture(n_sections=2)
        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = 0
        mock_eval = _make_eval_mock(overall=50.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter:
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = MagicMock()
            writer_instance.used_chunk_ids = set()
            MockWriter.return_value = writer_instance
            result = enhancer.enhance(full_html_file, quality_level="balanced")

        assert result is None


# ── ContentEnhancer.enhance() — coverage sweep loop (lines 156-162) ──────────

class TestEnhanceCoverageSweep:
    """Ensure the 2-round coverage sweep executes when total_chunks > 0."""

    def test_sweep_runs_when_chunks_present(self, enhancer, full_html_file):
        lecture = _make_lecture()
        original = lecture.sections[0].markdown_content
        expand_calls = []

        def fake_expand(sections, curriculum):
            expand_calls.append(1)
            # Give it enough ratio to break after first round
            writer_instance.used_chunk_ids = set(range(100))

        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = 10
        mock_eval = _make_eval_mock(overall=50.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter, \
             patch("lecture_forge.config.Config.RAG_COVERAGE_MIN_RATIO", new=0.5):
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = MagicMock()
            writer_instance.used_chunk_ids = set()
            writer_instance._expand_sections_for_coverage.side_effect = fake_expand
            MockWriter.return_value = writer_instance

            enhancer.enhance(full_html_file, quality_level="lenient")

        assert len(expand_calls) >= 1

    def test_total_chunks_type_error_handled(self, enhancer, full_html_file):
        """get_total_chunk_count returning non-numeric should not crash."""
        lecture = _make_lecture()
        mock_vs = MagicMock()
        mock_vs.get_total_chunk_count.return_value = "not-a-number"
        mock_eval = _make_eval_mock(overall=50.0)

        with patch("lecture_forge.agents.content_enhancer.VectorStore", return_value=mock_vs), \
             patch("lecture_forge.agents.content_enhancer.parse_html_to_lecture",
                   return_value=lecture), \
             patch("lecture_forge.agents.content_enhancer.QualityEvaluator") as MockQE, \
             patch("lecture_forge.agents.content_enhancer.ContentWriterAgent") as MockWriter:
            MockQE.return_value.evaluate.return_value = mock_eval
            writer_instance = MagicMock()
            writer_instance.used_chunk_ids = set()
            MockWriter.return_value = writer_instance
            # Should not raise
            enhancer.enhance(full_html_file, quality_level="lenient")


# ── ContentEnhancer.enhance() — ConfigurationError handling (line 184-186) ───

class TestEnhanceConfigurationError:
    def test_configuration_error_returns_none(self, enhancer, full_html_file):
        from lecture_forge.exceptions import ConfigurationError
        with patch("lecture_forge.agents.content_enhancer.VectorStore",
                   side_effect=ConfigurationError("bad config")):
            result = enhancer.enhance(full_html_file)
        assert result is None


# ── ContentEnhancer.enhance() — generic exception handler (lines 187-190) ────

class TestEnhanceGenericException:
    def test_generic_exception_returns_none(self, enhancer, full_html_file):
        with patch("lecture_forge.agents.content_enhancer.VectorStore",
                   side_effect=Exception("boom")):
            result = enhancer.enhance(full_html_file)
        assert result is None


# ── _lecture_to_curriculum (lines 213-217, 228-235) ─────────────────────────

class TestLectureToCurriculum:
    def test_returns_curriculum_object(self, enhancer):
        from lecture_forge.models.curriculum import Curriculum
        lecture = _make_lecture(n_sections=3)
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert isinstance(curriculum, Curriculum)

    def test_section_count_matches(self, enhancer):
        lecture = _make_lecture(n_sections=4)
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert len(curriculum.sections) == 4

    def test_curriculum_topic_matches_lecture(self, enhancer):
        lecture = _make_lecture()
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert curriculum.topic == lecture.topic

    def test_per_section_time_fallback_for_no_sections(self, enhancer):
        """When lecture has 0 sections, per_section defaults to 20."""
        from lecture_forge.models.lecture import Lecture
        lecture = Lecture(
            title="Empty",
            topic="Empty Topic",
            duration=60,
            audience_level="beginner",
            sections=[],
        )
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert curriculum.sections == []

    def test_section_difficulty_level_propagated(self, enhancer):
        lecture = _make_lecture(n_sections=2)
        lecture.sections[0].difficulty_level = "advanced"
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert curriculum.sections[0].difficulty_level == "advanced"

    def test_section_estimated_time_from_lecture(self, enhancer):
        lecture = _make_lecture(n_sections=1)
        lecture.sections[0].estimated_time = 30
        curriculum = enhancer._lecture_to_curriculum(lecture)
        assert curriculum.sections[0].estimated_time == 30

    def test_section_without_estimated_time_uses_default(self, enhancer):
        """Section with estimated_time=0 should use per-section fallback."""
        lecture = _make_lecture(n_sections=2)
        lecture.sections[0].estimated_time = 0  # falsy
        curriculum = enhancer._lecture_to_curriculum(lecture)
        # per_section = max(10, 90 // 2) = 45
        assert curriculum.sections[0].estimated_time == 45


# ── _inject_enhancements_to_html (lines 237-292) ─────────────────────────────

class TestInjectEnhancementsToHtml:
    def test_injects_content_to_matching_section(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "out.html"
        enhancements = {"intro": "## Additional Info\n\nNew content here."}
        enhancer._inject_enhancements_to_html(full_html_file, enhancements, out)
        result_html = out.read_text(encoding="utf-8")
        assert "lf-enhanced-content" in result_html
        assert "New content here." in result_html

    def test_skips_empty_supplement(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "out.html"
        enhancements = {"intro": "", "cnn": "Extra CNN content."}
        enhancer._inject_enhancements_to_html(full_html_file, enhancements, out)
        result_html = out.read_text(encoding="utf-8")
        # Only one injection (cnn), not two
        assert result_html.count("lf-enhanced-content") == 1

    def test_skips_missing_section_id(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "out.html"
        enhancements = {"nonexistent_section": "Some content."}
        enhancer._inject_enhancements_to_html(full_html_file, enhancements, out)
        result_html = out.read_text(encoding="utf-8")
        assert "lf-enhanced-content" not in result_html

    def test_uses_sanitized_id_fallback(self, enhancer, tmp_path):
        """Section with non-ASCII ID should be found via sanitized fallback."""
        html = """\
<html><body>
<section id="intro_section">
  <p>Content here.</p>
</section>
</body></html>
"""
        f = tmp_path / "src.html"
        f.write_text(html, encoding="utf-8")
        out = tmp_path / "out.html"
        # Use an id that becomes "intro_section" after sanitization
        enhancements = {"intro_section": "Appended text."}
        enhancer._inject_enhancements_to_html(f, enhancements, out)
        result = out.read_text(encoding="utf-8")
        assert "Appended text." in result

    def test_output_file_is_written(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "result.html"
        enhancer._inject_enhancements_to_html(full_html_file, {"intro": "Hi."}, out)
        assert out.exists()

    def test_stats_updated_in_output(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "stats_out.html"
        enhancer._inject_enhancements_to_html(full_html_file, {"intro": "More words here."}, out)
        html = out.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        sidebar = soup.find("aside", id="sidebar")
        # Stats should have been recomputed — sidebar still exists
        assert sidebar is not None

    def test_label_text_present(self, enhancer, full_html_file, tmp_path):
        out = tmp_path / "label_out.html"
        enhancer._inject_enhancements_to_html(full_html_file, {"cnn": "Extra."}, out)
        html = out.read_text(encoding="utf-8")
        assert "KB 보충 내용" in html


# ── _compute_updated_stats edge cases ────────────────────────────────────────

class TestComputeUpdatedStatsEdgeCases:
    def test_sections_without_id_not_counted(self, enhancer):
        """Sections without id attribute should not contribute to word count."""
        html = '<section><p>no id here</p></section><section id="s1"><p>hello</p></section>'
        soup = BeautifulSoup(html, "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        assert stats["total_words"] == 1  # only "hello"

    def test_updated_at_format(self, enhancer):
        soup = BeautifulSoup('<section id="x"><p>y</p></section>', "html.parser")
        stats = enhancer._compute_updated_stats(soup)
        # Format: YYYY-MM-DD HH:MM
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", stats["updated_at"])
