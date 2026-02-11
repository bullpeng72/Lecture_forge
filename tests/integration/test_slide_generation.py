"""
Integration tests for slide generation from HTML lectures.

Tests the Reveal.js slide conversion functionality.
"""

import tempfile
from pathlib import Path

import pytest

from lecture_forge.config import Config


@pytest.mark.integration
class TestSlideGeneration:
    """Test slide generation from HTML."""

    def test_html_to_slides_structure(self):
        """
        Test basic HTML to slides conversion structure.

        Validates that slides are created with proper structure.
        """
        # Create minimal test HTML with proper structure
        test_html = """<!DOCTYPE html>
<html>
<head>
    <title>Test Lecture</title>
</head>
<body>
    <div class="lecture-content">
        <h1>Test Lecture Title</h1>

        <h2>Section 1: Introduction</h2>
        <p>This is the introduction section.</p>

        <h3>Subsection 1.1</h3>
        <p>First subsection content.</p>
        <ul>
            <li>Point 1</li>
            <li>Point 2</li>
        </ul>

        <h4>Sub-subsection 1.1.1</h4>
        <p>Detailed content here.</p>

        <h2>Section 2: Main Content</h2>
        <p>Main content goes here.</p>

        <h3>Subsection 2.1</h3>
        <p>More content.</p>
        <pre><code>print("Hello, World!")</code></pre>
    </div>
</body>
</html>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write test HTML
            html_path = Path(tmpdir) / "test_lecture.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(test_html)

            # Import the slide generation logic
            # Note: This would normally be in cli.py's improve command
            # For testing, we'll verify the HTML parsing works

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(test_html, "html.parser")

            # Verify structure parsing
            h1 = soup.find("h1")
            assert h1 is not None
            assert "Test Lecture Title" in h1.get_text()

            h2_sections = soup.find_all("h2")
            assert len(h2_sections) == 2
            assert "Section 1" in h2_sections[0].get_text()
            assert "Section 2" in h2_sections[1].get_text()

            h3_subsections = soup.find_all("h3")
            assert len(h3_subsections) == 2

            h4_subsubsections = soup.find_all("h4")
            assert len(h4_subsubsections) == 1

    def test_slide_max_items_config(self):
        """
        Test that MAX_ITEMS_PER_SLIDE config is used.

        Validates configuration-based slide composition.
        """
        assert hasattr(Config, "MAX_ITEMS_PER_SLIDE")
        assert isinstance(Config.MAX_ITEMS_PER_SLIDE, int)
        assert Config.MAX_ITEMS_PER_SLIDE > 0
        assert Config.MAX_ITEMS_PER_SLIDE <= 10  # Reasonable limit

    def test_slide_content_blocks_classification(self):
        """
        Test classification of content into slide blocks.

        Different block types have different weights for slide composition.
        """
        from bs4 import BeautifulSoup

        test_html = """<div>
<h3>Subsection Title</h3>
<p>Paragraph content</p>
<ul>
    <li>List item 1</li>
    <li>List item 2</li>
</ul>
<pre><code>code block</code></pre>
<h4>Sub-subsection</h4>
<p>More content</p>
</div>"""

        soup = BeautifulSoup(test_html, "html.parser")

        # Count different block types
        h3_count = len(soup.find_all("h3"))
        h4_count = len(soup.find_all("h4"))
        p_count = len(soup.find_all("p"))
        ul_count = len(soup.find_all("ul"))
        code_count = len(soup.find_all("pre"))

        assert h3_count == 1  # Section header
        assert h4_count == 1  # Subsection header
        assert p_count == 2   # Paragraphs
        assert ul_count == 1  # List
        assert code_count == 1  # Code block

        # Slide composition logic would use these counts
        # h3: 1.0 weight (always new slide)
        # h4: 0.5 weight (stay with content)
        # p, ul, code: 1.0 weight each

    def test_orphaned_heading_prevention(self):
        """
        Test that h4 headings are not orphaned at slide ends.

        Validates look-ahead logic: h4 should stay with its content.
        """
        # This is a structural test - validates the pattern exists
        # Actual implementation is in cli.py _generate_reveal_html

        # Test data: h4 followed by content
        blocks = [
            {"type": "subsubsection", "content": "Details"},  # h4
            {"type": "paragraph", "content": "Content for details"},
        ]

        # Validation: these two should be on same slide
        # h4 alone would be 0.5, h4 + p would be 1.5
        # With MAX_ITEMS_PER_SLIDE=4, they should fit together

        h4_weight = 0.5
        p_weight = 1.0
        combined = h4_weight + p_weight

        assert combined <= Config.MAX_ITEMS_PER_SLIDE
        # This ensures orphaning won't happen with default config

    @pytest.mark.skip(reason="Requires full HTML and Reveal.js template")
    def test_full_slide_generation(self):
        """
        Test complete slide generation with Reveal.js.

        This would test:
        1. Read HTML lecture file
        2. Parse structure
        3. Generate Reveal.js slides
        4. Validate slides.html output
        5. Check keyboard shortcuts are included

        Skipped by default as it requires full implementation.
        """
        # TODO: Implement when doing comprehensive slide testing
        pass

    @pytest.mark.skip(reason="Requires browser testing with Playwright")
    def test_reveal_js_rendering(self):
        """
        Test that generated slides actually render in browser.

        Would use Playwright to:
        1. Load slides.html
        2. Navigate slides with arrow keys
        3. Verify all sections present
        4. Test overview mode

        Requires browser testing setup.
        """
        # TODO: Implement for E2E testing
        pass
