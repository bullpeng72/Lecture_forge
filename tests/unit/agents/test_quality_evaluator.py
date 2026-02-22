"""
Smoke tests for QualityEvaluator.
"""

import pytest

from lecture_forge.quality.evaluator import QualityEvaluator
from lecture_forge.models.lecture import Lecture, SectionContent


@pytest.fixture
def quality_evaluator(test_env_vars, mock_llm):
    """Create QualityEvaluator instance."""
    return QualityEvaluator()


@pytest.fixture
def sample_lecture():
    """Create sample lecture for testing."""
    section = SectionContent(
        section_id="sec_1",
        title="Test Section",
        markdown_content="# Test Content\n\nDetailed content here.",
        code_blocks=[],
        images=[],
        diagrams=[],
        word_count=50,
        estimated_time=10,
        difficulty_level="beginner",
    )

    return Lecture(
        title="Test Lecture",
        topic="Testing",
        duration=60,
        audience_level="beginner",
        learning_objectives=["Learn testing"],
        sections=[section],
    )


def test_quality_evaluator_initialization(quality_evaluator):
    """Test that QualityEvaluator initializes correctly."""
    assert quality_evaluator is not None


def test_evaluate_lecture(quality_evaluator, sample_lecture):
    """Test lecture quality evaluation returns a valid result."""
    result = quality_evaluator.evaluate(lecture=sample_lecture)

    assert result is not None
    assert hasattr(result, "overall_score")
    assert 0 <= result.overall_score <= 100
