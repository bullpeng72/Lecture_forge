"""
Unit tests for slides utility functions.
"""

from unittest.mock import MagicMock, patch

import pytest


def test_short_text_returns_as_is(test_env_vars):
    """Short text (<100 chars) is returned as a single-item list without calling LLM."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    short_text = "Short text."
    result = convert_to_bullet_points(short_text)
    assert result == [short_text]


def test_already_bulleted_returns_as_is(test_env_vars):
    """Text starting with bullet marker is returned without LLM call."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    bulleted = "• Already a bullet point"
    result = convert_to_bullet_points(bulleted)
    assert result == [bulleted]


def test_already_dash_bulleted(test_env_vars):
    """Text starting with dash is returned without LLM call."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    bulleted = "- Already a dash bullet"
    result = convert_to_bullet_points(bulleted)
    assert result == [bulleted]


def test_already_star_bulleted(test_env_vars):
    """Text starting with star is returned without LLM call."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    bulleted = "* Already starred"
    result = convert_to_bullet_points(bulleted)
    assert result == [bulleted]


def test_long_text_calls_llm(test_env_vars):
    """Long text (>100 chars) calls LLM to convert to bullet points."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    long_text = "Python is a high-level programming language. " * 5  # > 100 chars

    mock_response = MagicMock()
    mock_response.content = "• Python is easy to learn\n• It has clean syntax\n• Many libraries available"

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("lecture_forge.slides.utils.ChatOpenAI", return_value=mock_llm):
        result = convert_to_bullet_points(long_text)

    assert isinstance(result, list)
    assert len(result) >= 1
    # LLM was called
    mock_llm.invoke.assert_called_once()


def test_llm_returns_numbered_list(test_env_vars):
    """Numbered list output is stripped of numbers."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    long_text = "Python is a high-level programming language. " * 5

    mock_response = MagicMock()
    mock_response.content = "1. Python is easy\n2. It has clean syntax\n3. Great libraries"

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("lecture_forge.slides.utils.ChatOpenAI", return_value=mock_llm):
        result = convert_to_bullet_points(long_text)

    assert isinstance(result, list)
    # Numbers should be stripped
    assert all(not item.startswith(("1.", "2.", "3.")) for item in result)


def test_llm_error_falls_back_to_sentences(test_env_vars):
    """When LLM raises exception, fallback splits by sentences."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    long_text = (
        "Python is easy to learn. It has great syntax. "
        "Many libraries are available. The community is huge. "
        "It is used everywhere in the industry."
    )

    with patch("lecture_forge.slides.utils.ChatOpenAI", side_effect=Exception("API error")):
        result = convert_to_bullet_points(long_text)

    assert isinstance(result, list)
    assert len(result) >= 1
    # Should return non-empty sentences
    assert all(len(item) > 10 for item in result)


def test_llm_returns_empty_falls_back_to_original(test_env_vars):
    """When LLM returns all very short lines, falls back to original text."""
    from lecture_forge.slides.utils import convert_to_bullet_points

    long_text = "Python is a high-level programming language. " * 5

    mock_response = MagicMock()
    mock_response.content = "ok\nyes\nno"  # All < 5 chars (filtered out)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("lecture_forge.slides.utils.ChatOpenAI", return_value=mock_llm):
        result = convert_to_bullet_points(long_text)

    # Falls back to [original text]
    assert result == [long_text]
