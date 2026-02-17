"""
Unit tests for ContentExpander.
"""

from unittest.mock import MagicMock

import pytest

from lecture_forge.agents.content_writer.content_expander import ContentExpander
from lecture_forge.models.curriculum import Curriculum, Section


@pytest.fixture
def sample_section():
    """Sample Section for testing."""
    return Section(
        id="sec_1",
        title="Python Basics",
        estimated_time=20,
        difficulty_level="beginner",
        topics=["Variables", "Functions", "Loops"],
        learning_outcomes=["Understand Python basics"],
    )


@pytest.fixture
def sample_curriculum():
    """Sample Curriculum for testing."""
    return Curriculum(
        topic="Python Programming",
        duration=60,
        audience_level="beginner",
        learning_objectives=["Learn Python"],
        sections=[],
    )


@pytest.fixture
def expander(test_env_vars, mock_llm):
    """ContentExpander with mocked LLM (via BaseAgent)."""
    return ContentExpander()


def test_initialization(expander):
    """ContentExpander initializes via BaseAgent."""
    assert expander.llm is not None  # BaseAgent creates the LLM
    assert expander.vector_store is None


def test_initialization_defaults(test_env_vars, mock_llm):
    """ContentExpander initializes without arguments."""
    exp = ContentExpander()
    assert exp.vector_store is None


def test_count_images_none(expander):
    """count_images returns 0 when no images in markdown."""
    markdown = "# Title\n\nSome text without images."
    assert expander.count_images(markdown) == 0


def test_count_images_single(expander):
    """count_images returns 1 for a single image."""
    markdown = "# Title\n\n![alt text](image.png)\n\nSome text."
    assert expander.count_images(markdown) == 1


def test_count_images_multiple(expander):
    """count_images counts all markdown images."""
    markdown = (
        "# Title\n\n"
        "![img1](a.png)\n"
        "Some text.\n"
        "![img2](b.jpg)\n"
        "More text.\n"
        "![img3](c.webp)\n"
    )
    assert expander.count_images(markdown) == 3


def test_count_images_partial_syntax(expander):
    """count_images ignores incomplete image syntax."""
    markdown = "# Title\n\n[not an image](link.html)\n\nPlain text."
    assert expander.count_images(markdown) == 0


def test_count_images_private_method(expander):
    """_count_images is equivalent to count_images."""
    markdown = "![one](a.png) ![two](b.png)"
    assert expander._count_images(markdown) == expander.count_images(markdown)


def test_expand_content_calls_invoke_llm(expander, sample_section, sample_curriculum):
    """expand_content calls invoke_llm on the expander instance."""
    mock_invoke_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "# Long expanded content\n\n" + "Word " * 200
    mock_invoke_llm.return_value = mock_response

    # Patch invoke_llm (provided by BaseAgent) with a mock
    expander.invoke_llm = mock_invoke_llm

    targets = {
        "min_words": 100,
        "target_words": 200,
        "max_words": 400,
        "min_code_examples": 1,
        "min_subsections": 2,
    }
    previous_quality = {
        "word_count": 50,
        "code_block_count": 0,
        "subsection_count": 0,
        "overall_score": 40,
    }

    result = expander.expand_content(
        section=sample_section,
        curriculum=sample_curriculum,
        contexts=["Some context text here."],
        targets=targets,
        previous_content="Short content.",
        previous_quality=previous_quality,
    )

    mock_invoke_llm.assert_called_once()
    assert isinstance(result, str)


def test_expand_content_returns_original_on_no_expansion(expander, sample_section, sample_curriculum):
    """expand_content returns original content when expansion is shorter."""
    original = "Short content. " * 20

    mock_invoke_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Short."  # shorter than original
    mock_invoke_llm.return_value = mock_response

    expander.invoke_llm = mock_invoke_llm

    targets = {
        "min_words": 100,
        "target_words": 200,
        "max_words": 400,
        "min_code_examples": 0,
        "min_subsections": 0,
    }
    previous_quality = {
        "word_count": len(original.split()),
        "code_block_count": 0,
        "subsection_count": 0,
        "overall_score": 60,
    }

    result = expander.expand_content(
        section=sample_section,
        curriculum=sample_curriculum,
        contexts=[],
        targets=targets,
        previous_content=original,
        previous_quality=previous_quality,
    )

    assert result == original


def test_expand_content_returns_original_on_error(expander, sample_section, sample_curriculum):
    """expand_content returns original content when invoke_llm raises an exception."""
    original = "Original content."

    mock_invoke_llm = MagicMock(side_effect=Exception("LLM error"))
    expander.invoke_llm = mock_invoke_llm

    targets = {
        "min_words": 100,
        "target_words": 200,
        "max_words": 400,
        "min_code_examples": 1,
        "min_subsections": 2,
    }
    previous_quality = {
        "word_count": 5,
        "code_block_count": 0,
        "subsection_count": 0,
        "overall_score": 30,
    }

    result = expander.expand_content(
        section=sample_section,
        curriculum=sample_curriculum,
        contexts=[],
        targets=targets,
        previous_content=original,
        previous_quality=previous_quality,
    )

    assert result == original


def test_expand_content_success_returns_expanded(expander, sample_section, sample_curriculum):
    """Lines 123-129: expand_content succeeds and returns expanded content."""
    from unittest.mock import patch as mpatch
    previous_content = "Short."  # 6 chars
    expanded_content = "# Much longer expanded content with many words.\n\n" + "Word " * 300  # ~1500 chars

    mock_invoke_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = expanded_content
    mock_invoke_llm.return_value = mock_response
    expander.invoke_llm = mock_invoke_llm

    targets = {
        "min_words": 50,
        "target_words": 200,
        "max_words": 400,
        "min_code_examples": 0,
        "min_subsections": 0,
    }
    previous_quality = {
        "word_count": 1,
        "code_block_count": 0,
        "subsection_count": 0,
        "overall_score": 10,
    }

    mock_quality = {"word_count": 200, "overall_score": 80, "meets_requirements": True}
    with mpatch("lecture_forge.agents.content_writer.content_expander.load_prompt", return_value="Expansion prompt"):
        with mpatch("lecture_forge.agents.content_writer.content_expander.evaluate_content_quality", return_value=mock_quality):
            result = expander.expand_content(
                section=sample_section,
                curriculum=sample_curriculum,
                contexts=[],
                targets=targets,
                previous_content=previous_content,
                previous_quality=previous_quality,
            )

    # Should return the expanded content (not original)
    assert result != previous_content
    assert len(result) > len(previous_content)
