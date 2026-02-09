"""
HTML Assembler Agent - Generates final HTML output.
"""

from datetime import datetime
from pathlib import Path
from typing import List
import markdown
from bs4 import BeautifulSoup

from lecture_forge.agents.base import BaseAgent
from lecture_forge.models.lecture import Lecture, SectionContent
from lecture_forge.utils import logger


class HTMLAssemblerAgent(BaseAgent):
    """Agent for assembling final HTML output."""

    def __init__(self):
        super().__init__()
        logger.info("Initializing HTML Assembler Agent")

    def assemble(
        self,
        lecture: Lecture,
        output_path: str = None,
    ) -> str:
        """
        Assemble final HTML from lecture content.

        Args:
            lecture: Complete lecture data
            output_path: Path to save HTML file

        Returns:
            Path to generated HTML file
        """
        logger.info(f"Assembling HTML for lecture: {lecture.title}")

        # Validate image availability
        self._validate_images(lecture)

        # Generate HTML content
        html_content = self._generate_html(lecture)

        # Determine output path
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{lecture.topic.replace(' ', '_')}_{timestamp}.html"
            output_dir = Path("outputs")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / filename)

        # Write HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"✅ HTML generated: {output_path}")
        logger.info(f"   - Sections: {len(lecture.sections)}")
        logger.info(f"   - Words: {lecture.total_word_count}")
        logger.info(f"   - Images: {lecture.total_images}")
        logger.info(f"   - Diagrams: {lecture.total_diagrams}")

        return output_path

    def _validate_images(self, lecture: Lecture):
        """Validate image availability and log warnings."""
        total_sections = len(lecture.sections)
        sections_without_images = 0
        section_names_without_images = []

        for section in lecture.sections:
            if not section.images:
                sections_without_images += 1
                section_names_without_images.append(section.title)

        # Log warnings
        if lecture.total_images == 0:
            logger.error("❌ No images in lecture!")
            logger.error("   Possible causes:")
            logger.error("   1. Image search disabled (use --image-search)")
            logger.error("   2. PDF images disabled (use --include-pdf-images)")
            logger.error("   3. Image collection failed")
            logger.error("")
            logger.error("   Quick fix:")
            logger.error("   $ lecture-forge create --image-search")
        elif sections_without_images > 0:
            percentage = (sections_without_images / total_sections) * 100
            logger.warning(f"⚠️  {sections_without_images}/{total_sections} sections ({percentage:.1f}%) have no images")

            if sections_without_images <= 3:
                logger.warning(f"   Sections without images: {', '.join(section_names_without_images)}")

            if percentage > 50:
                logger.warning("   Consider:")
                logger.warning("   • Regenerate with --image-search")
                logger.warning("   • Enable PDF images with --include-pdf-images")
        else:
            logger.info(f"✅ All {total_sections} sections have images")

    def _generate_html(self, lecture: Lecture) -> str:
        """Generate complete HTML document."""
        # Convert sections to HTML
        sections_html = []

        for i, section in enumerate(lecture.sections):
            section_html = self._generate_section_html(section, i + 1)
            sections_html.append(section_html)

        # Generate TOC
        toc_html = self._generate_toc(lecture.sections)

        # Build complete HTML
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lecture.title}</title>

    <!-- TailwindCSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Mermaid.js -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>

    <!-- Prism.js for code highlighting -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>

    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #fafbfc;
        }}
        .sidebar {{
            position: fixed;
            top: 0;
            left: 0;
            width: 250px;
            height: 100vh;
            overflow-y: auto;
            background: #f8fafc;
            border-right: 1px solid #e2e8f0;
            padding: 2rem 1rem;
        }}
        .main-content {{
            margin-left: 250px;
            padding: 2rem 3rem;
            max-width: 900px;
        }}

        /* Section styling for better visual separation */
        .section {{
            margin-bottom: 4rem;
            background: white;
            padding: 2rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        /* Typography hierarchy */
        h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            color: #0f172a;
            margin: 2rem 0 1rem 0;
        }}

        h2 {{
            font-size: 1.75rem;
            font-weight: 600;
            color: #1e293b;
            margin: 1.5rem 0 1rem 0;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.5rem;
        }}

        .section h3 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #1e293b;
            margin-top: 2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e2e8f0;
        }}

        .section h4 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #475569;
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }}

        /* Paragraphs with better spacing */
        .section p {{
            line-height: 1.8;
            margin-bottom: 1rem;
            color: #334155;
        }}

        /* Lists with better readability */
        .section ul, .section ol {{
            margin: 1rem 0;
            padding-left: 1.5rem;
            line-height: 1.8;
        }}

        .section li {{
            margin-bottom: 0.5rem;
            color: #334155;
        }}

        /* Code blocks with improved styling */
        .section code {{
            background: #f1f5f9;
            padding: 0.2rem 0.4rem;
            border-radius: 0.25rem;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
            color: #e11d48;
        }}

        .section pre {{
            background: #1e293b;
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin: 1.5rem 0;
            overflow-x: auto;
        }}

        .section pre code {{
            background: transparent;
            padding: 0;
            color: #e2e8f0;
            font-size: 0.9em;
        }}

        /* Bold text emphasis */
        .section strong {{
            color: #0f172a;
            font-weight: 600;
        }}

        /* Diagrams with background */
        .mermaid {{
            background: #f8fafc;
            padding: 2rem;
            border-radius: 0.5rem;
            margin: 2rem 0;
            text-align: center;
        }}

        /* Images */
        img {{
            max-width: 100%;
            height: auto;
            margin: 1.5rem 0;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}

        /* TOC styling */
        .toc-link {{
            display: block;
            padding: 0.5rem 0;
            color: #64748b;
            text-decoration: none;
            transition: color 0.2s;
        }}
        .toc-link:hover {{
            color: #3b82f6;
        }}
    </style>
</head>
<body>
    <!-- Sidebar TOC -->
    <div class="sidebar">
        <h3 class="text-xl font-bold mb-4">{lecture.title}</h3>
        <div class="text-sm text-gray-600 mb-4">
            <div>⏱️ {lecture.duration} minutes</div>
            <div>👥 {lecture.audience_level.capitalize()}</div>
        </div>
        <nav class="toc">
            {toc_html}
        </nav>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        <h1>{lecture.title}</h1>

        <!-- Learning Objectives -->
        {self._generate_objectives_html(lecture.learning_objectives)}

        <!-- Sections -->
        {''.join(sections_html)}

        <footer class="mt-12 pt-6 border-t border-gray-200 text-sm text-gray-500">
            <p>Generated by LectureForge on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p>Total: {lecture.total_word_count} words | {lecture.total_images} images | {lecture.total_diagrams} diagrams</p>
        </footer>
    </div>

    <script>
        // Initialize Mermaid
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});

        // Smooth scrolling for TOC links
        document.querySelectorAll('.toc-link').forEach(link => {{
            link.addEventListener('click', (e) => {{
                e.preventDefault();
                const target = document.querySelector(e.target.getAttribute('href'));
                target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }});
        }});
    </script>
</body>
</html>"""

        return html

    def _generate_toc(self, sections: List[SectionContent]) -> str:
        """Generate table of contents HTML."""
        toc_items = []

        for section in sections:
            toc_items.append(f'<a href="#{section.section_id}" class="toc-link">{section.title}</a>')

        return "\n".join(toc_items)

    def _generate_objectives_html(self, objectives: List[str]) -> str:
        """Generate learning objectives HTML."""
        if not objectives:
            return ""

        items = "\n".join(f"<li>{obj}</li>" for obj in objectives)

        return f"""
        <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-8">
            <h3 class="text-lg font-semibold mb-2">🎯 Learning Objectives</h3>
            <ul class="list-disc list-inside space-y-1">
                {items}
            </ul>
        </div>"""

    def _cleanup_content(self, html_content: str) -> str:
        """
        Clean up HTML content to improve structure and readability.

        Removes:
        - Redundant h1 tags within content
        - Downgrades h2 -> h3, h3 -> h4 for proper hierarchy
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove all h1 tags (section already has title)
            for h1 in soup.find_all("h1"):
                h1.decompose()

            # Downgrade heading levels for proper hierarchy
            # h2 -> h3 (since section has h2 title)
            for h2 in soup.find_all("h2"):
                h2.name = "h3"

            # h3 -> h4
            for h3 in soup.find_all("h3"):
                h3.name = "h4"

            return str(soup)
        except Exception as e:
            logger.warning(f"Error cleaning up HTML: {e}")
            return html_content

    def _generate_section_html(self, section: SectionContent, section_num: int) -> str:
        """Generate HTML for a single section."""
        # Convert markdown to HTML with improved code highlighting
        md_html = markdown.markdown(
            section.markdown_content,
            extensions=[
                "extra",  # Tables, attributes, etc.
                "fenced_code",  # ```python code blocks
                "codehilite",  # Syntax highlighting
                "tables",  # Table support
                "nl2br",  # Newline to <br>
                "sane_lists",  # Better list handling
            ],
            extension_configs={"codehilite": {"css_class": "highlight", "linenums": False, "guess_lang": True}},
        )

        # Clean up HTML structure
        md_html = self._cleanup_content(md_html)

        # Add diagrams
        diagrams_html = []
        for diagram in section.diagrams:
            diagrams_html.append(
                f"""
            <div class="my-8">
                <h4 class="text-center text-gray-600 mb-2">{diagram.title}</h4>
                <div class="mermaid">
{diagram.mermaid_code}
                </div>
            </div>"""
            )

        # Add images with corrected relative paths
        images_html = []
        for img in section.images:
            # Fix path: outputs/file.html -> ../data/images/...
            corrected_path = f"../{img.path}" if not img.path.startswith(("http://", "https://", "../")) else img.path

            images_html.append(
                f"""
            <figure class="my-6">
                <img src="{corrected_path}" alt="{img.description}" loading="lazy" />
                <figcaption class="text-center text-sm text-gray-600 mt-2">
                    {img.caption or img.description}
                    {f'<br><span class="text-xs">{img.attribution}</span>' if img.attribution else ''}
                </figcaption>
            </figure>"""
            )

        return f"""
        <section id="{section.section_id}" class="section">
            <h2>{section_num}. {section.title}</h2>
            {md_html}
            {''.join(diagrams_html)}
            {''.join(images_html)}
        </section>"""
