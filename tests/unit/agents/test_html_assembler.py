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


# ===== Additional coverage tests =====

from lecture_forge.models.lecture import ImageReference


class TestAssembleOutputPaths:
    """Tests covering output_path branching in assemble()."""

    @pytest.fixture
    def lecture_no_images(self):
        section = SectionContent(
            section_id="s1",
            title="Section",
            markdown_content="Some content.",
            images=[],
        )
        return Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[section],
        )

    def test_assemble_with_none_output_path_auto_generates_name(
        self, html_assembler, lecture_no_images, tmp_path
    ):
        """output_path=None → auto-generates timestamp-based filename in OUTPUT_DIR."""
        import os
        from lecture_forge.config import Config
        original = Config.OUTPUT_DIR
        try:
            Config.OUTPUT_DIR = tmp_path
            result = html_assembler.assemble(lecture=lecture_no_images, output_path=None)
        finally:
            Config.OUTPUT_DIR = original
        assert result is not None
        assert result.endswith(".html")
        assert os.path.exists(result)

    def test_assemble_with_filename_only(self, html_assembler, lecture_no_images, tmp_path):
        """output_path='name.html' (no dir) → written to OUTPUT_DIR."""
        import os
        from lecture_forge.config import Config
        original = Config.OUTPUT_DIR
        try:
            Config.OUTPUT_DIR = tmp_path
            result = html_assembler.assemble(
                lecture=lecture_no_images, output_path="my_lecture.html"
            )
        finally:
            Config.OUTPUT_DIR = original
        assert result is not None
        assert "my_lecture.html" in result
        assert os.path.exists(result)

    def test_assemble_filename_adds_html_extension(
        self, html_assembler, lecture_no_images, tmp_path
    ):
        """output_path without .html → .html extension is added."""
        import os
        from lecture_forge.config import Config
        original = Config.OUTPUT_DIR
        try:
            Config.OUTPUT_DIR = tmp_path
            result = html_assembler.assemble(
                lecture=lecture_no_images, output_path="no_extension"
            )
        finally:
            Config.OUTPUT_DIR = original
        assert result.endswith(".html")
        assert os.path.exists(result)


class TestValidateImages:
    """Tests covering _validate_images() branches."""

    def test_some_sections_without_images(self, html_assembler):
        """_validate_images() with some sections lacking images but total_images > 0."""
        img = ImageReference(image_id="i1", path="test.jpg", description="img")
        sec_with = SectionContent(
            section_id="s1", title="With", markdown_content="c", images=[img]
        )
        sec_without = SectionContent(
            section_id="s2", title="Without", markdown_content="c", images=[]
        )
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[sec_with, sec_without],
        )
        # Should not raise; logs warning for missing sections
        html_assembler._validate_images(lecture)

    def test_all_sections_have_images(self, html_assembler):
        """_validate_images() with all sections having images → logs success."""
        img = ImageReference(image_id="i1", path="test.jpg", description="img")
        section = SectionContent(
            section_id="s1", title="S", markdown_content="c", images=[img]
        )
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[section],
        )
        html_assembler._validate_images(lecture)  # Should log "All sections have images"

    def test_majority_sections_without_images(self, html_assembler):
        """_validate_images() with >50% sections missing images → logs extra warning."""
        img = ImageReference(image_id="i1", path="test.jpg", description="img")
        sec_with = SectionContent(
            section_id="s1", title="With", markdown_content="c", images=[img]
        )
        # 3 sections without images out of 4 = 75%
        secs_without = [
            SectionContent(section_id=f"s{i}", title=f"Without{i}", markdown_content="c", images=[])
            for i in range(2, 5)
        ]
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[sec_with] + secs_without,
        )
        html_assembler._validate_images(lecture)  # Should log "Consider..."


class TestCleanupContent:
    """Tests for _cleanup_content() HTML heading downgrading."""

    def test_downgrades_h1_tags(self, html_assembler):
        html = "<h1>Title</h1><p>content</p>"
        result = html_assembler._cleanup_content(html)
        assert "<h1>" not in result
        assert "Title" not in result  # h1 is decomposed

    def test_downgrades_h2_to_h4(self, html_assembler):
        """h2 is first converted to h3, then h3 to h4 → ends up as h4."""
        html = "<h2>Section</h2><p>content</p>"
        result = html_assembler._cleanup_content(html)
        assert "<h2>" not in result
        assert "<h4>" in result  # h2→h3→h4 in sequence
        assert "Section" in result

    def test_downgrades_h3_to_h4(self, html_assembler):
        html = "<h3>Sub</h3><p>content</p>"
        result = html_assembler._cleanup_content(html)
        assert "<h3>" not in result
        assert "<h4>" in result
        assert "Sub" in result


class TestGenerateObjectivesHtml:
    """Tests for _generate_objectives_html()."""

    def test_empty_list_returns_empty_string(self, html_assembler):
        result = html_assembler._generate_objectives_html([])
        assert result == ""

    def test_nonempty_list_returns_html(self, html_assembler):
        result = html_assembler._generate_objectives_html(["Obj 1", "Obj 2"])
        assert "Obj 1" in result
        assert "<li>" in result


class TestGenerateSectionHtmlImages:
    """Tests for _generate_section_html() covering image path branching."""

    def test_http_url_image_used_as_is(self, html_assembler):
        img = ImageReference(
            image_id="i1",
            path="https://example.com/photo.jpg",
            description="A URL image",
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.", images=[img]
        )
        result = html_assembler._generate_section_html(section, 1)
        assert "https://example.com/photo.jpg" in result

    def test_relative_path_with_dotdot_used_as_is(self, html_assembler):
        img = ImageReference(
            image_id="i2",
            path="../images/test.jpg",
            description="Relative img",
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.", images=[img]
        )
        result = html_assembler._generate_section_html(section, 1)
        assert "../images/test.jpg" in result

    def test_other_relative_path_gets_prefix(self, html_assembler):
        img = ImageReference(
            image_id="i3",
            path="images/test.jpg",
            description="Other relative",
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.", images=[img]
        )
        result = html_assembler._generate_section_html(section, 1)
        assert "images/test.jpg" in result

    def test_absolute_path_under_data_dir(self, html_assembler, tmp_path):
        """Absolute path under Config.DATA_DIR → computes relative path."""
        from lecture_forge.config import Config
        orig_data = Config.DATA_DIR
        orig_out = Config.OUTPUT_DIR
        try:
            Config.DATA_DIR = tmp_path / "data"
            Config.OUTPUT_DIR = tmp_path / "outputs"
            (tmp_path / "data" / "images").mkdir(parents=True)
            img_path = tmp_path / "data" / "images" / "test.jpg"
            img_path.write_bytes(b"fake")

            img = ImageReference(image_id="i4", path=str(img_path), description="abs")
            section = SectionContent(
                section_id="s1", title="S", markdown_content="c", images=[img]
            )
            result = html_assembler._generate_section_html(section, 1)
        finally:
            Config.DATA_DIR = orig_data
            Config.OUTPUT_DIR = orig_out
        assert "img" in result.lower() or "test.jpg" in result

    def test_absolute_path_outside_data_dir(self, html_assembler, tmp_path):
        """Absolute path NOT under DATA_DIR → uses str(img.path) directly."""
        img = ImageReference(
            image_id="i5",
            path="/usr/share/images/test.jpg",
            description="Outside",
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="c", images=[img]
        )
        result = html_assembler._generate_section_html(section, 1)
        assert "test.jpg" in result


class TestAssembleAbsolutePathNoExtension:
    """Tests covering line 77: absolute/relative path without .html gets .html added."""

    def test_path_with_dir_no_extension_gets_html_added(self, html_assembler, tmp_path):
        """output_path like 'dir/name' (no .html) → .html is appended."""
        import os
        output_path = str(tmp_path / "subdir" / "lecture_output")
        (tmp_path / "subdir").mkdir(parents=True, exist_ok=True)

        section = SectionContent(section_id="s1", title="S", markdown_content="Content.")
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[section],
        )
        result = html_assembler.assemble(lecture=lecture, output_path=output_path)
        assert result.endswith(".html")
        assert os.path.exists(result)


class TestValidateImagesNoImages:
    """Tests covering lines 124-136: validate_images with zero total_images."""

    def test_no_images_logs_error(self, html_assembler):
        """lecture.total_images == 0 → logs error messages."""
        section = SectionContent(
            section_id="s1", title="S", markdown_content="c", images=[]
        )
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[section], total_images=0,
        )
        # Should not raise
        html_assembler._validate_images(lecture)

    def test_few_sections_without_images_names_logged(self, html_assembler):
        """1-3 sections without images → names are logged."""
        img = ImageReference(image_id="i1", path="img.jpg", description="img")
        sec_with = SectionContent(
            section_id="s1", title="WithImg", markdown_content="c", images=[img]
        )
        sec_without1 = SectionContent(
            section_id="s2", title="NoImg1", markdown_content="c", images=[]
        )
        sec_without2 = SectionContent(
            section_id="s3", title="NoImg2", markdown_content="c", images=[]
        )
        lecture = Lecture(
            title="L", topic="T", duration=60, audience_level="beginner",
            learning_objectives=[], sections=[sec_with, sec_without1, sec_without2],
        )
        html_assembler._validate_images(lecture)  # Should log section names


class TestCleanupContentException:
    """Test _cleanup_content handles exception gracefully (lines 213-215)."""

    def test_exception_returns_original_html(self, html_assembler):
        from unittest.mock import patch
        bad_html = "<broken>content</broken>"
        with patch("lecture_forge.agents.html_assembler.BeautifulSoup", side_effect=Exception("parse error")):
            result = html_assembler._cleanup_content(bad_html)
        assert result == bad_html


class TestGenerateSectionHtmlWithDiagram:
    """Test _generate_section_html with diagrams (line 239)."""

    def test_section_with_diagram_renders_mermaid(self, html_assembler):
        from lecture_forge.models.lecture import MermaidDiagram
        diagram = MermaidDiagram(
            id="d1", title="Flow", mermaid_code="flowchart TD\n A-->B", diagram_type="flowchart"
        )
        section = SectionContent(
            section_id="s1", title="S", markdown_content="Content.",
            code_blocks=[], images=[], diagrams=[diagram], word_count=1,
            estimated_time=10, difficulty_level="intermediate",
        )
        result = html_assembler._generate_section_html(section, 1)
        assert "mermaid" in result
        assert "A-->B" in result
