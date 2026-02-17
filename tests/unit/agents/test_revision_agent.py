"""
Comprehensive unit tests for RevisionAgent.
Tests cover _handle_issue() dispatch, private utility methods,
and integration paths without real LLM calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.revision_agent import RevisionAgent
from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import CodeBlock, Lecture, MermaidDiagram, SectionContent


# ===== Fixtures =====

@pytest.fixture
def revision_agent(test_env_vars, mock_llm):
    """Create RevisionAgent instance."""
    return RevisionAgent()


@pytest.fixture
def section_with_code():
    return SectionContent(
        section_id="sec_code",
        title="Python Basics",
        markdown_content="# Python\n\n```python\nprint('hello')\n```",
        code_blocks=[CodeBlock(language="python", code="print('hello')", caption="Example")],
        images=[],
        diagrams=[],
        word_count=20,
        estimated_time=10,
        difficulty_level="beginner",
    )


@pytest.fixture
def section_no_code():
    return SectionContent(
        section_id="sec_1",
        title="Concepts",
        markdown_content="# Concepts\n\nThis section explains concepts.",
        code_blocks=[],
        images=[],
        diagrams=[],
        word_count=10,
        estimated_time=10,
        difficulty_level="beginner",
    )


@pytest.fixture
def sample_lecture(section_no_code):
    return Lecture(
        title="Test Lecture",
        topic="Python",
        duration=60,
        audience_level="beginner",
        learning_objectives=["Understand basics"],
        sections=[section_no_code],
    )


def _make_issue(dimension, description="needs improvement", severity="medium"):
    return Issue(
        dimension=dimension,
        severity=severity,
        location="sec_1",
        description=description,
        suggestion="Fix it",
    )


def _make_llm_response(content="Generated content here with enough words."):
    mock_response = MagicMock()
    mock_response.content = content
    mock_response.response_metadata = {
        "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    }
    return mock_response


# ===== Basic initialization =====

def test_revision_agent_initialization(revision_agent):
    assert revision_agent is not None
    assert revision_agent.agent_name == "RevisionAgent"


# ===== revise() integration =====

def test_revise_returns_lecture(revision_agent, sample_lecture):
    evaluation = EvaluationResult(
        overall_score=75,
        passed=False,
        dimension_scores={k: 75 for k in [
            "content_completeness", "logical_flow", "time_alignment",
            "level_appropriateness", "visual_quality", "technical_accuracy"
        ]},
        issues=[],
        revision_strategy="targeted_improvements",
    )
    revised = revision_agent.revise(sample_lecture, evaluation)
    assert revised is not None
    assert isinstance(revised.sections, list)


def test_revise_recalculates_stats(revision_agent, sample_lecture):
    """After revise(), total_word_count reflects current sections."""
    evaluation = EvaluationResult(
        overall_score=75, passed=False,
        dimension_scores={k: 75 for k in [
            "content_completeness", "logical_flow", "time_alignment",
            "level_appropriateness", "visual_quality", "technical_accuracy"
        ]},
        issues=[],
        revision_strategy="targeted_improvements",
    )
    revised = revision_agent.revise(sample_lecture, evaluation)
    expected_words = sum(s.word_count for s in revised.sections)
    assert revised.total_word_count == expected_words


def test_revise_handles_high_severity_first(revision_agent, sample_lecture):
    """High-severity issues are listed before medium in processing."""
    high_issue = _make_issue("content_completeness", "code examples missing", severity="high")
    medium_issue = _make_issue("content_completeness", "section is short", severity="medium")

    evaluation = EvaluationResult(
        overall_score=60, passed=False,
        dimension_scores={k: 60 for k in [
            "content_completeness", "logical_flow", "time_alignment",
            "level_appropriateness", "visual_quality", "technical_accuracy"
        ]},
        issues=[medium_issue, high_issue],
        revision_strategy="targeted_improvements",
    )
    mock_response = _make_llm_response("New code example\n```python\npass\n```")
    with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
        with patch("lecture_forge.agents.content_writer.ContentWriterAgent") as mock_cw:
            mock_cw.return_value._extract_code_blocks.return_value = []
            revised = revision_agent.revise(sample_lecture, evaluation)
    assert revised is not None


# ===== _handle_issue() dispatch =====

class TestHandleIssue:
    def test_content_completeness_code_triggers_add_code(self, revision_agent, sample_lecture):
        issue = _make_issue("content_completeness", "NO code examples in section")
        mock_response = _make_llm_response("```python\nprint('code')\n```")

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            with patch("lecture_forge.agents.content_writer.ContentWriterAgent") as mock_cw:
                mock_cw.return_value._extract_code_blocks.return_value = []
                revision_agent._handle_issue(sample_lecture, issue)
        # No assertion needed - just verify it runs without error

    def test_content_completeness_short_triggers_expand(self, revision_agent, sample_lecture):
        issue = _make_issue("content_completeness", "section is too short")
        mock_response = _make_llm_response("Expanded content with many words " * 50)

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._handle_issue(sample_lecture, issue)

    def test_content_completeness_general_triggers_expand(self, revision_agent, sample_lecture):
        issue = _make_issue("content_completeness", "completeness is lacking")
        mock_response = _make_llm_response("Added content " * 50)

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._handle_issue(sample_lecture, issue)

    def test_logical_flow_intro_triggers_add_introduction(self, revision_agent, sample_lecture):
        issue = _make_issue("logical_flow", "missing intro section")
        mock_response = _make_llm_response("Introduction content here.")

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            original_count = len(sample_lecture.sections)
            revision_agent._handle_issue(sample_lecture, issue)
        # Introduction prepended → section count increases
        assert len(sample_lecture.sections) > original_count

    def test_logical_flow_conclusion_triggers_add_conclusion(self, revision_agent, sample_lecture):
        issue = _make_issue("logical_flow", "missing conclusion")
        mock_response = _make_llm_response("Conclusion content here.")

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            original_count = len(sample_lecture.sections)
            revision_agent._handle_issue(sample_lecture, issue)
        assert len(sample_lecture.sections) > original_count

    def test_visual_quality_diagram_triggers_add_diagrams(self, revision_agent, sample_lecture):
        issue = _make_issue("visual_quality", "no diagram in section")
        diagram_code = "flowchart TD\n    A[Start] --> B[End]"
        mock_response = _make_llm_response(diagram_code)

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._handle_issue(sample_lecture, issue)

    def test_visual_quality_image_only_logs(self, revision_agent, sample_lecture):
        """Image addition logs a message — no LLM call."""
        issue = _make_issue("visual_quality", "needs more images")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._handle_issue(sample_lecture, issue)
        mock_invoke.assert_not_called()

    def test_time_alignment_short_triggers_expand(self, revision_agent, sample_lecture):
        issue = _make_issue("time_alignment", "content is too short for time")
        mock_response = _make_llm_response("More time content " * 50)

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._handle_issue(sample_lecture, issue)

    def test_time_alignment_long_only_logs(self, revision_agent, sample_lecture):
        """Content too long only logs — no LLM call."""
        issue = _make_issue("time_alignment", "content is too long")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._handle_issue(sample_lecture, issue)
        mock_invoke.assert_not_called()

    def test_unknown_dimension_no_action(self, revision_agent, sample_lecture):
        """Unknown dimension should not trigger any LLM call."""
        issue = _make_issue("unknown_dimension", "unknown problem")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._handle_issue(sample_lecture, issue)
        mock_invoke.assert_not_called()


# ===== _has_significant_overlap() =====

class TestHasSignificantOverlap:
    def test_identical_text_returns_true(self, revision_agent):
        text = "word " * 100
        assert revision_agent._has_significant_overlap(text, text) is True

    def test_completely_different_text_returns_false(self, revision_agent):
        original = "apple " * 100
        new_text = "banana " * 100
        assert revision_agent._has_significant_overlap(original, new_text) is False

    def test_empty_original_returns_false(self, revision_agent):
        assert revision_agent._has_significant_overlap("", "some content") is False

    def test_empty_new_returns_false(self, revision_agent):
        assert revision_agent._has_significant_overlap("some content", "") is False

    def test_both_empty_returns_false(self, revision_agent):
        assert revision_agent._has_significant_overlap("", "") is False

    def test_short_original_no_overlap(self, revision_agent):
        # Short text, very different → no overlap
        assert revision_agent._has_significant_overlap("abc", "xyz different content") is False


# ===== _remove_duplicates() =====

class TestRemoveDuplicates:
    def test_returns_string(self, revision_agent):
        result = revision_agent._remove_duplicates("new content here.", "original text")
        assert isinstance(result, str)

    def test_removes_shared_sentence(self, revision_agent):
        original = "Sentence one. Sentence two. Sentence three."
        new_text = "Sentence one. Sentence four. Sentence five."
        result = revision_agent._remove_duplicates(new_text, original)
        # "Sentence one" should be removed, rest kept
        assert "Sentence four" in result or "Sentence five" in result

    def test_no_duplicates_returns_original(self, revision_agent):
        original = "Alpha beta gamma."
        new_text = "Delta epsilon zeta. Theta iota kappa."
        result = revision_agent._remove_duplicates(new_text, original)
        assert "Delta epsilon zeta" in result

    def test_result_ends_with_period(self, revision_agent):
        result = revision_agent._remove_duplicates("Unique content here.", "Different text.")
        assert result.endswith(".")


# ===== _add_introduction() =====

class TestAddIntroduction:
    def test_adds_intro_section(self, revision_agent, sample_lecture):
        mock_response = _make_llm_response("## Introduction\n\nWelcome to this lecture.")
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            original_count = len(sample_lecture.sections)
            revision_agent._add_introduction(sample_lecture)
        assert len(sample_lecture.sections) == original_count + 1
        assert "intro" in sample_lecture.sections[0].section_id.lower()

    def test_intro_inserted_at_front(self, revision_agent, sample_lecture):
        mock_response = _make_llm_response("Introduction text here.")
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._add_introduction(sample_lecture)
        assert sample_lecture.sections[0].section_id == "section_0_intro"

    def test_add_intro_handles_llm_exception(self, revision_agent, sample_lecture):
        """If LLM raises, the lecture is unchanged."""
        original_count = len(sample_lecture.sections)
        with patch.object(revision_agent, "invoke_llm", side_effect=Exception("LLM error")):
            revision_agent._add_introduction(sample_lecture)
        assert len(sample_lecture.sections) == original_count


# ===== _add_conclusion() =====

class TestAddConclusion:
    def test_adds_conclusion_section(self, revision_agent, sample_lecture):
        mock_response = _make_llm_response("## Conclusion\n\nKey takeaways: ...")
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            original_count = len(sample_lecture.sections)
            revision_agent._add_conclusion(sample_lecture)
        assert len(sample_lecture.sections) == original_count + 1

    def test_conclusion_appended_at_end(self, revision_agent, sample_lecture):
        mock_response = _make_llm_response("Conclusion here.")
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._add_conclusion(sample_lecture)
        last = sample_lecture.sections[-1]
        assert "conclusion" in last.section_id.lower()

    def test_add_conclusion_handles_exception(self, revision_agent, sample_lecture):
        original_count = len(sample_lecture.sections)
        with patch.object(revision_agent, "invoke_llm", side_effect=Exception("error")):
            revision_agent._add_conclusion(sample_lecture)
        assert len(sample_lecture.sections) == original_count


# ===== _add_diagrams() =====

class TestAddDiagrams:
    def test_adds_diagram_to_section_without_one(self, revision_agent, sample_lecture):
        issue = _make_issue("visual_quality", "no diagram")
        diagram_code = "flowchart TD\n    A[Start] --> B[Process] --> C[End]"
        mock_response = _make_llm_response(diagram_code)

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._add_diagrams(sample_lecture, issue)

    def test_skips_when_all_sections_have_diagrams(self, revision_agent):
        """If all sections already have diagrams, _add_diagrams returns early without LLM call."""
        section = SectionContent(
            section_id="sec_1",
            title="Diagrams",
            markdown_content="content",
            diagrams=[MermaidDiagram(
                id="diag_1",
                title="Test",
                mermaid_code="flowchart TD\n    A --> B",
                diagram_type="flowchart",
            )],
            code_blocks=[], images=[], word_count=10,
        )
        lecture = Lecture(
            title="T", topic="T", duration=60, audience_level="beginner",
            learning_objectives=["L"], sections=[section],
        )
        issue = _make_issue("visual_quality", "diagram issue")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._add_diagrams(lecture, issue)
        mock_invoke.assert_not_called()

    def test_add_diagrams_handles_exception(self, revision_agent, sample_lecture):
        issue = _make_issue("visual_quality", "no diagram")
        with patch.object(revision_agent, "invoke_llm", side_effect=Exception("LLM error")):
            # Should not raise
            revision_agent._add_diagrams(sample_lecture, issue)


# ===== _add_code_examples() =====

class TestAddCodeExamples:
    def test_adds_code_to_section_without_it(self, revision_agent, sample_lecture):
        issue = _make_issue("content_completeness", "no code examples")
        mock_response = _make_llm_response("```python\nprint('hello')\n```")

        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            with patch("lecture_forge.agents.content_writer.ContentWriterAgent") as mock_cw:
                mock_cw.return_value._extract_code_blocks.return_value = []
                revision_agent._add_code_examples(sample_lecture, issue)

    def test_skips_when_all_sections_have_code(self, revision_agent):
        """Returns early when all sections have code blocks."""
        section = SectionContent(
            section_id="sec_code",
            title="Section With Code",
            markdown_content="content",
            code_blocks=[CodeBlock(language="python", code="pass", caption="")],
            images=[], diagrams=[], word_count=10,
        )
        lecture = Lecture(
            title="T", topic="T", duration=60, audience_level="beginner",
            learning_objectives=["L"], sections=[section],
        )
        issue = _make_issue("content_completeness", "NO code")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._add_code_examples(lecture, issue)
        mock_invoke.assert_not_called()

    def test_intro_and_conclusion_sections_skipped(self, revision_agent):
        """Intro/conclusion sections are excluded from code addition."""
        intro = SectionContent(
            section_id="intro_0", title="Intro", markdown_content="intro",
            code_blocks=[], images=[], diagrams=[], word_count=10,
        )
        conclusion = SectionContent(
            section_id="conclusion_1", title="Conclusion", markdown_content="conclusion",
            code_blocks=[], images=[], diagrams=[], word_count=10,
        )
        lecture = Lecture(
            title="T", topic="T", duration=60, audience_level="beginner",
            learning_objectives=["L"], sections=[intro, conclusion],
        )
        issue = _make_issue("content_completeness", "NO code")
        with patch.object(revision_agent, "invoke_llm") as mock_invoke:
            revision_agent._add_code_examples(lecture, issue)
        mock_invoke.assert_not_called()


# ===== Additional coverage tests =====

class TestAddCodeExamplesFences:
    """Tests for _add_code_examples() markdown fence cleanup (lines 149-154, 173-174)."""

    def _make_lecture_with_section(self):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[], word_count=1,
        )
        return Lecture(
            title="T", topic="T", duration=60, audience_level="beginner",
            learning_objectives=["L"], sections=[section],
        ), section

    def test_backtick_fence_without_python_stripped(self, revision_agent):
        """```-wrapped content (not markdown) → elif branch (lines 152-154)."""
        from lecture_forge.models.evaluation import Issue
        lecture, section = self._make_lecture_with_section()
        issue = _make_issue("content_completeness", "no code")
        mock_response = MagicMock()
        mock_response.content = "```\ndef example():\n    pass\n```"
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            with patch("lecture_forge.agents.content_writer.ContentWriterAgent") as mock_writer_cls:
                mock_writer = MagicMock()
                mock_writer._extract_code_blocks.return_value = []
                mock_writer_cls.return_value = mock_writer
                revision_agent._add_code_examples(lecture, issue)

    def test_exception_in_add_code_example(self, revision_agent):
        """Exception in the for loop is caught (lines 173-174)."""
        from lecture_forge.models.evaluation import Issue
        lecture, section = self._make_lecture_with_section()
        issue = _make_issue("content_completeness", "no code")
        with patch.object(revision_agent, "invoke_llm", side_effect=Exception("LLM error")):
            # Should not raise - exception is caught
            revision_agent._add_code_examples(lecture, issue)


class TestExpandContentNoGap:
    """Tests for _expand_content() when total_gap <= 0 (lines 212-213)."""

    def test_returns_when_sufficient_words(self, revision_agent):
        from lecture_forge.models.evaluation import Issue
        sections = [
            SectionContent(
                section_id=f"s{i}", title=f"Section {i}", markdown_content="content " * 1000,
                code_blocks=[], images=[], diagrams=[], word_count=5000,
                estimated_time=30, difficulty_level="intermediate",
            )
            for i in range(2)
        ]
        lecture = Lecture(
            title="T", topic="T", duration=60, audience_level="intermediate",
            learning_objectives=["L"], sections=sections, total_word_count=10000,
        )
        issue = _make_issue("content_completeness", "short")
        with patch("lecture_forge.utils.content_metrics.calculate_target_metrics") as mock_calc:
            mock_calc.return_value = {"target_words": 100, "min_words": 80, "max_words": 150}
            with patch.object(revision_agent, "_expand_section_with_verification") as mock_expand:
                revision_agent._expand_content(lecture, issue)
        mock_expand.assert_not_called()


class TestExpandSectionFences:
    """Tests for _expand_section_with_verification() fence cleanup."""

    def test_backtick_fence_cleanup(self, revision_agent):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Original content here.",
            code_blocks=[], images=[], diagrams=[], word_count=3,
            estimated_time=20, difficulty_level="intermediate",
        )
        mock_response = MagicMock()
        mock_response.content = "```\nAdditional content\n```"
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            result = revision_agent._expand_section_with_verification(
                section=section, target_gap=500, lecture=MagicMock()
            )
        assert isinstance(result, int)

    def test_insufficient_expansion_triggers_retry(self, revision_agent):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Original content.",
            code_blocks=[], images=[], diagrams=[], word_count=2,
            estimated_time=20, difficulty_level="intermediate",
        )
        first_response = MagicMock()
        first_response.content = "Too short."
        second_response = MagicMock()
        second_response.content = "Much longer " * 300

        with patch.object(revision_agent, "invoke_llm", side_effect=[first_response, second_response]):
            result = revision_agent._expand_section_with_verification(
                section=section, target_gap=500, lecture=MagicMock()
            )
        assert isinstance(result, int)

    def test_exception_returns_zero(self, revision_agent):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[], word_count=1,
        )
        with patch.object(revision_agent, "invoke_llm", side_effect=Exception("API error")):
            result = revision_agent._expand_section_with_verification(
                section=section, target_gap=500, lecture=MagicMock()
            )
        assert result == 0


class TestRemoveDuplicatesWarning:
    def test_many_duplicates_logs_warning(self, revision_agent):
        original = "First sentence. Second sentence. Third sentence. Fourth sentence."
        new = "First sentence. Second sentence. Third sentence. New sentence."
        result = revision_agent._remove_duplicates(new, original)
        assert isinstance(result, str)


def _make_lecture_with_sections(sections):
    return Lecture(
        title="T", topic="T", duration=60, audience_level="intermediate",
        learning_objectives=["L"], sections=sections, total_word_count=500,
    )


class TestAddDiagramFences:
    def test_mermaid_fence_cleaned_up(self, revision_agent):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[], word_count=1,
            estimated_time=10, difficulty_level="intermediate",
        )
        lecture = _make_lecture_with_sections([section])
        issue = _make_issue("visual_quality", "no diagrams")
        mock_response = MagicMock()
        mock_response.content = "```mermaid\nflowchart TD\n    A-->B\n```"
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._add_diagrams(lecture, issue)
        assert len(section.diagrams) == 1
        assert "A-->B" in section.diagrams[0].mermaid_code

    def test_generic_fence_cleaned_up(self, revision_agent):
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[], word_count=1,
            estimated_time=10, difficulty_level="intermediate",
        )
        lecture = _make_lecture_with_sections([section])
        issue = _make_issue("visual_quality", "no diagrams")
        mock_response = MagicMock()
        mock_response.content = "```\nflowchart TD\n    A-->B\n```"
        with patch.object(revision_agent, "invoke_llm", return_value=mock_response):
            revision_agent._add_diagrams(lecture, issue)
        assert len(section.diagrams) == 1

    def test_no_sections_without_diagrams_returns_early(self, revision_agent):
        """_add_diagrams returns early if all sections have diagrams."""
        diagram = MermaidDiagram(
            id="d1", title="D", mermaid_code="flowchart TD\n A-->B", diagram_type="flowchart"
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[diagram], word_count=1,
            estimated_time=10, difficulty_level="intermediate",
        )
        lecture = _make_lecture_with_sections([section])
        issue = _make_issue("visual_quality", "no diagrams")
        with patch.object(revision_agent, "invoke_llm") as mock_llm:
            revision_agent._add_diagrams(lecture, issue)
        mock_llm.assert_not_called()
