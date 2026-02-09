"""
Smoke tests for ContentAnalyzerAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent


@pytest.fixture
def content_analyzer(test_env_vars, mock_llm):
    """Create ContentAnalyzerAgent instance."""
    return ContentAnalyzerAgent()


def test_content_analyzer_initialization(content_analyzer):
    """Test that ContentAnalyzerAgent initializes correctly."""
    assert content_analyzer is not None
    assert content_analyzer.agent_name == "ContentAnalyzerAgent"


def test_analyze_content(content_analyzer, sample_text_content, mock_llm):
    """Test content analysis with mocked LLM."""
    with patch.object(content_analyzer, "llm") as mock_llm_instance:
        # Mock LLM response with JSON analysis
        mock_response = MagicMock()
        mock_response.content = """{
  "topic": "Machine Learning",
  "entities": [
    {
      "name": "supervised learning",
      "type": "concept",
      "importance": 0.9,
      "description": "Learning from labeled data"
    }
  ],
  "topic_clusters": [
    {
      "name": "Fundamentals",
      "topics": ["ML basics", "Types of ML"],
      "importance": 0.9,
      "estimated_time": 30
    }
  ],
  "key_concepts": ["Machine learning", "Supervised learning"],
  "prerequisite_knowledge": ["Basic programming"],
  "difficulty_indicators": {
    "technical_depth": 0.6,
    "math_complexity": 0.5,
    "abstraction_level": 0.7
  }
}"""
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350}
        }
        mock_llm_instance.invoke.return_value = mock_response

        # Test analysis
        collection_result = {"documents": [{"text": sample_text_content}], "metadata": {"total_chunks": 1}}
        result = content_analyzer.analyze(
            collection_result=collection_result,
            topic="Machine Learning",
        )

        assert result is not None
        assert hasattr(result, "key_topics") or isinstance(result, dict)


def test_analyze_handles_empty_content(content_analyzer, mock_llm):
    """Test analysis with empty content."""
    with patch.object(content_analyzer, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = """{
  "topic": "Unknown",
  "entities": [],
  "topic_clusters": [],
  "key_concepts": [],
  "prerequisite_knowledge": [],
  "difficulty_indicators": {}
}"""
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}}
        mock_llm_instance.invoke.return_value = mock_response

        collection_result = {"documents": [], "metadata": {"total_chunks": 0}}
        result = content_analyzer.analyze(collection_result=collection_result, topic="Test")

        assert result is not None
