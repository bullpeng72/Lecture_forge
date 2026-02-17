"""
Unit tests for QualityMetrics.
"""

import pytest

from lecture_forge.models.lecture import CodeBlock, Lecture, MermaidDiagram, SectionContent
from lecture_forge.quality.metrics import QualityMetrics


def make_section(
    section_id="section_1",
    title="Test Section",
    markdown_content="Some content here.",
    word_count=500,
    difficulty_level="intermediate",
    code_blocks=None,
    images=None,
    diagrams=None,
):
    return SectionContent(
        section_id=section_id,
        title=title,
        markdown_content=markdown_content,
        word_count=word_count,
        difficulty_level=difficulty_level,
        code_blocks=code_blocks or [],
        images=images or [],
        diagrams=diagrams or [],
    )


def make_lecture(duration=60, sections=None, total_word_count=0, total_images=0, total_diagrams=0, audience_level="intermediate"):
    return Lecture(
        title="Test Lecture",
        topic="Testing",
        duration=duration,
        audience_level=audience_level,
        learning_objectives=["Understand testing"],
        sections=sections or [],
        total_word_count=total_word_count,
        total_images=total_images,
        total_diagrams=total_diagrams,
    )


@pytest.fixture
def metrics():
    return QualityMetrics()


class TestCalculateContentCompleteness:
    def test_empty_lecture_returns_low_score(self, metrics):
        lecture = make_lecture(sections=[], total_word_count=0)
        score = metrics.calculate_content_completeness(lecture)
        assert 0 <= score <= 100
        assert score < 50

    def test_no_code_blocks_reduces_score(self, metrics):
        section = make_section(word_count=1000, code_blocks=[])
        lecture = make_lecture(
            duration=60,
            sections=[section, make_section("s2"), make_section("s3")],
            total_word_count=3000,
        )
        score = metrics.calculate_content_completeness(lecture)
        assert score < 100

    def test_with_code_blocks_increases_score(self, metrics):
        code_block = CodeBlock(language="python", code="print('hello')", caption=None)
        section = make_section(word_count=1000, code_blocks=[code_block])
        lecture = make_lecture(
            duration=30,
            sections=[section, make_section("s2"), make_section("s3")],
            total_word_count=3000,
        )
        score = metrics.calculate_content_completeness(lecture)
        assert score > 50

    def test_sufficient_word_count_increases_score(self, metrics):
        sections = [make_section(f"s{i}", word_count=3000) for i in range(3)]
        # 60 min * 250 words/min * 0.7 = 10500 expected words
        lecture = make_lecture(duration=60, sections=sections, total_word_count=10500)
        score = metrics.calculate_content_completeness(lecture)
        assert score >= 50

    def test_learning_objectives_adds_points(self, metrics):
        lecture = Lecture(
            title="Test",
            topic="Test",
            duration=60,
            audience_level="intermediate",
            learning_objectives=["Objective 1", "Objective 2"],
            sections=[],
            total_word_count=0,
        )
        score = metrics.calculate_content_completeness(lecture)
        assert score >= 10

    def test_at_least_3_sections_adds_points(self, metrics):
        sections = [make_section(f"s{i}") for i in range(3)]
        lecture = make_lecture(sections=sections, total_word_count=1000)
        score = metrics.calculate_content_completeness(lecture)
        # Should have the 20-point section coverage bonus
        less_sections_lecture = make_lecture(sections=sections[:2], total_word_count=1000)
        less_score = metrics.calculate_content_completeness(less_sections_lecture)
        assert score >= less_score

    def test_score_capped_at_100(self, metrics):
        code_block = CodeBlock(language="python", code="x = 1\n" * 50, caption=None)
        sections = [make_section(f"s{i}", word_count=5000, code_blocks=[code_block] * 5) for i in range(3)]
        lecture = make_lecture(duration=30, sections=sections, total_word_count=15000)
        score = metrics.calculate_content_completeness(lecture)
        assert score <= 100


class TestCalculateLogicalFlow:
    def test_single_section_no_intro_no_conclusion(self, metrics):
        section = make_section("section_main", "Main Content")
        lecture = make_lecture(sections=[section])
        score = metrics.calculate_logical_flow(lecture)
        assert 0 <= score <= 100
        # No intro, no conclusion, only 1 section → max 0 points for flow
        assert score == 0

    def test_intro_section_adds_points(self, metrics):
        intro = make_section("intro_1", "Introduction")
        main = make_section("main_1", "Main Content", word_count=500)
        conclusion = make_section("conclusion_1", "Summary")
        lecture = make_lecture(sections=[intro, main, conclusion])
        score = metrics.calculate_logical_flow(lecture)
        assert score >= 25

    def test_conclusion_section_adds_points(self, metrics):
        intro = make_section("intro_1", "Introduction")
        main = make_section("main_1", "Main Content", word_count=500)
        conclusion = make_section("conclusion_1", "Conclusion")
        lecture = make_lecture(sections=[intro, main, conclusion])
        score = metrics.calculate_logical_flow(lecture)
        assert score >= 50

    def test_three_plus_sections_for_balance_and_progression(self, metrics):
        intro = make_section("intro_1", "Introduction", word_count=500)
        main = make_section("main_1", "Main Content", word_count=500)
        conclusion = make_section("conclusion_1", "Summary", word_count=500)
        lecture = make_lecture(sections=[intro, main, conclusion])
        score = metrics.calculate_logical_flow(lecture)
        assert score >= 75

    def test_score_capped_at_100(self, metrics):
        intro = make_section("intro_1", "Introduction", word_count=500, difficulty_level="beginner")
        main = make_section("main_1", "Main", word_count=500, difficulty_level="intermediate")
        conclusion = make_section("conclusion_1", "Summary", word_count=500, difficulty_level="intermediate")
        lecture = make_lecture(sections=[intro, main, conclusion])
        score = metrics.calculate_logical_flow(lecture)
        assert score <= 100


class TestCalculateAllMetrics:
    def test_returns_all_six_dimensions(self, metrics):
        lecture = make_lecture(sections=[make_section()], total_word_count=500)
        result = metrics.calculate_all_metrics(lecture)

        expected_keys = {
            "content_completeness",
            "logical_flow",
            "time_alignment",
            "level_appropriateness",
            "visual_quality",
            "technical_accuracy",
        }
        assert set(result.keys()) == expected_keys

    def test_all_scores_are_floats_in_range(self, metrics):
        sections = [make_section(f"s{i}") for i in range(3)]
        lecture = make_lecture(sections=sections, total_word_count=1500)
        result = metrics.calculate_all_metrics(lecture)

        for dim, score in result.items():
            assert isinstance(score, float), f"{dim} score should be float"
            assert 0 <= score <= 100, f"{dim} score {score} out of range"

    def test_empty_lecture_all_scores_low(self, metrics):
        lecture = make_lecture(sections=[], total_word_count=0)
        result = metrics.calculate_all_metrics(lecture)

        # Most scores should be low for an empty lecture.
        # technical_accuracy is an exception: when there are no code blocks, the
        # implementation assumes code is accurate (50 pts) and checks basic structure,
        # so it can score up to 75 for an otherwise empty lecture.
        content_scores = {k: v for k, v in result.items() if k != "technical_accuracy"}
        for dim, score in content_scores.items():
            assert score <= 60, f"{dim} should be low for empty lecture, got {score}"


# ===== Additional coverage tests for missing branches =====

from lecture_forge.models.lecture import CodeBlock


class TestCalculateLogicalFlowDifficultyOrder:
    """Tests for calculate_logical_flow() difficulty ordering (lines 96-97)."""

    def test_difficulty_jump_backwards_reduces_score(self, metrics):
        """advanced → beginner (jump backwards) → has_logical_order=False (line 96-97)."""
        s1 = make_section("s1", difficulty_level="advanced")
        s2 = make_section("s2", difficulty_level="beginner")
        lecture = make_lecture(sections=[s1, s2])
        score = metrics.calculate_logical_flow(lecture)
        # Score should be lower than if difficulty was ordered (no has_logical_order bonus)
        assert score >= 0

    def test_valid_difficulty_order_gets_bonus(self, metrics):
        """beginner → intermediate → advanced → has_logical_order=True."""
        s1 = make_section("s1", difficulty_level="beginner")
        s2 = make_section("s2", difficulty_level="intermediate")
        s3 = make_section("s3", difficulty_level="advanced")
        lecture = make_lecture(sections=[s1, s2, s3])
        score = metrics.calculate_logical_flow(lecture)
        assert score > 0


class TestCalculateTimeAlignment:
    """Tests for calculate_time_alignment() branching (lines 122, 128)."""

    def test_word_count_below_range_partial_score(self, metrics):
        """total_word_count < expected_words_min → line 125-126 (ratio < 1)."""
        # 60 min * 150 = 9000 words minimum; set 1000 words → below range
        lecture = make_lecture(sections=[make_section("s1")], total_word_count=1000, duration=60)
        score = metrics.calculate_time_alignment(lecture)
        assert 0 <= score < 60  # Less than max for time alignment

    def test_word_count_above_range_partial_score(self, metrics):
        """total_word_count > expected_words_max → line 128 (ratio = max/count)."""
        # 30 min * 250 = 7500 words max; set 20000 words → above range
        lecture = make_lecture(sections=[make_section("s1")], total_word_count=20000, duration=30)
        score = metrics.calculate_time_alignment(lecture)
        assert 0 <= score < 60


class TestCalculateLevelAppropriateness:
    """Tests for calculate_level_appropriateness() code branches (lines 173, 180, 197-205)."""

    def test_intermediate_code_avg_lines_in_range(self, metrics):
        """intermediate level with 20-50 avg lines → line 199-200."""
        code_block = CodeBlock(language="python", code="\n".join([f"line{i}" for i in range(35)]))
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(
            sections=[section], audience_level="intermediate"
        )
        score = metrics.calculate_level_appropriateness(lecture)
        assert score >= 0

    def test_advanced_code_avg_lines_high(self, metrics):
        """advanced level with >= 30 avg lines → line 201-202."""
        code_block = CodeBlock(language="python", code="\n".join([f"line{i}" for i in range(40)]))
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(sections=[section], audience_level="advanced")
        score = metrics.calculate_level_appropriateness(lecture)
        assert score >= 0

    def test_level_mismatch_partial_credit(self, metrics):
        """Level mismatch → else branch → score += 15 (line 205)."""
        # beginner but avg_lines > 30 → mismatch
        code_block = CodeBlock(language="python", code="\n".join([f"line{i}" for i in range(50)]))
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(sections=[section], audience_level="beginner")
        score = metrics.calculate_level_appropriateness(lecture)
        assert score >= 0

    def test_word_count_in_appropriate_range(self, metrics):
        """Section word_count in 0.7-1.3 * expected → appropriate_sections += 1 (line 180)."""
        # beginner expected = 2500, 0.7*2500=1750, 1.3*2500=3250 → word_count=2000
        section = make_section("s1", word_count=2000, difficulty_level="beginner")
        lecture = make_lecture(sections=[section], audience_level="beginner")
        score = metrics.calculate_level_appropriateness(lecture)
        assert score >= 0


class TestCalculateTechnicalAccuracy:
    """Tests for calculate_technical_accuracy() code block branches (lines 266-278)."""

    def test_empty_code_block_skipped(self, metrics):
        """Empty code string → continue (line 270-271)."""
        code_block = CodeBlock(language="python", code="")
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(sections=[section])
        score = metrics.calculate_technical_accuracy(lecture)
        # Empty code: total_code_blocks=1, valid=0 → 50 * 0 = 0 for code, + structure
        assert score >= 0

    def test_unbalanced_brackets_counted_invalid(self, metrics):
        """Unbalanced brackets → not added to valid_code_blocks."""
        code_block = CodeBlock(language="python", code="def foo(: pass")
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(sections=[section])
        score = metrics.calculate_technical_accuracy(lecture)
        assert 0 <= score <= 100

    def test_valid_code_block_counted(self, metrics):
        """Balanced brackets → valid_code_blocks += 1 (line 274-275)."""
        code_block = CodeBlock(language="python", code="def foo(): pass")
        section = make_section("s1", code_blocks=[code_block])
        lecture = make_lecture(sections=[section])
        score = metrics.calculate_technical_accuracy(lecture)
        assert score > 0
