"""
Code Generator - Handles code block extraction from markdown.
"""

from typing import List

from lecture_forge.models.lecture import CodeBlock


def extract_code_blocks(markdown: str) -> List[CodeBlock]:
    """Extract fenced code blocks from markdown content."""
    code_blocks = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            language = line.strip()[3:].strip() or "text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = "\n".join(code_lines)
            code_blocks.append(CodeBlock(language=language, code=code, caption=None))
        i += 1

    return code_blocks


# Keep class for backwards compatibility with __init__.py exports
class CodeGenerator:
    """Thin wrapper kept for import compatibility."""

    def extract_code_blocks(self, markdown: str) -> List[CodeBlock]:
        return extract_code_blocks(markdown)
