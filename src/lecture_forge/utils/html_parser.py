"""
HTML parser utilities - parse lecture HTML files back to Lecture objects.
"""

from typing import Optional

from lecture_forge.utils import logger


def parse_html_to_lecture(html_path: str) -> Optional["Lecture"]:
    """
    Parse HTML file back to Lecture object.

    Args:
        html_path: Path to HTML file

    Returns:
        Lecture object or None if parsing fails
    """
    from bs4 import BeautifulSoup

    from lecture_forge.models.lecture import CodeBlock, Lecture, MermaidDiagram, SectionContent

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract metadata
        title = soup.find("h1")
        title_text = title.get_text() if title else "Untitled Lecture"

        # Extract learning objectives
        objectives_div = soup.find("div", class_="bg-blue-50")
        objectives = []
        if objectives_div:
            obj_items = objectives_div.find_all("li")
            objectives = [item.get_text() for item in obj_items]

        # Extract sections
        sections = []
        for section_elem in soup.find_all("section", id=True):
            section_id = section_elem.get("id")

            # Get section title
            h2 = section_elem.find("h2")
            if not h2:
                continue

            section_title = h2.get_text()
            # Remove section number (e.g., "1. Title" -> "Title")
            if ". " in section_title:
                section_title = section_title.split(". ", 1)[1]

            # Get content (all text except code blocks and diagrams)
            content_parts = []
            for elem in section_elem.find_all(["p", "h3", "ul", "ol"]):
                content_parts.append(elem.get_text())

            markdown_content = "\n\n".join(content_parts)

            # Extract code blocks
            code_blocks = []
            for pre in section_elem.find_all("pre"):
                code = pre.find("code")
                if code:
                    code_blocks.append(CodeBlock(language="python", code=code.get_text(), caption=None))

            # Extract diagrams
            diagrams = []
            for i, mermaid_div in enumerate(section_elem.find_all("div", class_="mermaid")):
                diagrams.append(
                    MermaidDiagram(
                        id=f"{section_id}_diagram_{i}",
                        title=f"Diagram {i + 1}",
                        mermaid_code=mermaid_div.get_text().strip(),
                        diagram_type="flowchart",
                    )
                )

            section = SectionContent(
                section_id=section_id,
                title=section_title,
                markdown_content=markdown_content,
                code_blocks=code_blocks,
                images=[],
                diagrams=diagrams,
                word_count=len(markdown_content.split()),
            )

            sections.append(section)

        # Create lecture object
        lecture = Lecture(
            title=title_text,
            topic=title_text,
            duration=180,  # Default
            audience_level="intermediate",  # Default
            learning_objectives=objectives,
            sections=sections,
            total_word_count=sum(s.word_count for s in sections),
            total_images=0,
            total_diagrams=sum(len(s.diagrams) for s in sections),
        )

        return lecture

    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        return None
