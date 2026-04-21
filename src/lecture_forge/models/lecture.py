"""
Lecture data model.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CodeBlock(BaseModel):
    """Code block in lecture content."""

    language: str
    code: str
    caption: Optional[str] = None


class ImageReference(BaseModel):
    """Image reference in lecture content."""

    image_id: str
    path: str
    description: str
    caption: Optional[str] = None
    attribution: Optional[str] = None
    # translate mode: [0, 1] position within the chapter (page_idx + y0/page_height) / n_pages
    page_fraction: Optional[float] = None


class MermaidDiagram(BaseModel):
    """Mermaid diagram."""

    id: str
    title: str
    mermaid_code: str
    diagram_type: str  # flowchart, sequence, class, mindmap


class SectionContent(BaseModel):
    """Content for a single section."""

    section_id: str
    title: str
    markdown_content: str
    code_blocks: List[CodeBlock] = Field(default_factory=list)
    images: List[ImageReference] = Field(default_factory=list)
    diagrams: List[MermaidDiagram] = Field(default_factory=list)
    word_count: int = 0
    estimated_time: int = 20  # Default: 20 minutes
    difficulty_level: str = "intermediate"  # Default: intermediate
    # v0.4.0: subsection-level image distribution (heading → images)
    subsection_images: Dict[str, List[ImageReference]] = Field(default_factory=dict)
    # v0.5.0: top RAG chunks preserved for DiagramGenerator context
    rag_key_chunks: List[str] = Field(default_factory=list)
    # v0.6.0: translate mode — page-number keyed image placement
    page_images: Dict[int, List[ImageReference]] = Field(default_factory=dict)
    chapter_pages: List[int] = Field(default_factory=list)


class Lecture(BaseModel):
    """Complete lecture data."""

    title: str
    topic: str
    duration: int  # minutes
    audience_level: str  # beginner, intermediate, advanced
    learning_objectives: List[str] = Field(default_factory=list)
    sections: List[SectionContent] = Field(default_factory=list)
    total_word_count: int = 0
    total_images: int = 0
    total_diagrams: int = 0
    vector_db_path: Optional[str] = None
    created_at: Optional[str] = None

    def to_text(self) -> str:
        """Convert lecture to plain text for evaluation."""
        text_parts = [f"# {self.title}\n"]

        for section in self.sections:
            text_parts.append(f"\n## {section.title}\n")
            text_parts.append(section.markdown_content)

        return "\n".join(text_parts)

    def get_section(self, section_id: str) -> Optional[SectionContent]:
        """Get section by ID."""
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None

    def update_section(self, section_id: str, content: SectionContent) -> None:
        """Update section content."""
        for i, section in enumerate(self.sections):
            if section.section_id == section_id:
                self.sections[i] = content
                break
