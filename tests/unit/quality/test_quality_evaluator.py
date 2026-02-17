"""
Unit tests for QualityEvaluator.
"""

import pytest

from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import CodeBlock, Lecture, SectionContent
from lecture_forge.quality.evaluator import QualityEvaluator


def make_section(section_id="section_1", title="Test Section", word_count=500, code_blocks=None):
    return SectionContent(
        section_id=section_id,
        title=title,
        markdown_content="Content " * word_count,
        word_count=word_count,
        code_blocks=code_blocks or [],
    )


def make_passing_lecture():
    """Create a lecture that should score >= 80."""
    code_block = CodeBlock(language="python", code="def hello():\n    print('hello')\n    return True\n", caption=None)
    intro = make_section("intro_1", "Introduction", word_count=2000, code_blocks=[code_block])
    main1 = make_section("main_1", "Core Concepts", word_count=2000, code_blocks=[code_block])
    main2 = make_section("main_2", "Advanced Topics", word_count=2000, code_blocks=[code_block])
    conclusion = make_section("conclusion_1", "Summary", word_count=1500, code_blocks=[code_block])

    return Lecture(
        title="Comprehensive Python Course",
        topic="Python",
        duration=60,
        audience_level="intermediate",
        learning_objectives=["Learn Python", "Write clean code", "Use libraries"],
        sections=[intro, main1, main2, conclusion],
        total_word_count=7500,
        total_images=3,
        total_diagrams=3,
    )


def make_failing_lecture():
    """Create a lecture that should score < 80."""
    return Lecture(
        title="Incomplete Course",
        topic="Nothing",
        duration=120,
        audience_level="intermediate",
        learning_objectives=[],
        sections=[],
        total_word_count=0,
        total_images=0,
        total_diagrams=0,
    )


@pytest.fixture
def evaluator():
    return QualityEvaluator()


class TestEvaluate:
    def test_returns_evaluation_result(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture)
        assert isinstance(result, EvaluationResult)

    def test_result_has_correct_structure(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture)

        assert hasattr(result, "overall_score")
        assert hasattr(result, "passed")
        assert hasattr(result, "dimension_scores")
        assert hasattr(result, "issues")
        assert hasattr(result, "revision_strategy")

    def test_failing_lecture_does_not_pass(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture, threshold=80)
        assert result.passed is False

    def test_failing_lecture_has_low_score(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture)
        assert result.overall_score < 80

    def test_dimension_scores_all_present(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture)

        expected_dimensions = {
            "content_completeness",
            "logical_flow",
            "time_alignment",
            "level_appropriateness",
            "visual_quality",
            "technical_accuracy",
        }
        assert set(result.dimension_scores.keys()) == expected_dimensions

    def test_overall_score_in_range(self, evaluator):
        lecture = make_failing_lecture()
        result = evaluator.evaluate(lecture)
        assert 0 <= result.overall_score <= 100

    def test_custom_threshold(self, evaluator):
        lecture = make_failing_lecture()
        # With threshold=0, everything should pass
        result = evaluator.evaluate(lecture, threshold=0)
        assert result.passed is True

    def test_weights_sum_correctly(self, evaluator):
        """Test that WEIGHTS sum to 1.0."""
        total = sum(evaluator.WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9


class TestIdentifyIssues:
    def test_empty_lecture_generates_issues(self, evaluator):
        lecture = make_failing_lecture()
        dimension_scores = {
            "content_completeness": 0.0,
            "logical_flow": 0.0,
            "time_alignment": 0.0,
            "level_appropriateness": 0.0,
            "visual_quality": 0.0,
            "technical_accuracy": 0.0,
        }
        issues = evaluator._identify_issues(dimension_scores, lecture)
        assert len(issues) > 0

    def test_perfect_scores_generate_no_issues(self, evaluator):
        lecture = make_failing_lecture()
        dimension_scores = {
            "content_completeness": 100.0,
            "logical_flow": 100.0,
            "time_alignment": 100.0,
            "level_appropriateness": 100.0,
            "visual_quality": 100.0,
            "technical_accuracy": 100.0,
        }
        issues = evaluator._identify_issues(dimension_scores, lecture)
        assert len(issues) == 0

    def test_score_below_60_creates_high_severity_issue(self, evaluator):
        lecture = make_failing_lecture()
        dimension_scores = {
            "content_completeness": 50.0,
            "logical_flow": 100.0,
            "time_alignment": 100.0,
            "level_appropriateness": 100.0,
            "visual_quality": 100.0,
            "technical_accuracy": 100.0,
        }
        issues = evaluator._identify_issues(dimension_scores, lecture)
        assert len(issues) == 1
        # content_completeness at 50 should be high severity (due to no code)
        assert any(i.severity == "high" for i in issues)

    def test_issues_are_issue_objects(self, evaluator):
        lecture = make_failing_lecture()
        dimension_scores = {k: 55.0 for k in evaluator.WEIGHTS}
        issues = evaluator._identify_issues(dimension_scores, lecture)
        for issue in issues:
            assert isinstance(issue, Issue)


class TestDetermineStrategy:
    def test_score_above_80_returns_none(self, evaluator):
        strategy = evaluator._determine_strategy(85.0, [])
        assert strategy == "none"

    def test_score_80_returns_none(self, evaluator):
        strategy = evaluator._determine_strategy(80.0, [])
        assert strategy == "none"

    def test_score_70_to_80_few_issues_returns_auto(self, evaluator):
        issues = [Issue(dimension="logical_flow", severity="low", location="overall", description="x", suggestion="y")]
        strategy = evaluator._determine_strategy(75.0, issues)
        assert strategy == "auto"

    def test_score_60_to_70_returns_consult(self, evaluator):
        strategy = evaluator._determine_strategy(65.0, [])
        assert strategy == "consult"

    def test_score_below_60_returns_major(self, evaluator):
        strategy = evaluator._determine_strategy(50.0, [])
        assert strategy == "major"
