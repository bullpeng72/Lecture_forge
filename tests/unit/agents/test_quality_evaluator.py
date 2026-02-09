"""
Smoke tests for QualityEvaluatorAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.quality_evaluator import QualityEvaluatorAgent
from lecture_forge.models.lecture import Lecture, SectionContent


@pytest.fixture
def quality_evaluator(test_env_vars, mock_llm):
    """Create QualityEvaluatorAgent instance."""
    return QualityEvaluatorAgent()


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
        duration_minutes=60,
        difficulty="beginner",
        target_audience="Students",
        learning_objectives=["Learn testing"],
        sections=[section],
    )


def test_quality_evaluator_initialization(quality_evaluator):
    """Test that QualityEvaluatorAgent initializes correctly."""
    assert quality_evaluator is not None
    assert quality_evaluator.agent_name == "QualityEvaluatorAgent"


def test_evaluate_lecture(quality_evaluator, sample_lecture, mock_llm):
    """Test lecture quality evaluation."""
    with patch.object(quality_evaluator, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = """{
  "overall_score": 85,
  "passed": true,
  "dimension_scores": {
    "content_completeness": 85,
    "logical_flow": 80,
    "time_alignment": 90,
    "level_appropriateness": 85,
    "visual_quality": 75,
    "technical_accuracy": 90
  },
  "issues": [],
  "revision_strategy": "minor_refinements"
}"""
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 300, "completion_tokens": 100, "total_tokens": 400}
        }
        mock_llm_instance.invoke.return_value = mock_response

        result = quality_evaluator.evaluate(lecture=sample_lecture)

        assert result is not None
