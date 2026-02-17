"""
HTML Assembler Agent - Generates final HTML output.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List

import markdown
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.models.lecture import Lecture, SectionContent
from lecture_forge.utils import logger


class HTMLAssemblerAgent(BaseAgent):
    """Agent for assembling final HTML output."""

    def __init__(self):
        super().__init__()
        logger.info("Initializing HTML Assembler Agent")
        templates_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape([]),
        )

    def assemble(
        self,
        lecture: Lecture,
        output_path: str = None,
        image_search_enabled: bool = True,
    ) -> str:
        """
        Assemble final HTML from lecture content.

        Args:
            lecture: Complete lecture data
            output_path: Path to save HTML file
            image_search_enabled: Whether image search was enabled (affects log level)

        Returns:
            Path to generated HTML file
        """
        logger.info(f"Assembling HTML for lecture: {lecture.title}")

        # Validate image availability
        self._validate_images(lecture, image_search_enabled)

        # Generate HTML content
        html_content = self._generate_html(lecture)

        # Determine output path
        output_dir = Config.OUTPUT_DIR  # Always use configured output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        if not output_path:
            # Generate filename if not provided
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{lecture.topic.replace(' ', '_')}_{timestamp}.html"
        else:
            # Process provided output_path
            output_path_obj = Path(output_path)

            # If it's just a filename (no directory), use output_dir
            if output_path_obj.parent == Path("."):
                filename = output_path_obj.name
                # Add .html extension if missing
                if not filename.endswith(".html"):
                    filename = f"{filename}.html"
            else:
                # Absolute or relative path with directory - use as-is
                # but ensure .html extension
                if not str(output_path_obj).endswith(".html"):
                    output_path = f"{output_path}.html"
                # Write directly and return early
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"✅ HTML generated: {output_path}")
                logger.info(f"   - Sections: {len(lecture.sections)}")
                logger.info(f"   - Words: {lecture.total_word_count}")
                logger.info(f"   - Images: {lecture.total_images}")
                logger.info(f"   - Diagrams: {lecture.total_diagrams}")
                return output_path

        # Construct full path in output directory
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

    def _validate_images(self, lecture: Lecture, image_search_enabled: bool = True):
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
            if not image_search_enabled:
                logger.info("ℹ️  No images (image search disabled by --no-image-search)")
            else:
                logger.warning("⚠️  No images collected. Check API keys (PEXELS_API_KEY, UNSPLASH_ACCESS_KEY)")
                logger.warning("   Tip: $ lecture-forge create --image-search")
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
        """Generate complete HTML document using Jinja2 template."""
        # Convert sections to HTML
        sections_html = []
        for i, section in enumerate(lecture.sections):
            section_html = self._generate_section_html(section, i + 1)
            sections_html.append(section_html)

        # Generate TOC and objectives
        toc_html = self._generate_toc(lecture.sections)
        objectives_html = self._generate_objectives_html(lecture.learning_objectives)

        template = self.jinja_env.get_template("lecture_html.html")
        return template.render(
            title=lecture.title,
            duration=lecture.duration,
            audience_level=lecture.audience_level.capitalize(),
            toc_html=toc_html,
            objectives_html=objectives_html,
            sections_html="\n".join(sections_html),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_word_count=lecture.total_word_count,
            total_images=lecture.total_images,
            total_diagrams=lecture.total_diagrams,
        )

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
            # Fix path: Calculate proper relative path from OUTPUT_DIR to image
            img_path = Path(img.path)

            # Handle absolute paths (convert to relative from outputs/)
            if img_path.is_absolute():
                try:
                    # Get relative path from DATA_DIR
                    rel_to_data = img_path.relative_to(Config.DATA_DIR)

                    # Calculate relative path from OUTPUT_DIR to DATA_DIR
                    # This works for any .env configuration!
                    rel_data_dir = os.path.relpath(Config.DATA_DIR, Config.OUTPUT_DIR)
                    corrected_path = str(Path(rel_data_dir) / rel_to_data)

                    # Normalize path separators for web (use forward slashes)
                    corrected_path = corrected_path.replace('\\', '/')
                except ValueError:
                    # Not under DATA_DIR, might be URL or other path
                    corrected_path = str(img.path)
            # Handle relative paths and URLs
            elif img.path.startswith(("http://", "https://")):
                corrected_path = img.path
            elif img.path.startswith("../"):
                corrected_path = img.path
            else:
                corrected_path = f"../{img.path}"

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
