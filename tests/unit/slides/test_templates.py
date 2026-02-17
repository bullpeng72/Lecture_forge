"""
Unit tests for RevealJsTemplate.
"""

import pytest

from lecture_forge.slides.templates import RevealJsTemplate


@pytest.fixture
def template():
    """Create a RevealJsTemplate instance."""
    return RevealJsTemplate()


@pytest.fixture
def sample_sections():
    """Sample sections for slide generation."""
    return [
        {
            "title": "Introduction",
            "blocks": [
                {"type": "paragraph", "content": "Python is a great language."},
                {"type": "list", "items": ["Easy to learn", "Readable", "Versatile"], "ordered": False},
            ],
        },
        {
            "title": "Control Flow",
            "blocks": [
                {"type": "code", "content": 'if x > 0:\n    print("positive")', "language": "python"},
            ],
        },
    ]


def test_template_initialization(template):
    """RevealJsTemplate initializes with max_items_per_slide."""
    assert template.max_items_per_slide > 0
    assert template.max_bullet_points > 0


def test_generate_returns_string(template, sample_sections):
    """generate() returns a non-empty HTML string."""
    result = template.generate("Test Lecture", "Beginner", sample_sections)

    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_contains_reveal_js(template, sample_sections):
    """generate() produces valid Reveal.js HTML structure."""
    result = template.generate("Test Lecture", "Beginner", sample_sections)

    assert "reveal.js" in result.lower() or "reveal" in result
    assert "<html" in result
    assert "</html>" in result


def test_generate_contains_title(template, sample_sections):
    """generate() includes the lecture title in the output."""
    result = template.generate("My Lecture Title", "Advanced", sample_sections)

    assert "My Lecture Title" in result


def test_generate_contains_subtitle(template, sample_sections):
    """generate() includes subtitle when provided."""
    result = template.generate("Title", "My Subtitle", sample_sections)

    assert "My Subtitle" in result


def test_generate_no_subtitle(template, sample_sections):
    """generate() works when subtitle is empty."""
    result = template.generate("Title", "", sample_sections)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_contains_sections(template, sample_sections):
    """generate() includes section titles in the output."""
    result = template.generate("Title", "Subtitle", sample_sections)

    assert "Introduction" in result
    assert "Control Flow" in result


def test_generate_empty_sections(template):
    """generate() handles empty sections list."""
    result = template.generate("Title", "Subtitle", [])

    assert isinstance(result, str)
    assert "Title" in result


def test_create_title_slide(template):
    """_create_title_slide returns HTML with title and subtitle."""
    slide_html = template._create_title_slide("My Talk", "A subtitle")

    assert "My Talk" in slide_html
    assert "A subtitle" in slide_html
    assert "<section" in slide_html


def test_create_title_slide_no_subtitle(template):
    """_create_title_slide works when subtitle is empty."""
    slide_html = template._create_title_slide("My Talk", "")

    assert "My Talk" in slide_html
    assert "<section" in slide_html


def test_create_section_title_slide(template):
    """_create_section_title_slide returns HTML with section title."""
    slide_html = template._create_section_title_slide("Python Basics")

    assert "Python Basics" in slide_html
    assert "<section" in slide_html


def test_generate_code_block(template):
    """generate() includes code content from code blocks."""
    sections = [
        {
            "title": "Code Section",
            "blocks": [
                {"type": "code", "content": "def hello():\n    pass", "language": "python"},
            ],
        }
    ]
    result = template.generate("Title", "", sections)

    assert "def hello()" in result or "hello" in result


def test_generate_list_block(template):
    """generate() includes list items from list blocks."""
    sections = [
        {
            "title": "List Section",
            "blocks": [
                {"type": "list", "items": ["Alpha", "Beta", "Gamma"], "ordered": False},
            ],
        }
    ]
    result = template.generate("Title", "", sections)

    assert "Alpha" in result
    assert "Beta" in result
    assert "Gamma" in result


# ===== _create_content_slides() — branch coverage =====

class TestCreateContentSlidesBlockTypes:
    """Direct tests for _create_content_slides() covering all block type branches."""

    @pytest.fixture
    def t(self, test_env_vars):
        return RevealJsTemplate()

    def test_subsection_creates_title_slide(self, t):
        """subsection block → dedicated h2 title slide."""
        blocks = [{"type": "subsection", "content": "My Subsection"}]
        slides = t._create_content_slides(blocks)
        assert any("My Subsection" in s for s in slides)
        assert any("h2" in s for s in slides)

    def test_subsection_flushes_existing_content(self, t):
        """subsection after paragraph → paragraph slide + title slide."""
        blocks = [
            {"type": "paragraph", "content": "Intro text"},
            {"type": "subsection", "content": "New Section"},
        ]
        slides = t._create_content_slides(blocks)
        # Should have at least 2 slides: one for paragraph, one for subsection
        assert len(slides) >= 2
        full = "".join(slides)
        assert "Intro text" in full
        assert "New Section" in full

    def test_subsubsection_adds_h3_title(self, t):
        """subsubsection block → adds h3 to slide content."""
        blocks = [{"type": "subsubsection", "content": "Sub Title"}]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "Sub Title" in full

    def test_subsubsection_flushes_existing(self, t):
        """subsubsection after paragraph → flush paragraph first, then h3."""
        blocks = [
            {"type": "paragraph", "content": "First para"},
            {"type": "subsubsection", "content": "Sub"},
            # Need a subsequent block to force flush of subsubsection content
            {"type": "code", "content": "x=1", "language": "python"},
        ]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "First para" in full
        assert "Sub" in full

    def test_paragraph_adds_to_slide(self, t):
        """paragraph block appends <p> to current slide content."""
        blocks = [{"type": "paragraph", "content": "Hello world"}]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "Hello world" in full

    def test_code_block_creates_code_slide(self, t):
        """code block → calls _create_code_slide."""
        blocks = [{"type": "code", "content": "def hello():\n    pass", "language": "python"}]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "def hello()" in full

    def test_code_block_flushes_existing_content(self, t):
        """code block after paragraph → paragraph slide then code slide."""
        blocks = [
            {"type": "paragraph", "content": "Before code"},
            {"type": "code", "content": "x = 1", "language": "python"},
        ]
        slides = t._create_content_slides(blocks)
        assert len(slides) >= 2
        full = "".join(slides)
        assert "Before code" in full
        assert "x = 1" in full

    def test_image_block_creates_image_slide(self, t):
        """image block → calls _create_image_slide."""
        blocks = [{"type": "image", "src": "/img/test.jpg", "alt": "Test img", "caption": "A caption"}]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "test.jpg" in full or "Test img" in full

    def test_image_block_flushes_existing_content(self, t):
        """image block after paragraph → flush paragraph first."""
        blocks = [
            {"type": "paragraph", "content": "Before image"},
            {"type": "image", "src": "/img/test.jpg", "alt": "Alt text"},
        ]
        slides = t._create_content_slides(blocks)
        assert len(slides) >= 2
        full = "".join(slides)
        assert "Before image" in full

    def test_diagram_block_creates_diagram_slide(self, t):
        """diagram block → calls _create_diagram_slide."""
        blocks = [{"type": "diagram", "content": "graph TD\n  A-->B"}]
        slides = t._create_content_slides(blocks)
        assert len(slides) >= 1

    def test_diagram_block_flushes_existing_content(self, t):
        """diagram block after paragraph → flush paragraph first."""
        blocks = [
            {"type": "paragraph", "content": "Before diagram"},
            {"type": "diagram", "content": "graph TD\n  A-->B"},
        ]
        slides = t._create_content_slides(blocks)
        assert len(slides) >= 2
        full = "".join(slides)
        assert "Before diagram" in full

    def test_long_list_block_returns_multiple_slides(self, t):
        """list with > max_bullet_points items → multiple slides returned."""
        items = [f"Item {i}" for i in range(8)]  # 8 > max_bullet_points=5
        blocks = [{"type": "list", "items": items, "ordered": False}]
        slides = t._create_content_slides(blocks)
        # Should get multiple slides for the split list
        assert len(slides) >= 2

    def test_long_list_flushes_existing_content(self, t):
        """long list after paragraph → flush paragraph before list slides."""
        items = [f"Item {i}" for i in range(7)]  # 7 > 5
        blocks = [
            {"type": "paragraph", "content": "Before list"},
            {"type": "list", "items": items, "ordered": False},
        ]
        slides = t._create_content_slides(blocks)
        full = "".join(slides)
        assert "Before list" in full

    def test_short_list_added_to_current_slide(self, t):
        """list with <= max_bullet_points items → added inline, no split."""
        items = ["A", "B", "C"]  # 3 <= 5
        blocks = [{"type": "list", "items": items, "ordered": False}]
        slides = t._create_content_slides(blocks)
        # Short list should end up in a final slide (if any content remains)
        full = "".join(slides)
        assert "A" in full

    def test_empty_blocks_returns_empty_list(self, t):
        """No blocks → empty slides list."""
        slides = t._create_content_slides([])
        assert slides == []
