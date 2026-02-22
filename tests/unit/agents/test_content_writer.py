"""
Smoke tests for ContentWriterAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.models.curriculum import Curriculum, Section


@pytest.fixture
def sample_curriculum():
    """Create a sample curriculum for testing."""
    section1 = Section(
        id="sec_1",
        title="Introduction to Machine Learning",
        estimated_time=20,
        difficulty_level="beginner",
        topics=["What is ML?", "Types of ML", "Applications"],
        learning_outcomes=["Understand ML basics"],
    )

    section2 = Section(
        id="sec_2",
        title="Supervised Learning Basics",
        estimated_time=30,
        difficulty_level="beginner",
        topics=["Classification", "Regression", "Training"],
        learning_outcomes=["Understand supervised learning"],
    )

    return Curriculum(
        topic="Machine Learning",
        duration=120,
        audience_level="beginner",
        learning_objectives=[
            "Understand ML fundamentals",
            "Learn supervised learning concepts",
        ],
        sections=[section1, section2],
    )


@pytest.fixture
def content_writer(test_env_vars, mock_vector_store, mock_llm):
    """Create a ContentWriterAgent instance with mocked dependencies."""
    agent = ContentWriterAgent(vector_store=mock_vector_store)
    return agent


def test_content_writer_initialization(content_writer):
    """Test that ContentWriterAgent initializes correctly."""
    assert content_writer is not None
    assert content_writer.agent_name == "ContentWriterAgent"
    assert content_writer.vector_store is not None


def test_write_section_basic(content_writer, sample_curriculum, mock_llm):
    """Test writing a single section with mocked LLM."""
    with patch.object(content_writer, "llm") as mock_llm_instance:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = """
# Introduction to Machine Learning

Machine learning is a field of artificial intelligence that enables computers to learn from data.

## What is Machine Learning?

ML algorithms improve automatically through experience.

## Types of Machine Learning

1. **Supervised Learning**: Learn from labeled data
2. **Unsupervised Learning**: Find patterns in unlabeled data
3. **Reinforcement Learning**: Learn through rewards

```python
# Example code
def train_model(data):
    model = LinearRegression()
    model.fit(data)
    return model
```
"""
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 200,
                "completion_tokens": 150,
                "total_tokens": 350,
            }
        }
        mock_llm_instance.invoke.return_value = mock_response

        # Test section writing
        section = sample_curriculum.sections[0]
        content = content_writer.write_section(
            section=section,
            curriculum=sample_curriculum,
            available_images=[],
        )

        # Assertions
        assert content is not None
        assert content.section_id == section.id
        assert content.title == section.title
        assert len(content.markdown_content) > 0
        assert content.word_count > 0


def test_write_section_with_images(content_writer, sample_curriculum, sample_images, mock_llm):
    """Test writing section with image selection."""
    with patch.object(content_writer, "llm") as mock_llm_instance:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "# Section content with images\n\nThis is sample content."
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        mock_llm_instance.invoke.return_value = mock_response

        # Test section writing with images
        section = sample_curriculum.sections[0]
        content = content_writer.write_section(
            section=section,
            curriculum=sample_curriculum,
            available_images=sample_images,
        )

        # Assertions
        assert content is not None
        assert len(content.markdown_content) > 0


def test_write_all_sections(content_writer, sample_curriculum, mock_llm):
    """Test writing all sections in a curriculum."""
    with patch.object(content_writer, "llm") as mock_llm_instance:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "# Section content\n\nThis is auto-generated content."
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        mock_llm_instance.invoke.return_value = mock_response

        # Test writing all sections
        section_contents = content_writer.write_all_sections(
            curriculum=sample_curriculum,
            available_images=[],
        )

        # Assertions
        assert len(section_contents) == len(sample_curriculum.sections)
        for content in section_contents:
            assert content.word_count > 0
            assert len(content.markdown_content) > 0


def test_extract_code_blocks():
    """Test code block extraction from markdown."""
    from lecture_forge.agents.content_writer.code_generator import extract_code_blocks
    markdown_with_code = """
# Title

Some text here.

```python
def hello():
    print("Hello, World!")
```

More text.

```javascript
console.log("Hello");
```
"""
    code_blocks = extract_code_blocks(markdown_with_code)

    # Assertions
    assert len(code_blocks) == 2
    assert code_blocks[0].language == "python"
    assert "hello" in code_blocks[0].code.lower()
    assert code_blocks[1].language == "javascript"


def test_backward_compat_import(test_env_vars, mock_llm):
    """Lines 15, 17 of agents/content_writer.py: backward compat wrapper imports ContentWriterAgent."""
    from lecture_forge.agents.content_writer import ContentWriterAgent
    assert ContentWriterAgent is not None
