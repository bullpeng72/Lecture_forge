"""
Smoke tests for DiagramGeneratorAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.models.lecture import SectionContent


@pytest.fixture
def diagram_generator(test_env_vars, mock_llm):
    """Create DiagramGeneratorAgent instance."""
    return DiagramGeneratorAgent()


@pytest.fixture
def sample_section_content():
    """Create sample section content for testing."""
    return SectionContent(
        section_id="sec_1",
        title="Machine Learning Pipeline",
        markdown_content="""
# Machine Learning Pipeline

The ML pipeline consists of several stages:
1. Data Collection
2. Data Preprocessing
3. Model Training
4. Model Evaluation
5. Deployment
        """,
        code_blocks=[],
        images=[],
        diagrams=[],
        word_count=50,
        estimated_time=20,
        difficulty_level="beginner",
    )


def test_diagram_generator_initialization(diagram_generator):
    """Test that DiagramGeneratorAgent initializes correctly."""
    assert diagram_generator is not None
    assert diagram_generator.agent_name == "DiagramGeneratorAgent"


def test_generate_diagrams(diagram_generator, sample_section_content, mock_llm):
    """Test diagram generation with mocked LLM."""
    with patch.object(diagram_generator, "llm") as mock_llm_instance:
        # Mock LLM response with Mermaid diagram
        mock_response = MagicMock()
        mock_response.content = """```mermaid
graph LR
    A[Data Collection] --> B[Data Preprocessing]
    B --> C[Model Training]
    C --> D[Model Evaluation]
    D --> E[Deployment]
```"""
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180}}
        mock_llm_instance.invoke.return_value = mock_response

        # Test diagram generation
        diagrams = diagram_generator.generate_diagrams(section_contents=[sample_section_content])

        assert diagrams is not None
        assert isinstance(diagrams, list)


def test_generate_with_no_diagrams_needed(diagram_generator, mock_llm):
    """Test when no diagrams are needed."""
    simple_content = SectionContent(
        section_id="sec_2",
        title="Simple Topic",
        markdown_content="This is simple text with no complex concepts.",
        code_blocks=[],
        images=[],
        diagrams=[],
        word_count=10,
        estimated_time=5,
        difficulty_level="beginner",
    )

    with patch.object(diagram_generator, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = "No diagrams needed."
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}
        mock_llm_instance.invoke.return_value = mock_response

        diagrams = diagram_generator.generate_diagrams(section_contents=[simple_content])

        assert diagrams is not None
