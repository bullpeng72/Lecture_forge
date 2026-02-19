"""
HTML lecture parser for slide conversion.
"""

import re
from pathlib import Path
from typing import Dict, List

_LEVEL_SUFFIX_RE = re.compile(r"\s*-\s*\w+\s+Level\s*$", re.IGNORECASE)

from bs4 import BeautifulSoup

from lecture_forge.slides.utils import batch_convert_to_bullet_points, convert_to_bullet_points
from lecture_forge.utils import logger


class HTMLLectureParser:
    """Parser for extracting lecture content from HTML files."""

    def __init__(self):
        """Initialize HTML lecture parser."""
        self.converted_paragraphs = 0

    def parse(self, html_path: Path) -> Dict:
        """Parse lecture HTML file and extract structured content.

        Args:
            html_path: Path to lecture HTML file

        Returns:
            Dictionary with title, subtitle, and sections
        """
        # Read HTML file
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract metadata
        title = self._extract_title(soup)
        subtitle = self._extract_subtitle(soup)

        # Extract sections
        sections = self._extract_sections(soup)

        logger.debug(f"Parsed lecture: {title}, {len(sections)} sections, {self.converted_paragraphs} paragraphs converted")

        return {
            "title": title,
            "subtitle": subtitle,
            "sections": sections,
            "converted_paragraphs": self.converted_paragraphs,
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract lecture title from HTML, stripping the '- Level' suffix added by create.py."""
        raw = self._extract_raw_title(soup)
        return _LEVEL_SUFFIX_RE.sub("", raw).strip() or raw

    def _extract_raw_title(self, soup: BeautifulSoup) -> str:
        """Extract raw title string (before level-suffix stripping)."""
        # 1. Legacy class (never matched by current template, kept for compatibility)
        title_tag = soup.find("h1", class_="lecture-title")
        if title_tag:
            return title_tag.text.strip()
        # 2. <title> tag (reliable, always present)
        title_elem = soup.find("title")
        if title_elem and title_elem.text.strip():
            return title_elem.text.strip()
        # 3. First <h1> in main content area
        main = soup.find(id="mainContent")
        if main:
            h1 = main.find("h1")
            if h1:
                return h1.text.strip()
        # 4. Any <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.text.strip()
        return "Lecture Slides"

    def _extract_subtitle(self, soup: BeautifulSoup) -> str:
        """Extract lecture subtitle from HTML."""
        subtitle_tag = soup.find("p", class_="lecture-subtitle")
        return subtitle_tag.text.strip() if subtitle_tag else ""

    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract all sections from HTML.

        Returns:
            List of section dictionaries with title and content blocks
        """
        sections = []
        section_elements = soup.find_all("section", id=True)

        logger.debug(f"Found {len(section_elements)} sections in HTML")

        for section_elem in section_elements:
            # Find section title (h2)
            section_title_tag = section_elem.find("h2")
            if not section_title_tag:
                logger.debug(f"Skipping section without h2: {section_elem.get('id')}")
                continue

            # Extract title and remove numbering
            section_title_raw = section_title_tag.text.strip()
            section_title = re.sub(r"^\d+\.\s*", "", section_title_raw)

            logger.debug(f"Processing section: {section_title_raw} -> {section_title}")

            # Extract content blocks
            content_blocks = self._extract_content_blocks(section_elem)

            sections.append({"title": section_title, "blocks": content_blocks})

        return sections

    def _extract_content_blocks(self, section_elem) -> List[Dict]:
        """Extract content blocks from a section element.

        Paragraphs that require LLM conversion are collected first, then
        converted in a single batched API call to minimise LLM round-trips.

        Args:
            section_elem: BeautifulSoup section element

        Returns:
            List of content block dictionaries
        """
        content_blocks: List[Dict] = []

        # (placeholder_index, paragraph_text) for paragraphs needing LLM conversion
        pending_paragraphs: List = []

        # Process all content elements
        for elem in section_elem.find_all(["h3", "h4", "p", "ul", "ol", "pre"]):
            if elem.name == "h3":
                content_blocks.append({"type": "subsection", "content": elem.text.strip()})
            elif elem.name == "h4":
                text = elem.text.strip()
                if text:
                    content_blocks.append({"type": "subsubsection", "content": text})
            elif elem.name == "p":
                text = elem.text.strip()
                # Skip very short paragraphs, those inside code blocks, and
                # those inside list items (already captured by the list processor)
                if not text or len(text) <= 20 or elem.find_parent(["pre", "li", "ul", "ol"]):
                    continue
                # Short texts / already-bulleted: no LLM needed
                if len(text) < 100 or text.startswith(("•", "-", "*")):
                    content_blocks.append({"type": "paragraph", "content": text})
                    self.converted_paragraphs += 1
                else:
                    # Reserve a slot; fill after batch conversion
                    placeholder_idx = len(content_blocks)
                    content_blocks.append(None)  # type: ignore[arg-type]
                    pending_paragraphs.append((placeholder_idx, text))
            elif elem.name in ["ul", "ol"]:
                # Skip nested lists (already captured as text by the parent list processor)
                if elem.find_parent(["li", "ul", "ol"]):
                    continue
                block = self._process_list(elem)
                if block:
                    content_blocks.append(block)
            elif elem.name == "pre":
                block = self._process_code_block(elem)
                if block:
                    content_blocks.append(block)

        # Batch-convert all paragraphs that need LLM processing
        if pending_paragraphs:
            texts = [t for _, t in pending_paragraphs]
            bullet_lists = batch_convert_to_bullet_points(texts)
            for (placeholder_idx, _), bullet_points in zip(pending_paragraphs, bullet_lists):
                self.converted_paragraphs += 1
                if len(bullet_points) > 1:
                    content_blocks[placeholder_idx] = {"type": "list", "items": bullet_points, "ordered": False}
                else:
                    content_blocks[placeholder_idx] = {"type": "paragraph", "content": bullet_points[0]}

        # Remove any remaining None placeholders (should not occur in normal flow)
        content_blocks = [b for b in content_blocks if b is not None]

        # Extract images — with P3: attach the nearest preceding heading as title
        for figure in section_elem.find_all("figure"):
            block = self._process_image(figure)
            if block:
                block["title"] = self._get_preceding_heading(figure)
                content_blocks.append(block)

        # Extract diagrams
        for diagram_div in section_elem.find_all("div", class_="mermaid"):
            block = self._process_diagram(diagram_div)
            if block:
                content_blocks.append(block)

        return content_blocks

    def _process_paragraph(self, elem) -> Dict:
        """Process paragraph element.

        Returns:
            Content block dictionary or None
        """
        text = elem.text.strip()
        # Filter out very short paragraphs and paragraphs inside code blocks
        if not text or len(text) <= 20 or elem.find_parent("pre"):
            return None

        # Convert narrative text to bullet points
        bullet_points = convert_to_bullet_points(text)
        self.converted_paragraphs += 1

        if len(bullet_points) > 1:
            # Multiple bullet points - add as list
            return {"type": "list", "items": bullet_points, "ordered": False}
        else:
            # Single point or short text - keep as paragraph
            return {"type": "paragraph", "content": bullet_points[0]}

    def _process_list(self, elem) -> Dict:
        """Process list element (ul/ol).

        Returns:
            Content block dictionary or None
        """
        items = [self._li_inner_html(li) for li in elem.find_all("li", recursive=False)]
        items = [item for item in items if item]  # filter empty strings
        if not items:
            return None

        return {"type": "list", "items": items, "ordered": elem.name == "ol"}

    def _li_inner_html(self, li) -> str:
        """Extract inner HTML of a <li>, unwrapping a single <p> wrapper and
        preserving inline formatting tags (strong, em, code, b, i).

        Plain .text.strip() loses <strong>/<code> emphasis which is meaningful
        in slide bullet points.
        """
        _INLINE_TAGS = {"strong", "b", "em", "i", "code", "mark"}

        # Unwrap a single <p> child so <li><p>content</p></li> is treated
        # the same as <li>content</li>
        direct = [c for c in li.children if hasattr(c, "name") or str(c).strip()]
        if len(direct) == 1 and hasattr(direct[0], "name") and direct[0].name == "p":
            li = direct[0]

        # Rebuild content: keep inline tags as-is, convert block tags to plain text
        parts = []
        for child in li.children:
            if not hasattr(child, "name"):          # NavigableString
                parts.append(str(child))
            elif child.name in _INLINE_TAGS:
                parts.append(str(child))
            else:
                parts.append(child.get_text())

        return "".join(parts).strip()

    def _process_code_block(self, elem) -> Dict:
        """Process code block element.

        Returns:
            Content block dictionary or None
        """
        code_elem = elem.find("code")
        # P4: Fallback — use <pre> text directly if no <code> child
        if code_elem:
            code = code_elem.text.strip()
        else:
            code = elem.get_text().strip()

        if not code:
            return None

        # Extract language
        # Priority 1: data-lang on parent .highlight div (set by Pygments post-processor)
        language = "python"  # default
        parent = elem.parent
        if parent and parent.get("data-lang"):
            language = parent["data-lang"]
        elif code_elem and "class" in code_elem.attrs:
            # Priority 2: language-* class on <code> (set by Prism.js / raw fenced blocks)
            for cls in code_elem["class"]:
                if cls.startswith("language-"):
                    language = cls.replace("language-", "")
                    break
        elif "class" in elem.attrs:
            # Priority 3: language-* class on <pre> itself
            for cls in elem.get("class", []):
                if cls.startswith("language-"):
                    language = cls.replace("language-", "")
                    break

        return {"type": "code", "content": code, "language": language}

    def _get_preceding_heading(self, elem) -> str:
        """Return the nearest h2/h3/h4 sibling that precedes *elem* in the DOM.

        Used to capture the contextual heading for an image slide (P3).
        """
        for sibling in elem.previous_siblings:
            if hasattr(sibling, "name") and sibling.name in ("h2", "h3", "h4"):
                return sibling.get_text(strip=True)
        return ""

    def _process_image(self, figure) -> Dict:
        """Process image element.

        Returns:
            Content block dictionary or None
        """
        img = figure.find("img")
        if not img:
            return None

        img_src = img.get("src", "")
        if not img_src:
            return None

        img_alt = img.get("alt", "")
        caption_elem = figure.find("figcaption")
        caption = caption_elem.text.strip() if caption_elem else ""

        return {"type": "image", "src": img_src, "alt": img_alt, "caption": caption}

    def _process_diagram(self, diagram_div) -> Dict:
        """Process diagram element.

        Returns:
            Content block dictionary or None
        """
        mermaid_code = diagram_div.text.strip()
        if not mermaid_code:
            return None

        return {"type": "diagram", "content": mermaid_code}
