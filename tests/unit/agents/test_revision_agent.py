"""
Smoke tests for RevisionAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.revision_agent import RevisionAgent
from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import Lecture, SectionContent


@pytest.fixture
def revision_agent(test_env_vars, mock_llm):
    """Create RevisionAgent instance."""
    return RevisionAgent()


@pytest.fixture
def sample_lecture():
    """Create sample lecture."""
    section = SectionContent(
        section_id="sec_1",
        title="Test Section",
        markdown_content="# Test",
        code_blocks=[],
        images=[],
        diagrams=[],
        word_count=10,
        estimated_time=5,
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


@pytest.fixture
def sample_evaluation():
    """Create sample evaluation result."""
    issue = Issue(
        category="content_completeness",
        severity="medium",
        description="Section needs more examples",
        suggestion="Add 2-3 code examples",
    )

    return EvaluationResult(
        overall_score=75,
        passed=False,
        dimension_scores={
            "content_completeness": 70,
            "logical_flow": 80,
            "time_alignment": 75,
            "level_appropriateness": 75,
            "visual_quality": 70,
            "technical_accuracy": 80,
        },
        issues=[issue],
        revision_strategy="targeted_improvements",
    )


def test_revision_agent_initialization(revision_agent):
    """Test that RevisionAgent initializes correctly."""
    assert revision_agent is not None
    assert revision_agent.agent_name == "RevisionAgent"


def test_revise_lecture(revision_agent, sample_lecture, sample_evaluation, mock_llm):
    """Test lecture revision."""
    with patch.object(revision_agent, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = "Revised content with improvements."
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
        }
        mock_llm_instance.invoke.return_value = mock_response

        revised_lecture = revision_agent.revise(
            lecture=sample_lecture,
            evaluation=sample_evaluation,
        )

        assert revised_lecture is not None
