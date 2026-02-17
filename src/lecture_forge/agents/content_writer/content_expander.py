"""
Content Expander - Handles content expansion and quality improvement.
"""

from typing import List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.utils import logger
from lecture_forge.utils.content_metrics import (
    calculate_target_metrics,
    evaluate_content_quality,
    format_quality_report,
)
from lecture_forge.utils.prompt_manager import load_prompt


class ContentExpander(BaseAgent):
    """Handles content expansion to meet quality targets."""

    def __init__(self, vector_store: VectorStore = None, model: str = None, temperature: float = None):
        """
        Initialize ContentExpander.

        Args:
            vector_store: Vector store for RAG queries
            model: LLM model name (default: Config.DEFAULT_MODEL)
            temperature: Temperature for LLM (default: Config.TEMPERATURE)
        """
        super().__init__(model=model, temperature=temperature)
        self.vector_store = vector_store

    def expand_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        targets: dict,
        previous_content: str,
        previous_quality: dict,
    ) -> str:
        """Expand content (wrapper for compatibility)."""
        return self._expand_content(section, curriculum, contexts, targets, previous_content, previous_quality)

    def count_images(self, markdown: str) -> int:
        """Count images (wrapper for compatibility)."""
        return self._count_images(markdown)

    def _expand_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        targets: dict,
        previous_content: str,
        previous_quality: dict,
    ) -> str:
        """Expand insufficient content to meet requirements."""
        shortfalls = []

        if previous_quality["word_count"] < targets["min_words"]:
            shortfalls.append(
                f"- Words: {previous_quality['word_count']} / {targets['min_words']} (need {targets['min_words'] - previous_quality['word_count']} more)"
            )

        if previous_quality["code_block_count"] < targets["min_code_examples"]:
            shortfalls.append(f"- Code examples: {previous_quality['code_block_count']} / {targets['min_code_examples']}")

        if previous_quality["subsection_count"] < targets["min_subsections"]:
            shortfalls.append(f"- Subsections: {previous_quality['subsection_count']} / {targets['min_subsections']}")

        shortfall_text = "\n".join(shortfalls)

        # Use more contexts for expansion (10 instead of 8)
        context_text = "\n\n---\n\n".join(contexts[:10]) if contexts else ""

        word_gap = targets["target_words"] - previous_quality["word_count"]

        # Prepare template variables
        template_vars = {
            "shortfall_text": shortfall_text,
            "current_word_count": previous_quality["word_count"],
            "min_words": targets["min_words"],
            "target_words": targets["target_words"],
            "word_gap": word_gap,
            "section_title": section.title,
            "estimated_time": section.estimated_time,
            "previous_content": previous_content,
            "depth_words": int(word_gap * 0.4),
            "code_words": int(word_gap * 0.3),
            "pitfall_words": int(word_gap * 0.15),
            "best_practice_words": int(word_gap * 0.15),
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("content_expansion", **template_vars)

        try:
            logger.debug(f"     Sending expansion prompt ({len(prompt)} chars)")

            response = self.invoke_llm(prompt, phase="content_expansion")
            expanded = response.content.strip()

            # Validate expansion actually happened
            if len(expanded) <= len(previous_content):
                logger.warning(f"     ⚠️ Expansion failed - response is not longer than original")
                logger.warning(f"        Original: {len(previous_content)} chars, Expanded: {len(expanded)} chars")
                return previous_content

            # Re-evaluate
            code_blocks = self._extract_code_blocks(expanded)
            image_count = self._count_images(expanded)
            new_quality = evaluate_content_quality(
                content=expanded,
                targets=targets,
                code_block_count=len(code_blocks),
                image_count=image_count,
            )

            word_increase = new_quality["word_count"] - previous_quality["word_count"]
            logger.info(
                f"     ✅ Expansion succeeded: +{word_increase} words ({previous_quality['word_count']} → {new_quality['word_count']})"
            )
            logger.info(f"     📊 Expanded quality score: {new_quality['overall_score']}/100")

            return expanded

        except Exception as e:
            logger.error(f"     ❌ Error expanding content: {type(e).__name__}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return previous_content  # Return original on error


    def _extract_code_blocks(self, markdown: str) -> list:
        """Extract fenced code blocks from markdown (used for quality re-evaluation)."""
        import re
        return re.findall(r"```[\w]*\n.*?```", markdown, re.DOTALL)

    def _count_images(self, markdown: str) -> int:
        """Count the number of images in markdown content."""
        import re
        # Match markdown image syntax: ![alt](url)
        image_pattern = r'!\[.*?\]\(.*?\)'
        matches = re.findall(image_pattern, markdown)
        return len(matches)

