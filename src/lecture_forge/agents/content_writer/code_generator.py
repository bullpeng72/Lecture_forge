"""
Code Generator - Handles code extraction and generation for lectures.
"""

import re
from typing import List

from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import CodeBlock
from lecture_forge.utils import logger
from lecture_forge.utils.prompt_manager import load_prompt


class CodeGenerator:
    """Handles code block extraction and generation."""

    def __init__(self, llm_client=None, vector_store: VectorStore = None):
        """
        Initialize CodeGenerator.

        Args:
            llm_client: LLM client for code generation
            vector_store: Vector store for RAG queries
        """
        self.llm = llm_client
        self.vector_store = vector_store

    def extract_code_blocks(self, markdown: str) -> List[CodeBlock]:
        """Extract code blocks (wrapper for compatibility)."""
        return self._extract_code_blocks(markdown)

    def generate_code_examples(
        self, section: Section, curriculum: Curriculum, contexts: List[str], num_examples: int
    ) -> str:
        """Generate code examples (wrapper for compatibility)."""
        return self._generate_code_examples(section, curriculum, contexts, num_examples)

    def _extract_code_blocks(self, markdown: str) -> List[CodeBlock]:
        """Extract code blocks from markdown content."""
        code_blocks = []

        lines = markdown.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for code fence
            if line.strip().startswith("```"):
                # Extract language
                language = line.strip()[3:].strip() or "text"

                # Collect code lines
                code_lines = []
                i += 1

                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1

                code = "\n".join(code_lines)

                code_blocks.append(
                    CodeBlock(
                        language=language,
                        code=code,
                        caption=None,
                    )
                )

            i += 1

        return code_blocks


    def _generate_code_examples(self, section: Section, curriculum: Curriculum, contexts: List[str], num_examples: int) -> str:
        """Generate code examples separately when main content lacks them."""

        context_text = "\n\n---\n\n".join(contexts[:5]) if contexts else ""

        # Prepare template variables
        template_vars = {
            "num_examples": num_examples,
            "section_title": section.title,
            "topic": curriculum.topic,
            "audience_level": curriculum.audience_level,
            "topics_list": ', '.join(section.topics),
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("code_examples_generation", **template_vars)

        try:
            response = self.invoke_llm(prompt, phase="code_generation")
            code_examples_content = response.content.strip()

            # Clean up markdown fences
            if code_examples_content.startswith("```markdown"):
                code_examples_content = code_examples_content.split("```markdown")[1].split("```")[0].strip()
            elif code_examples_content.startswith("```"):
                # Remove only outer code fence, keep inner code blocks
                parts = code_examples_content.split("```")
                if len(parts) >= 3:
                    # Remove first and last ```
                    code_examples_content = "```".join(parts[1:-1])

            return code_examples_content

        except Exception as e:
            logger.error(f"  ❌ Failed to generate code examples: {e}")
            # Return informative fallback when code generation fails
            return f"""
### 코드 예제: {section.title}

> **안내:** 이 섹션의 코드 예제는 자동 생성에 실패하여 표시되지 않았습니다.
> 강의 진행 시 관련 코드를 직접 시연하거나, 생성된 HTML 파일을 편집하여 코드를 추가하실 수 있습니다.

**이 섹션에서 다룰 주제:**
- {section.title}의 핵심 개념 구현
- 실전 활용 예제
- 주의사항 및 베스트 프랙티스

_(코드 생성 실패 원인: {str(e)[:100]})_
"""

