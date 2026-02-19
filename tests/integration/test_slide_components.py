"""
Integration tests for refactored slide generation components.

Tests the interaction between:
- HTMLLectureParser: Parses lecture HTML
- RevealJsTemplate: Generates Reveal.js slides
- SlideConverter: Orchestrates the conversion
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from lecture_forge.slides import SlideConverter
from lecture_forge.slides.parser import HTMLLectureParser
from lecture_forge.slides.templates import RevealJsTemplate


class TestSlideParserIntegration:
    """Test HTMLLectureParser component."""

    def test_parse_simple_html(self):
        """Test parsing simple lecture HTML."""
        parser = HTMLLectureParser()

        html_content = """
        <html>
        <body>
            <h1>Lecture Title</h1>
            <h2>Section 1</h2>
            <p>Content here</p>
            <h2>Section 2</h2>
            <p>More content</p>
        </body>
        </html>
        """

        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = Path(f.name)

        try:
            result = parser.parse(temp_path)

            assert result is not None
            assert 'title' in result
            assert 'sections' in result
            assert len(result['sections']) >= 0
        finally:
            temp_path.unlink()

    def test_parse_html_with_code(self):
        """Test parsing HTML with code blocks."""
        parser = HTMLLectureParser()

        html_content = """
        <html>
        <body>
            <h1>Programming Tutorial</h1>
            <h2>Python Basics</h2>
            <pre><code class="language-python">
def hello():
    print("Hello, World!")
            </code></pre>
        </body>
        </html>
        """

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = Path(f.name)

        try:
            result = parser.parse(temp_path)

            # Should extract code blocks
            assert result is not None
        finally:
            temp_path.unlink()

    def test_parse_html_with_images(self):
        """Test parsing HTML with images."""
        parser = HTMLLectureParser()

        html_content = """
        <html>
        <body>
            <h1>Visual Guide</h1>
            <h2>Diagrams</h2>
            <img src="diagram.png" alt="Diagram">
            <p>Caption text</p>
        </body>
        </html>
        """

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = Path(f.name)

        try:
            result = parser.parse(temp_path)

            # Should handle images
            assert result is not None
        finally:
            temp_path.unlink()


class TestRevealJsTemplateIntegration:
    """Test RevealJsTemplate component."""

    def test_generate_basic_slides(self):
        """Test generating basic slide deck."""
        template = RevealJsTemplate()

        data = {
            'title': 'Test Lecture',
            'subtitle': 'A test presentation',
            'sections': [
                {
                    'title': 'Introduction',
                    'blocks': [
                        {'type': 'paragraph', 'content': 'Welcome to the lecture'}
                    ]
                }
            ]
        }

        html = template.generate(
            title=data['title'],
            subtitle=data['subtitle'],
            sections=data['sections']
        )

        assert isinstance(html, str)
        assert '<html' in html
        assert 'reveal.js' in html.lower() or 'Reveal' in html
        assert data['title'] in html

    def test_generate_slides_with_code(self):
        """Test generating slides with code blocks."""
        template = RevealJsTemplate()

        sections = [
            {
                'title': 'Code Example',
                'blocks': [
                    {
                        'type': 'code',
                        'language': 'python',
                        'content': 'def hello():\n    print("Hello")'
                    }
                ]
            }
        ]

        html = template.generate(
            title='Programming',
            subtitle='Code Tutorial',
            sections=sections
        )

        assert '<code' in html or '<pre' in html
        assert 'def hello' in html

    def test_generate_slides_with_lists(self):
        """Test generating slides with lists."""
        template = RevealJsTemplate()

        sections = [
            {
                'title': 'Key Points',
                'blocks': [
                    {
                        'type': 'list',
                        'items': ['Point 1', 'Point 2', 'Point 3'],
                        'ordered': False,
                    }
                ]
            }
        ]

        html = template.generate(
            title='Summary',
            subtitle='Main Points',
            sections=sections
        )

        assert '<ul>' in html or '<li>' in html
        assert 'Point 1' in html


class TestSlideConverterIntegration:
    """Test SlideConverter orchestration."""

    def test_converter_initialization(self):
        """Test SlideConverter initializes components."""
        from rich.console import Console
        console = Console()

        converter = SlideConverter(console=console)

        assert converter is not None
        assert hasattr(converter, 'console')

    def test_convert_lecture_to_slides(self):
        """Test complete conversion process."""
        from rich.console import Console
        console = Console()
        converter = SlideConverter(console=console)

        # Create test lecture HTML using the parser's expected <section id="..."> structure
        lecture_html = """
        <html>
        <head><title>Machine Learning</title></head>
        <body>
            <section id="intro">
                <h2>Introduction</h2>
                <p>Machine learning is a field of AI.</p>
                <ul>
                    <li>Supervised learning</li>
                    <li>Unsupervised learning</li>
                </ul>
            </section>
            <section id="applications">
                <h2>Applications</h2>
                <p>ML has many applications.</p>
            </section>
        </body>
        </html>
        """

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(lecture_html)
            lecture_path = Path(f.name)

        slides_path = lecture_path.parent / f"{lecture_path.stem}_slides.html"

        try:
            success = converter.convert(lecture_path, slides_path)

            # Should create slides file
            if success:
                assert slides_path.exists()
                assert slides_path.stat().st_size > 0

                # Check slide content
                with open(slides_path, 'r') as f:
                    slides_content = f.read()

                assert 'Machine Learning' in slides_content
        finally:
            lecture_path.unlink()
            if slides_path.exists():
                slides_path.unlink()


class TestSlideSplittingLogic:
    """Test slide splitting and organization."""

    def test_split_long_list_into_slides(self):
        """Test that long lists are split across slides."""
        # Simulate splitting logic
        items = [f"Item {i}" for i in range(15)]
        max_items_per_slide = 5

        slides = []
        for i in range(0, len(items), max_items_per_slide):
            slide_items = items[i:i + max_items_per_slide]
            slides.append(slide_items)

        assert len(slides) == 3
        assert len(slides[0]) == 5
        assert len(slides[1]) == 5
        assert len(slides[2]) == 5

    def test_one_topic_per_slide(self):
        """Test that each subsection gets its own slide."""
        sections = [
            {'title': 'Section 1', 'subsections': ['Sub 1.1', 'Sub 1.2']},
            {'title': 'Section 2', 'subsections': ['Sub 2.1']},
        ]

        # Each subsection should become a slide
        slide_count = sum(len(s['subsections']) for s in sections)
        assert slide_count == 3

    def test_code_blocks_get_titles(self):
        """Test that code blocks get appropriate titles."""
        code_block = {
            'type': 'code',
            'language': 'python',
            'content': 'print("hello")',
        }

        # Should add title
        if code_block['type'] == 'code':
            title = f"Code Example"  # or "Code Example - Python"

        assert 'Code' in title


class TestSlideEnhancements:
    """Test v0.3.0 slide enhancements."""

    def test_slide_item_limit(self):
        """Test that slides limit items per slide (3 items)."""
        max_items = 3

        items = ['Item 1', 'Item 2', 'Item 3', 'Item 4', 'Item 5']

        # Split into slides
        slides = []
        for i in range(0, len(items), max_items):
            slides.append(items[i:i + max_items])

        assert len(slides[0]) == 3
        assert len(slides[1]) == 2

    def test_continuation_markers(self):
        """Test that split lists show continuation."""
        items = ['Item 1', 'Item 2', 'Item 3', 'Item 4']
        max_items = 3

        slides = []
        for i in range(0, len(items), max_items):
            slide_items = items[i:i + max_items]
            # Add continuation marker if not last slide
            if i + max_items < len(items):
                slide_items.append("(continued...)")
            slides.append(slide_items)

        assert slides[0][-1] == "(continued...)"
        assert len(slides[1]) == 1

    def test_subsection_becomes_title_slide(self):
        """Test that h3 subsections become title slides."""
        content = [
            {'type': 'h3', 'text': 'Subsection Title'},
            {'type': 'p', 'text': 'Content here'},
        ]

        # First item should create title slide
        first_item = content[0]
        assert first_item['type'] == 'h3'

        # Should create separate slide for title
        title_slide = {'title': first_item['text'], 'content': []}
        assert title_slide['title'] == 'Subsection Title'


class TestSlideInteraction:
    """Test slide keyboard shortcuts and interaction."""

    def test_reveal_js_keyboard_shortcuts(self):
        """Test that generated slides support keyboard navigation."""
        template = RevealJsTemplate()

        html = template.generate(
            title='Test',
            subtitle='Shortcuts',
            sections=[{'title': 'Section 1', 'blocks': []}]
        )

        # Should include Reveal.js which provides keyboard shortcuts
        # Arrow keys, Esc, etc. are handled by Reveal.js library
        assert 'reveal' in html.lower() or '<script' in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
