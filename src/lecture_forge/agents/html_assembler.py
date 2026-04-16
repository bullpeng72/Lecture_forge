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
        super().__init__(thinking=False)
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
                # Bundle images next to the output file before writing
                html_content = self._bundle_images(html_content, Path(output_path))
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

        # Bundle images next to the HTML so they survive data/images cleanup
        html_content = self._bundle_images(html_content, Path(output_path))

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

    def _bundle_images(self, html_content: str, html_path: Path) -> str:
        """Copy local images into a {stem}_images/ folder next to the HTML.

        Images stored in data/images/ are deleted when the user runs
        ``lecture-forge cleanup``.  Bundling them alongside the HTML file
        makes the output self-contained so that images survive cleanup.

        Scans the generated HTML for local <img src="..."> attributes rather
        than relying on ImageReference.path (which is absolute, different from
        the relative src written into the HTML by _render_image_html).

        Returns the HTML string with src attributes updated to the new paths.
        """
        import re as _re

        # Find all img src attributes that are local (not http/https, not data:)
        src_pattern = _re.compile(r'<img\b[^>]*\bsrc="([^"]+)"')
        all_srcs = src_pattern.findall(html_content)

        local_srcs: list[tuple[str, Path]] = []  # (src_attr_value, resolved_path)
        for src in all_srcs:
            if src.startswith(("http://", "https://", "data:", "//")):
                continue
            resolved = (html_path.parent / src).resolve()
            if resolved.exists():
                local_srcs.append((src, resolved))

        if not local_srcs:
            return html_content

        # Create bundle directory: {html_stem}_images/ next to the HTML
        bundle_dir = html_path.parent / f"{html_path.stem}_images"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        replacements: dict[str, str] = {}

        for src_attr, src_file in local_srcs:
            if src_attr in replacements:
                continue  # already handled
            dest_file = bundle_dir / src_file.name
            # If dest already exists with the same size, skip copy
            if not dest_file.exists() or dest_file.stat().st_size != src_file.stat().st_size:
                try:
                    shutil.copy2(src_file, dest_file)
                    copied += 1
                except OSError as e:
                    logger.warning(f"Could not copy image {src_file.name}: {e}")
                    continue
            # Build new relative src: "./{stem}_images/filename.ext"
            new_src = f"./{bundle_dir.name}/{src_file.name}"
            replacements[src_attr] = new_src

        if not replacements:
            return html_content

        # Replace src attributes in HTML via exact string match
        for old_src, new_src in replacements.items():
            html_content = html_content.replace(f'src="{old_src}"', f'src="{new_src}"')

        logger.info(f"   📦 Bundled {copied} images → {bundle_dir.name}/")
        return html_content

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

    def _build_section_id_registry(self, sections: List[SectionContent]) -> dict:
        """
        Build a mapping from raw section_id → unique sanitized HTML id.

        When two sections produce the same sanitized id (e.g. Korean-only
        titles that share the same ASCII prefix), the later ones get a
        numeric suffix (_2, _3, …) to guarantee uniqueness.
        """
        registry: dict = {}
        used: set = set()
        for section in sections:
            base = self._sanitize_section_id(section.section_id)
            if base not in used:
                registry[section.section_id] = base
                used.add(base)
            else:
                counter = 2
                candidate = f"{base}_{counter}"
                while candidate in used:
                    counter += 1
                    candidate = f"{base}_{counter}"
                registry[section.section_id] = candidate
                used.add(candidate)
        return registry

    def _generate_html(self, lecture: Lecture) -> str:
        """Generate complete HTML document using Jinja2 template."""
        # Build a de-duplicated id registry before any HTML generation
        self._id_registry = self._build_section_id_registry(lecture.sections)

        # Convert sections to HTML
        sections_html = []
        for i, section in enumerate(lecture.sections):
            section_html = self._generate_section_html(section, i + 1)
            sections_html.append(section_html)

        # Generate TOC and objectives
        toc_html = self._generate_toc(lecture.sections)
        objectives_html = self._generate_objectives_html(lecture.learning_objectives)

        # Build search data (full content for search; preview truncation is handled in search.js)
        search_data = {
            "sections": [
                {
                    "section_id": self._id_registry.get(section.section_id,
                                                        self._sanitize_section_id(section.section_id)),
                    "title": section.title,
                    "markdown_content": section.markdown_content,
                }
                for section in lecture.sections
            ]
        }
        search_data_json = json.dumps(search_data, ensure_ascii=False)

        template = self.jinja_env.get_template("lecture_html.html")
        html_content = template.render(
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
        # v0.5.2: 재평가 기능을 위해 메타데이터를 HTML 상단에 주석으로 내장
        metadata_comments = (
            f"<!-- lf:vector_db_path: {lecture.vector_db_path or ''} -->\n"
            f"<!-- lf:topic: {lecture.topic} -->\n"
            f"<!-- lf:duration: {lecture.duration} -->\n"
            f"<!-- lf:audience_level: {lecture.audience_level} -->\n"
        )
        return metadata_comments + html_content

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
            safe_id = getattr(self, '_id_registry', {}).get(
                section.section_id, self._sanitize_section_id(section.section_id)
            )
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
        except (ValueError, AttributeError) as e:
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
        except (ValueError, AttributeError):
            return html_content

    def _render_image_html(self, img) -> str:
        """Render a single ImageReference as HTML <figure> with correct relative path."""
        img_path = Path(img.path)

        if img_path.is_absolute():
            try:
                rel_to_data = img_path.relative_to(Config.DATA_DIR)
                rel_data_dir = os.path.relpath(Config.DATA_DIR, Config.OUTPUT_DIR)
                corrected_path = str(Path(rel_data_dir) / rel_to_data).replace("\\", "/")
            except ValueError:
                corrected_path = str(img.path)
        elif img.path.startswith(("http://", "https://")):
            corrected_path = img.path
        elif img.path.startswith("../"):
            corrected_path = img.path
        else:
            corrected_path = f"../{img.path}"

        return f"""
            <figure class="my-6">
                <img src="{corrected_path}" alt="{img.description}" loading="lazy"
                     onerror="this.closest('figure').style.display='none'" />
                <figcaption class="text-center text-sm text-gray-600 mt-2">
                    {img.caption or img.description}
                    {f'<br><span class="text-xs">{img.attribution}</span>' if img.attribution else ''}
                </figcaption>
            </figure>"""

    def _generate_section_html(self, section: SectionContent, section_num: int) -> str:
        """Generate HTML for a single section."""
        _md_extensions = [
            "extra",       # Tables, attributes, etc.
            "fenced_code", # ```python code blocks
            "codehilite",  # Syntax highlighting
            "tables",      # Table support
            "nl2br",       # Newline to <br>
            "sane_lists",  # Better list handling
        ]
        _md_ext_configs = {"codehilite": {"css_class": "highlight", "linenums": False, "guess_lang": True}}

        # v0.4.0: subsection-based image placement (inline after each ## heading)
        subsection_images = getattr(section, "subsection_images", {})

        if subsection_images:
            # Import parse_markdown_subsections from content_writer (or use inline version)
            try:
                from lecture_forge.agents.content_writer.agent import parse_markdown_subsections
            except ImportError:
                # Inline fallback
                import re as _re
                def parse_markdown_subsections(md):
                    pat = _re.compile(r"^(#{2,3})\s+(.+)$", _re.MULTILINE)
                    ms = list(pat.finditer(md))
                    if not ms:
                        return [{"heading": "", "heading_text": "", "level": 2, "content": md}]
                    subs = []
                    for i, m in enumerate(ms):
                        start = m.end()
                        end = ms[i+1].start() if i+1 < len(ms) else len(md)
                        subs.append({"heading": m.group(0), "heading_text": m.group(2),
                                     "level": len(m.group(1)), "content": md[start:end].strip()})
                    return subs

            subsections = parse_markdown_subsections(section.markdown_content)
            html_parts = []
            for subsec in subsections:
                # Convert this subsection's markdown (heading + content) to HTML
                subsec_md = (f"{subsec['heading']}\n\n{subsec['content']}" if subsec["heading"]
                             else subsec["content"])
                subsec_html = markdown.markdown(subsec_md, extensions=_md_extensions,
                                                extension_configs=_md_ext_configs)
                subsec_html = self._cleanup_content(subsec_html)
                subsec_html = self._annotate_code_languages(subsec_md, subsec_html)
                html_parts.append(subsec_html)

                # Insert images assigned to this subsection
                for img in subsection_images.get(subsec["heading"], []):
                    html_parts.append(self._render_image_html(img))

            md_html = "\n".join(html_parts)

            # Collect images that were NOT assigned to any subsection (fallback)
            assigned_image_ids = {
                img.image_id
                for imgs in subsection_images.values()
                for img in imgs
            }
            remaining_images = [img for img in section.images if img.image_id not in assigned_image_ids]
        else:
            # Fallback: classic rendering — all markdown then all images
            md_html = markdown.markdown(
                section.markdown_content,
                extensions=_md_extensions,
                extension_configs=_md_ext_configs,
            )
            md_html = self._cleanup_content(md_html)
            md_html = self._annotate_code_languages(section.markdown_content, md_html)
            remaining_images = section.images

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

        # Add remaining images (not inline-placed) at the end
        remaining_images_html = [self._render_image_html(img) for img in remaining_images]

        safe_id = getattr(self, '_id_registry', {}).get(
            section.section_id, self._sanitize_section_id(section.section_id)
        )
        return f"""
        <section id="{safe_id}" class="section">
            <h2>{section_num}. {section.title}</h2>
            {md_html}
            {''.join(diagrams_html)}
            {''.join(remaining_images_html)}
        </section>"""
