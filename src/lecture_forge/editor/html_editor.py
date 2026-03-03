"""
HTML Lecture Editor - Section-level editing logic.

Handles parsing, updating, and deleting sections in generated lecture HTML.
Image/diagram operations are delegated to ImageEditor.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

import markdown
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

from lecture_forge.utils import logger


class LectureHTMLEditor:
    """Manages section-level edits on a lecture HTML file."""

    def __init__(self, html_path: str, soup: Optional[BeautifulSoup] = None):
        self.html_path = Path(html_path)
        if not self.html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        if soup is not None:
            self.soup = soup
        else:
            with open(self.html_path, "r", encoding="utf-8") as f:
                self.soup = BeautifulSoup(f.read(), "html.parser")

        # Fix duplicate section IDs that can occur in pre-v0.5.2 HTML files
        self._deduplicate_section_ids()

        # Staging: {section_id: {"title": ..., "markdown": ...}} or "deleted"
        self._staged: Dict[str, object] = {}
        # Image additions: {section_id: [{"path": ..., "caption": ...}]}
        self._added_images: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_lecture_meta(self) -> Dict:
        """Return lecture metadata and section list."""
        title_tag = self.soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        sections = []
        for sec in self.soup.find_all("section", id=True):
            sec_id = sec.get("id", "")
            h2 = sec.find("h2")
            if not h2:
                continue
            sec_title = h2.get_text(strip=True)

            # Word count (text only, no scripts/styles)
            text = sec.get_text(separator=" ")
            word_count = len(text.split())

            # Image / diagram count
            img_count = len(sec.find_all("img"))
            dgm_count = len(sec.find_all("div", class_="mermaid"))

            staged = self._staged.get(sec_id)
            if staged == "deleted":
                status = "deleted"
            elif staged is not None:
                status = "modified"
            else:
                status = "original"

            sections.append({
                "id": sec_id,
                "title": sec_title,
                "word_count": word_count,
                "image_count": img_count,
                "diagram_count": dgm_count,
                "status": status,
            })

        return {"title": title, "sections": sections}

    def get_section_content(self, section_id: str) -> Dict:
        """
        Return section content as Markdown (via markdownify).

        Returns dict with keys: id, title, markdown, word_count
        """
        sec = self.soup.find("section", id=section_id)
        if not sec:
            return {"error": f"Section not found: {section_id}"}

        h2 = sec.find("h2")
        title = h2.get_text(strip=True) if h2 else ""

        # Check if staged modification exists
        staged = self._staged.get(section_id)
        if staged and staged != "deleted":
            return {
                "id": section_id,
                "title": staged.get("title", title),
                "markdown": staged.get("markdown", ""),
                "word_count": len(staged.get("markdown", "").split()),
                "status": "modified",
            }

        # Convert HTML section content → Markdown
        md = self._html_section_to_markdown(sec)
        word_count = len(md.split())

        return {
            "id": section_id,
            "title": title,
            "markdown": md,
            "word_count": word_count,
            "status": "original",
        }

    def update_section_content(
        self, section_id: str, markdown_text: str, title: Optional[str] = None
    ) -> Dict:
        """Stage a section content update (does not write to disk)."""
        sec = self.soup.find("section", id=section_id)
        if not sec:
            return {"success": False, "error": f"Section not found: {section_id}"}

        h2 = sec.find("h2")
        current_title = h2.get_text(strip=True) if h2 else ""

        self._staged[section_id] = {
            "title": title if title is not None else current_title,
            "markdown": markdown_text,
        }
        return {"success": True, "section_id": section_id}

    def delete_section(self, section_id: str) -> bool:
        """Stage a section for deletion."""
        sec = self.soup.find("section", id=section_id)
        if not sec:
            return False
        self._staged[section_id] = "deleted"
        return True

    def stage_add_image(self, section_id: str, image_path: str, caption: str = "") -> bool:
        """Stage an image addition for a section."""
        sec = self.soup.find("section", id=section_id)
        if not sec:
            return False
        self._added_images.setdefault(section_id, []).append(
            {"path": image_path, "caption": caption}
        )
        return True

    def unstage_add_image(self, section_id: str, index: int) -> bool:
        """Remove a pending image addition by its list index."""
        images = self._added_images.get(section_id, [])
        if 0 <= index < len(images):
            images.pop(index)
            return True
        return False

    def get_pending_additions(self, section_id: str) -> List[Dict]:
        """Return staged image additions for a section."""
        return list(self._added_images.get(section_id, []))

    def apply_all_changes(self) -> BeautifulSoup:
        """
        Apply all staged changes to a copy of the soup.

        Returns the modified BeautifulSoup (does NOT write to disk).
        The caller (server.py) is responsible for saving.
        """
        for section_id, change in self._staged.items():
            sec = self.soup.find("section", id=section_id)
            if not sec:
                logger.warning(f"Section {section_id} not found during apply; skipping")
                continue

            if change == "deleted":
                # Remove section from DOM
                sec.decompose()
                # Also remove matching TOC entry
                self._remove_toc_entry(section_id)

            else:
                # Apply title update
                new_title = change.get("title", "")
                h2 = sec.find("h2")
                if h2 and new_title:
                    # Preserve section number prefix if present (e.g., "2. ")
                    old_text = h2.get_text(strip=True)
                    prefix_match = re.match(r"^(\d+\.\s+)", old_text)
                    prefix = prefix_match.group(1) if prefix_match else ""
                    # Strip prefix from new title if user included it
                    clean_title = re.sub(r"^\d+\.\s+", "", new_title)
                    h2.string = prefix + clean_title

                # Apply content update (Markdown → HTML)
                md_text = change.get("markdown", "")
                new_html = self._markdown_to_section_html(md_text)
                self._replace_section_content(sec, new_html)

                # Update TOC title
                self._update_toc_entry(section_id, new_title)

        # Apply staged image additions
        for section_id, images in self._added_images.items():
            sec = self.soup.find("section", id=section_id)
            if not sec:
                logger.warning(f"Section {section_id} not found for image addition; skipping")
                continue
            for img_info in images:
                self._append_figure(sec, img_info["path"], img_info.get("caption", ""))

        # Update section word counts in sidebar stats
        self._update_stats()

        return self.soup

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _deduplicate_section_ids(self) -> None:
        """Fix duplicate <section id="..."> attributes in-place.

        Pre-v0.5.2 HTML files may contain two sections whose titles produce
        the same sanitized id (e.g. Korean-only titles sharing the same ASCII
        prefix).  Later duplicates are renamed with a _2, _3, … suffix so
        every section has a unique id, and the matching TOC <a href> is
        updated accordingly.
        """
        seen: Dict[str, int] = {}  # id -> occurrence count (0-indexed)
        all_ids: set = {s.get("id", "") for s in self.soup.find_all("section", id=True)}

        for sec in self.soup.find_all("section", id=True):
            sec_id = sec.get("id", "")
            occurrence = seen.get(sec_id, 0)
            seen[sec_id] = occurrence + 1

            if occurrence == 0:
                continue  # first occurrence — keep as-is

            # Find a collision-free new id
            counter = occurrence + 1
            new_id = f"{sec_id}_{counter}"
            while new_id in all_ids:
                counter += 1
                new_id = f"{sec_id}_{counter}"
            all_ids.add(new_id)

            # Rename the section element
            sec["id"] = new_id

            # Update the corresponding TOC link (the occurrence-th one)
            dup_links = self.soup.find_all("a", href=f"#{sec_id}", class_="toc-link")
            if occurrence < len(dup_links):
                dup_links[occurrence]["href"] = f"#{new_id}"

            logger.debug(
                f"Deduplicated section id: '{sec_id}' → '{new_id}' "
                f"(occurrence {occurrence + 1})"
            )

    def _html_section_to_markdown(self, sec: Tag) -> str:
        """Convert section inner HTML to Markdown, excluding figures and diagrams."""
        # Work on a clone to avoid mutating the main soup
        clone = BeautifulSoup(str(sec), "html.parser")

        # Remove heading (h2) — it's the title, kept separately
        h2 = clone.find("h2")
        if h2:
            h2.decompose()

        # Remove figure elements (images with captions)
        for fig in clone.find_all("figure"):
            fig.decompose()

        # Remove standalone img tags
        for img in clone.find_all("img"):
            img.decompose()

        # Remove mermaid diagram containers
        for div in clone.find_all("div", class_="my-8"):
            if div.find("div", class_="mermaid"):
                div.decompose()
        for div in clone.find_all("div", class_="mermaid"):
            div.decompose()

        # Remove search-index script tags
        for script in clone.find_all("script"):
            script.decompose()

        # Get inner HTML of section
        section_tag = clone.find("section")
        inner_html = section_tag.decode_contents() if section_tag else str(clone)

        # Convert to Markdown
        md = markdownify(inner_html, heading_style="ATX", strip=["a"])
        # Normalize excessive blank lines
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md

    def _markdown_to_section_html(self, md_text: str) -> str:
        """Convert Markdown text to HTML for insertion into a section."""
        html = markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "nl2br"],
        )
        return html

    def _replace_section_content(self, sec: Tag, new_html: str) -> None:
        """Replace text/content children of section, keeping figure/diagram elements."""
        # Collect elements to keep (figures, mermaid containers)
        preserved = []
        for child in list(sec.children):
            if not isinstance(child, Tag):
                continue
            if child.name == "h2":
                preserved.append(("heading", child))
            elif child.name == "figure":
                preserved.append(("figure", child))
            elif child.name == "div" and (
                "my-8" in (child.get("class") or [])
                and child.find("div", class_="mermaid")
            ):
                preserved.append(("diagram", child))
            elif child.name == "div" and "mermaid" in (child.get("class") or []):
                preserved.append(("diagram", child))

        # Clear all children
        sec.clear()

        # Re-add heading
        for kind, tag in preserved:
            if kind == "heading":
                sec.append(tag)
                break

        # Insert new content HTML
        new_soup = BeautifulSoup(new_html, "html.parser")
        for elem in list(new_soup.children):
            sec.append(elem)

        # Re-add figures and diagrams at the end
        for kind, tag in preserved:
            if kind in ("figure", "diagram"):
                sec.append(tag)

    def _remove_toc_entry(self, section_id: str) -> None:
        """Remove TOC entry linking to this section.

        The lecture template uses bare <a class="toc-link"> anchors with no <li>
        wrapper.  Fall back to removing the <a> tag itself when no parent <li>
        exists so both template styles are handled.
        """
        link = self.soup.find("a", href=f"#{section_id}")
        if not link:
            return
        li = link.find_parent("li")
        if li:
            li.decompose()
        else:
            link.decompose()

    def _update_toc_entry(self, section_id: str, new_title: str) -> None:
        """Update TOC link text for a section."""
        if not new_title:
            return
        link = self.soup.find("a", href=f"#{section_id}")
        if link:
            clean_title = re.sub(r"^\d+\.\s+", "", new_title)
            # Preserve any existing number prefix in the link
            old_text = link.get_text(strip=True)
            prefix_match = re.match(r"^(\d+\.\s+)", old_text)
            prefix = prefix_match.group(1) if prefix_match else ""
            link.string = prefix + clean_title

    def _append_figure(self, sec: Tag, image_path: str, caption: str = "") -> None:
        """Append a <figure> element containing the given image to a section."""
        fig = self.soup.new_tag("figure", attrs={"class": "my-6 text-center"})
        img = self.soup.new_tag(
            "img",
            src=image_path,
            alt=caption or "추가된 이미지",
            attrs={"class": "max-w-full rounded shadow mx-auto"},
        )
        fig.append(img)
        if caption:
            figcap = self.soup.new_tag(
                "figcaption", attrs={"class": "text-sm text-gray-500 mt-2"}
            )
            figcap.string = caption
            fig.append(figcap)
        sec.append(fig)

    def _update_stats(self) -> None:
        """Update word count / section count stats in sidebar if present."""
        remaining_sections = len(self.soup.find_all("section", id=True))
        for text_node in self.soup.find_all(string=re.compile(r"섹션\s*\d+개")):
            new_text = re.sub(
                r"(섹션\s*)\d+(개)", rf"\g<1>{remaining_sections}\g<2>", str(text_node)
            )
            text_node.replace_with(new_text)
