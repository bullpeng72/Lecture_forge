"""
HTML Assembler Agent - Generates final HTML output.
"""

import json
import os
import re
import shutil
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

        # Copy static assets (styles.css, search.js) alongside the HTML so that
        # relative href/src links in the template resolve correctly.
        self._copy_static_assets(output_dir)

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
                # Copy static assets to the target directory too
                self._copy_static_assets(Path(output_path).parent)
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

    def _copy_static_assets(self, dest_dir: Path) -> None:
        """Copy styles.css and search.js next to the generated HTML file.

        The template references these files with relative paths, so they must
        exist in the same directory as the HTML output.  We always overwrite so
        that updated assets are deployed whenever a new lecture is generated.
        """
        templates_dir = Path(__file__).parent.parent / "templates"
        for asset in ("styles.css", "search.js"):
            src = templates_dir / asset
            if src.exists():
                shutil.copy2(src, dest_dir / asset)

    def _detect_lang(self, lecture: Lecture) -> str:
        """Detect primary language from lecture title and first section content.

        Returns an IETF language tag ('ko', 'ja', 'zh', 'en', …) for use in
        the HTML lang attribute.  Falls back to 'ko' when CJK characters are
        dominant, 'en' otherwise.
        """
        sample = lecture.title
        if lecture.sections:
            sample += " " + lecture.sections[0].markdown_content[:300]
        # Count Hangul, CJK, Hiragana/Katakana characters
        hangul = sum(1 for c in sample if '\uac00' <= c <= '\ud7af')
        cjk    = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff')
        kana   = sum(1 for c in sample if '\u3040' <= c <= '\u30ff')
        total  = max(len(sample), 1)
        if hangul / total > 0.05:
            return "ko"
        if kana / total > 0.05:
            return "ja"
        if cjk / total > 0.05:
            return "zh"
        return "en"

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

        # Build search data (first 500 chars of content for snippet preview)
        search_data = {
            "sections": [
                {
                    "section_id": self._sanitize_section_id(section.section_id),
                    "title": section.title,
                    "markdown_content": section.markdown_content[:500],
                }
                for section in lecture.sections
            ]
        }
        search_data_json = json.dumps(search_data, ensure_ascii=False)

        template = self.jinja_env.get_template("lecture_html.html")
        return template.render(
            title=lecture.title,
            lang=self._detect_lang(lecture),
            duration=lecture.duration,
            audience_level=lecture.audience_level.capitalize(),
            toc_html=toc_html,
            objectives_html=objectives_html,
            sections_html="\n".join(sections_html),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_word_count=lecture.total_word_count,
            total_images=lecture.total_images,
            total_diagrams=lecture.total_diagrams,
            search_data_json=search_data_json,
        )

    def _sanitize_section_id(self, section_id: str) -> str:
        """
        Convert a section_id to an ASCII-safe HTML id attribute value.

        Strips non-ASCII characters (e.g. Korean) and replaces special
        characters that would break CSS attribute selectors (parentheses,
        brackets, etc.) with underscores.
        """
        # Remove non-ASCII characters
        safe = re.sub(r'[^\x00-\x7F]', '', section_id)
        # Replace anything that isn't alphanumeric, underscore, or hyphen
        safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', safe)
        # Collapse multiple consecutive underscores
        safe = re.sub(r'_+', '_', safe)
        # Strip leading/trailing underscores
        safe = safe.strip('_')
        return safe or 'section'

    def _generate_toc(self, sections: List[SectionContent]) -> str:
        """Generate table of contents HTML."""
        toc_items = []

        for section in sections:
            safe_id = self._sanitize_section_id(section.section_id)
            toc_items.append(f'<a href="#{safe_id}" class="toc-link">{section.title}</a>')

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

    def _annotate_code_languages(self, markdown_source: str, html_content: str) -> str:
        """Add data-lang attributes to .highlight divs from fenced code block languages.

        Pygments does not emit a language class on <code>, so we extract languages
        from the markdown source in order and stamp each .highlight wrapper div with
        data-lang="<language>" so the slides parser can detect the language correctly.
        """
        # Extract fenced code-block languages in document order (```lang or ~~~lang)
        languages = re.findall(r'(?:```|~~~)(\w+)', markdown_source)
        if not languages:
            return html_content

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            highlight_divs = soup.find_all("div", class_="highlight")
            for div, lang in zip(highlight_divs, languages):
                div["data-lang"] = lang
            return str(soup)
        except Exception:
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

        # Annotate .highlight divs with data-lang for slides parser
        md_html = self._annotate_code_languages(section.markdown_content, md_html)

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
                <img src="{corrected_path}" alt="{img.description}" loading="lazy"
                     onerror="this.closest('figure').style.display='none'" />
                <figcaption class="text-center text-sm text-gray-600 mt-2">
                    {img.caption or img.description}
                    {f'<br><span class="text-xs">{img.attribution}</span>' if img.attribution else ''}
                </figcaption>
            </figure>"""
            )

        safe_id = self._sanitize_section_id(section.section_id)
        return f"""
        <section id="{safe_id}" class="section">
            <h2>{section_num}. {section.title}</h2>
            {md_html}
            {''.join(diagrams_html)}
            {''.join(images_html)}
        </section>"""
