"""
Smoke tests for HTMLAssemblerAgent.
"""

from unittest.mock import MagicMock

import pytest

from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
from lecture_forge.models.lecture import Lecture, SectionContent


@pytest.fixture
def html_assembler(test_env_vars):
    """Create HTMLAssemblerAgent instance."""
    return HTMLAssemblerAgent()


@pytest.fixture
def sample_lecture():
    """Create sample lecture for testing."""
    section = SectionContent(
        section_id="sec_1",
        title="Test Section",
        markdown_content="# Test\n\nThis is test content.",
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


def test_html_assembler_initialization(html_assembler):
    """Test that HTMLAssemblerAgent initializes correctly."""
    assert html_assembler is not None
    assert html_assembler.agent_name == "HTMLAssemblerAgent"


def test_assemble_html(html_assembler, sample_lecture):
    """Test HTML assembly."""
    html_output = html_assembler.assemble(
        lecture=sample_lecture,
        output_path="test_output.html",
    )

    assert html_output is not None
    assert isinstance(html_output, str)
    assert len(html_output) > 0
    assert "<html>" in html_output or "<!DOCTYPE" in html_output
