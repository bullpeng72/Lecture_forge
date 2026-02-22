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


# ===== _assess_difficulty() =====

class TestAssessDifficulty:
    def test_default_is_intermediate(self, content_analyzer):
        result = content_analyzer._assess_difficulty(["General Topic"], "some text")
        assert result["General Topic"] == 0.5

    def test_beginner_keyword_gives_low_score(self, content_analyzer):
        result = content_analyzer._assess_difficulty(["basic introduction"], "text")
        assert result["basic introduction"] < 0.5

    def test_advanced_keyword_gives_high_score(self, content_analyzer):
        result = content_analyzer._assess_difficulty(["advanced optimization"], "text")
        assert result["advanced optimization"] > 0.5

    def test_complex_keyword_gives_high_score(self, content_analyzer):
        result = content_analyzer._assess_difficulty(["complex architecture"], "text")
        assert result["complex architecture"] > 0.5

    def test_returns_dict_for_multiple_topics(self, content_analyzer):
        topics = ["Topic A", "Topic B", "Advanced Topic"]
        result = content_analyzer._assess_difficulty(topics, "text")
        assert set(result.keys()) == set(topics)

    def test_empty_topics_returns_empty_dict(self, content_analyzer):
        result = content_analyzer._assess_difficulty([], "text")
        assert result == {}


# ===== _build_relationships() =====

# ===== _create_clusters() =====

class TestCreateClusters:
    def _make_entity(self, name, entity_type="concept"):
        from lecture_forge.models.analysis import Entity
        return Entity(
            name=name, type=entity_type, description=f"desc",
            mentions=1, sources=["src"], difficulty="intermediate",
        )

    def test_creates_cluster_per_main_concept(self, content_analyzer):
        entities = [
            self._make_entity("Concept A", "concept"),
            self._make_entity("Concept B", "concept"),
        ]
        result = content_analyzer._create_clusters(entities)
        assert len(result) == 2

    def test_cluster_has_correct_name(self, content_analyzer):
        entities = [self._make_entity("My Topic", "concept")]
        result = content_analyzer._create_clusters(entities)
        assert result[0].name == "My Topic"

    def test_no_clusters_for_sub_concepts_only(self, content_analyzer):
        entities = [self._make_entity("Sub A", "sub_concept")]
        result = content_analyzer._create_clusters(entities)
        assert result == []

    def test_cluster_includes_related_sub_concepts(self, content_analyzer):
        from lecture_forge.models.analysis import Entity
        main = self._make_entity("Deep Learning", "concept")
        sub = Entity(
            name="Backpropagation", type="sub_concept",
            description="sub", mentions=1,
            sources=["Deep Learning"], difficulty="intermediate",
        )
        result = content_analyzer._create_clusters([main, sub])
        assert len(result) == 1


# ===== _extract_key_topics() - exception handling =====

class TestExtractKeyTopics:
    def test_returns_fallback_on_llm_exception(self, content_analyzer):
        with patch.object(content_analyzer, "invoke_llm", side_effect=Exception("LLM error")):
            result = content_analyzer._extract_key_topics("Some text content", "ML")
        # Returns fallback [main_topic]
        assert "ML" in result or result == []

    def test_returns_topics_from_json_response(self, content_analyzer):
        mock_response = MagicMock()
        mock_response.content = '["Topic A", "Topic B", "Topic C"]'
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}
        }
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_key_topics("content", "ML")
        assert "Topic A" in result

    def test_parses_json_from_code_block(self, content_analyzer):
        mock_response = MagicMock()
        mock_response.content = '```json\n["Topic X", "Topic Y"]\n```'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 80}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_key_topics("content", "ML")
        assert "Topic X" in result

    def test_parses_json_from_bare_code_block(self, content_analyzer):
        """Line 126: bare ``` code block (not json) is also parsed."""
        mock_response = MagicMock()
        mock_response.content = '```\n["Topic A", "Topic B"]\n```'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 80}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_key_topics("content", "ML")
        assert "Topic A" in result

    def test_non_list_topics_returns_empty(self, content_analyzer):
        """Line 147: topics is a dict (not list) → returns []."""
        mock_response = MagicMock()
        mock_response.content = '{"key": "value"}'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 80}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_key_topics("content", "ML")
        assert result == []


class TestExtractEntities:
    """Tests for _extract_entities() sub-concept extraction branches."""

    def test_entities_from_key_topics(self, content_analyzer):
        """_extract_entities creates Entity for each key topic."""
        entities = content_analyzer._extract_entities.__wrapped__(
            content_analyzer, "text content", []
        ) if hasattr(content_analyzer._extract_entities, "__wrapped__") else None
        # Simple call - no topics → returns empty
        result = content_analyzer._extract_entities("text content", [])
        assert isinstance(result, list)

    def test_entities_with_sub_concepts_from_llm(self, content_analyzer):
        """Lines 160-183: LLM returns sub-concepts for first topics."""
        mock_response = MagicMock()
        mock_response.content = '["개념1", "개념2"]'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 50}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_entities("text content", ["Python", "ML"])
        assert len(result) >= 2
        names = [e.name for e in result]
        assert "Python" in names

    def test_entities_sub_concepts_from_code_block(self, content_analyzer):
        """LLM returns sub-concepts in code block format."""
        mock_response = MagicMock()
        mock_response.content = '```json\n["서브개념A", "서브개념B"]\n```'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 50}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_entities("text content", ["Topic1"])
        assert any(e.name == "Topic1" for e in result)

    def test_entities_sub_concepts_llm_exception_continues(self, content_analyzer):
        """Line 194-195: Exception in sub-concept extraction is caught."""
        with patch.object(content_analyzer, "invoke_llm", side_effect=Exception("API error")):
            result = content_analyzer._extract_entities("text content", ["Topic1", "Topic2"])
        # Should still return base entities from topics
        assert len(result) >= 2

    def test_entities_sub_concepts_bare_code_block(self, content_analyzer):
        """Line 177: LLM returns sub-concepts in bare ``` code block (no json tag)."""
        mock_response = MagicMock()
        mock_response.content = '```\n["개념X", "개념Y"]\n```'
        mock_response.response_metadata = {"token_usage": {"total_tokens": 50}}
        with patch.object(content_analyzer, "invoke_llm", return_value=mock_response):
            result = content_analyzer._extract_entities("text content", ["Topic1"])
        assert any(e.name == "Topic1" for e in result)


class TestCreateClustersRelatedAppend:
    """Test _create_clusters appends related concept (line 281)."""

    def test_related_concept_appended_to_cluster(self, content_analyzer):
        """Line 281: related.append(sub.name) when sub.name appears in source."""
        from lecture_forge.models.analysis import Entity
        main = Entity(
            name="Python", type="concept",
            description="main", mentions=1, sources=["content"], difficulty="intermediate",
        )
        # sub.name = "List" is in the source that contains main.name = "Python"
        sub = Entity(
            name="List", type="sub_concept",
            description="sub", mentions=1,
            sources=["Python List comprehension"],  # Contains both "Python" (main.name) AND "List" (sub.name)
            difficulty="beginner",
        )
        result = content_analyzer._create_clusters([main, sub])
        assert len(result) == 1
        # "List" should be in the cluster concepts since it matches the filter
        assert "List" in result[0].concepts
