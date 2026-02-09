"""
Smoke tests for HTMLAssemblerAgent.
"""

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
        duration=60,
        audience_level="beginner",
        learning_objectives=["Learn testing"],
        sections=[section],
    )


def test_html_assembler_initialization(html_assembler):
    """Test that HTMLAssemblerAgent initializes correctly."""
    assert html_assembler is not None
    assert html_assembler.agent_name == "HTMLAssemblerAgent"


def test_assemble_html(html_assembler, sample_lecture, temp_dir):
    """Test HTML assembly."""
    output_path = str(temp_dir / "test_output.html")
    result_path = html_assembler.assemble(
        lecture=sample_lecture,
        output_path=output_path,
    )

    # Should return file path
    assert result_path is not None
    assert isinstance(result_path, str)
    assert result_path == output_path

    # File should exist and contain HTML
    import os

    assert os.path.exists(result_path)
    with open(result_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        assert len(html_content) > 0
        assert "<html>" in html_content or "<!DOCTYPE" in html_content
