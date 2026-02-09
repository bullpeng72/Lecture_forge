"""
Smoke tests for CurriculumDesignerAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.models.analysis import AnalysisResult, Entity, TopicCluster


@pytest.fixture
def sample_analysis():
    """Create sample analysis result for testing."""
    return AnalysisResult(
        entities=[
            Entity(
                name="supervised learning",
                type="concept",
                description="Learning from labeled data",
            ),
            Entity(
                name="neural networks",
                type="concept",
                description="Brain-inspired computing model",
            ),
            Entity(
                name="classification",
                type="technique",
                description="Categorizing data into classes",
            ),
        ],
        key_topics=[
            "Machine learning basics",
            "Supervised learning",
            "Neural networks",
        ],
        topic_clusters=[
            TopicCluster(
                id="cluster_1",
                name="Fundamentals",
                concepts=["What is ML?", "Types of ML"],
                difficulty="beginner",
                estimated_time=30,
            ),
            TopicCluster(
                id="cluster_2",
                name="Supervised Learning",
                concepts=["Classification", "Regression"],
                difficulty="intermediate",
                estimated_time=40,
            ),
        ],
        difficulty_scores={
            "Machine learning basics": 0.3,
            "Supervised learning": 0.6,
            "Neural networks": 0.8,
        },
        metadata={
            "topic": "Machine Learning",
            "prerequisite_knowledge": ["Basic programming", "Statistics"],
        },
    )


@pytest.fixture
def curriculum_designer(test_env_vars, mock_llm):
    """Create a CurriculumDesignerAgent instance."""
    return CurriculumDesignerAgent()


def test_curriculum_designer_initialization(curriculum_designer):
    """Test that CurriculumDesignerAgent initializes correctly."""
    assert curriculum_designer is not None
    assert curriculum_designer.agent_name == "CurriculumDesignerAgent"


def test_design_curriculum_basic(curriculum_designer, sample_analysis, mock_llm):
    """Test basic curriculum design with mocked LLM."""
    with patch.object(curriculum_designer, "llm") as mock_llm_instance:
        # Mock LLM response with structured curriculum JSON
        mock_response = MagicMock()
        mock_response.content = """{
  "topic": "Machine Learning",
  "duration_minutes": 120,
  "difficulty": "beginner",
  "target_audience": "Computer Science students",
  "learning_objectives": [
    "Understand ML fundamentals",
    "Learn supervised learning basics"
  ],
  "sections": [
    {
      "id": "sec_1",
      "title": "Introduction to Machine Learning",
      "estimated_time": 30,
      "difficulty_level": "beginner",
      "key_points": ["What is ML?", "Types of ML"],
      "subsections": []
    },
    {
      "id": "sec_2",
      "title": "Supervised Learning",
      "estimated_time": 40,
      "difficulty_level": "beginner",
      "key_points": ["Classification", "Regression"],
      "subsections": []
    }
  ]
}"""
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 150, "completion_tokens": 200, "total_tokens": 350}
        }
        mock_llm_instance.invoke.return_value = mock_response

        # Test curriculum design
        curriculum = curriculum_designer.design(
            analysis_result=sample_analysis,
            topic="Machine Learning",
            duration=120,
            audience_level="beginner",
        )

        # Assertions
        assert curriculum is not None
        assert curriculum.topic == "Machine Learning"
        assert curriculum.duration == 120
        assert len(curriculum.sections) >= 1
        assert len(curriculum.learning_objectives) >= 1


def test_design_respects_duration(curriculum_designer, sample_analysis, mock_llm):
    """Test that curriculum design respects the specified duration."""
    with patch.object(curriculum_designer, "llm") as mock_llm_instance:
        # Mock response for 60-minute lecture
        mock_response = MagicMock()
        mock_response.content = """{
  "topic": "Machine Learning Intro",
  "duration_minutes": 60,
  "difficulty": "beginner",
  "target_audience": "Beginners",
  "learning_objectives": ["Understand ML basics"],
  "sections": [
    {
      "id": "sec_1",
      "title": "ML Fundamentals",
      "estimated_time": 60,
      "difficulty_level": "beginner",
      "key_points": ["What is ML?"],
      "subsections": []
    }
  ]
}"""
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}
        }
        mock_llm_instance.invoke.return_value = mock_response

        # Test with shorter duration
        curriculum = curriculum_designer.design(
            analysis_result=sample_analysis,
            topic="Machine Learning",
            duration=60,
            audience_level="beginner",
        )

        # Check duration
        assert curriculum.duration == 60
        total_section_time = sum(s.estimated_time for s in curriculum.sections)
        # Allow some tolerance (within 20% of target)
        assert abs(total_section_time - 60) <= 60 * 0.2


def test_design_different_difficulty_levels(curriculum_designer, sample_analysis, mock_llm):
    """Test curriculum design with different difficulty levels."""
    with patch.object(curriculum_designer, "llm") as mock_llm_instance:
        # Mock response for advanced level
        mock_response = MagicMock()
        mock_response.content = """{
  "topic": "Advanced Machine Learning",
  "duration_minutes": 180,
  "difficulty": "advanced",
  "target_audience": "ML Engineers",
  "learning_objectives": ["Master advanced ML techniques"],
  "sections": [
    {
      "id": "sec_1",
      "title": "Deep Learning Architecture",
      "estimated_time": 90,
      "difficulty_level": "advanced",
      "key_points": ["CNN", "RNN", "Transformers"],
      "subsections": []
    }
  ]
}"""
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 150, "completion_tokens": 150, "total_tokens": 300}
        }
        mock_llm_instance.invoke.return_value = mock_response

        # Test with advanced difficulty
        curriculum = curriculum_designer.design(
            analysis_result=sample_analysis,
            topic="Machine Learning",
            duration=180,
            audience_level="advanced",
        )

        # Assertions
        assert curriculum is not None
        assert curriculum.audience_level == "advanced"
