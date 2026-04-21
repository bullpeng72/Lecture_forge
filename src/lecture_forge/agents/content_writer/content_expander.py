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
    evaluate_content_quality,
)
from lecture_forge.utils.prompt_manager import load_prompt


def _format_context_with_metadata(documents: list, metadatas: list) -> str:
    """Format retrieved chunks with source metadata visible to the LLM (K2).

    Prepends a lightweight [Ref N/T type:X src:Y pN [lang]] header to each chunk
    so the LLM can reason about content provenance and source credibility.
    """
    if not documents:
        return "No additional context available."

    metas = metadatas if metadatas else [{}] * len(documents)
    parts = []
    for i, (doc, meta) in enumerate(zip(documents, metas), 1):
        meta = meta or {}
        source = meta.get("source", "")
        page   = meta.get("page_number") or meta.get("page") or meta.get("page_num")
        lang   = meta.get("language", "")
        stype  = meta.get("source_type", "")

        header_parts = [f"[Ref {i}/{len(documents)}]"]
        if stype:
            header_parts.append(f"type:{stype}")
        if source:
            # Shorten long paths / URLs to last path segment
            short_src = source.split("/")[-1] if "/" in source else source
            if len(short_src) > 50:
                short_src = "…" + short_src[-47:]
            header_parts.append(f"src:{short_src}")
        if page is not None:
            header_parts.append(f"p{page}")
        if lang and lang not in ("unknown", ""):
            header_parts.append(f"[{lang}]")

        header = " ".join(header_parts)
        parts.append(f"{header}\n{doc}")

    return "\n\n---\n\n".join(parts)


def _trim_contexts_by_tokens(
    documents: list,
    metadatas: list,
    max_tokens: int,
) -> tuple:
    """Trim context list to stay within token budget (M).

    Uses ~3 chars/token approximation (conservative for mixed KO/EN content).
    Preserves chunk order; stops adding once budget is exhausted.
    """
    total = 0
    kept_docs: list = []
    kept_metas: list = []
    metas = metadatas if metadatas else [{}] * len(documents)
    for doc, meta in zip(documents, metas):
        doc_tokens = max(1, len(doc) // 3)
        if total + doc_tokens > max_tokens:
            break
        kept_docs.append(doc)
        kept_metas.append(meta)
        total += doc_tokens
    if len(kept_docs) < len(documents):
        logger.debug(
            f"Token trim: kept {len(kept_docs)}/{len(documents)} chunks "
            f"(est. ~{total}/{max_tokens} tokens)"
        )
    return kept_docs, kept_metas


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
        super().__init__(model=model, temperature=temperature, thinking=False)
        self.vector_store = vector_store

    def expand_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        targets: dict,
        previous_content: str,
        previous_quality: dict,
        context_metadatas: list = None,
    ) -> str:
        """Expand content (wrapper for compatibility)."""
        return self._expand_content(
            section, curriculum, contexts, targets,
            previous_content, previous_quality, context_metadatas,
        )

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
        context_metadatas: list = None,
    ) -> str:
        """Expand insufficient content to meet requirements."""
        shortfalls = []

        if previous_quality["word_count"] < targets["min_words"]:
            shortfalls.append(
                f"- Words: {previous_quality['word_count']} / {targets['min_words']} (need {targets['min_words'] - previous_quality['word_count']} more)"
            )

        if previous_quality["subsection_count"] < targets["min_subsections"]:
            shortfalls.append(f"- Subsections: {previous_quality['subsection_count']} / {targets['min_subsections']}")

        shortfall_text = "\n".join(shortfalls)

        # Fetch additional chunks from the vector DB to supplement the initial context.
        # L2: use an intent-aware expansion query ("in-depth explanation tutorial")
        # to surface tutorial/walkthrough-style chunks missed by the initial retrieval.
        extra_chunks: List[str] = []
        extra_metas: List[dict] = []
        if self.vector_store:
            try:
                # L2: intent-aware expansion query (targets tutorial/walkthrough chunks)
                expansion_query = f"in-depth explanation tutorial: {' '.join(section.topics)}"
                extra_results = self.vector_store.query(
                    expansion_query, n_results=10
                )
                extra_docs = (extra_results.get("documents") or [[]])[0]
                extra_ids  = (extra_results.get("ids")       or [[]])[0]
                extra_meta = (extra_results.get("metadatas") or [[]])[0]
                # Exclude chunks already in the initial context (approximate by content)
                existing_content = set(contexts)
                for doc, cid, emeta in zip(extra_docs, extra_ids, extra_meta):
                    if doc not in existing_content:
                        extra_chunks.append(doc)
                        extra_metas.append(emeta or {})
                if extra_chunks:
                    logger.info(
                        f"     🔍 ContentExpander: fetched {len(extra_chunks)} additional chunks from KB"
                    )
            except Exception as e:
                logger.debug(f"ContentExpander re-query failed (non-critical): {e}")

        # Combine original contexts with freshly fetched ones (originals first for relevance)
        combined_contexts = list(contexts) + extra_chunks
        # K2: pair contexts with metadata (extra chunks get empty meta if not available)
        combined_metas = list(context_metadatas or []) + extra_metas
        # Pad metadatas if shorter than contexts (shouldn't happen but be safe)
        if len(combined_metas) < len(combined_contexts):
            combined_metas += [{}] * (len(combined_contexts) - len(combined_metas))
        # M: token-aware trimming instead of fixed [:20] slice
        combined_contexts, combined_metas = _trim_contexts_by_tokens(
            combined_contexts, combined_metas, Config.RAG_MAX_CONTEXT_TOKENS
        )
        # K2: format with source metadata so LLM sees provenance
        context_text = _format_context_with_metadata(combined_contexts, combined_metas) if combined_contexts else ""

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
            "depth_words": int(word_gap * 0.55),
            "pitfall_words": int(word_gap * 0.15),
            "best_practice_words": int(word_gap * 0.15),
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("content_expansion", **template_vars)

        try:
            logger.debug(f"     Sending expansion prompt ({len(prompt)} chars)")

            response = self.invoke_llm(prompt, phase="content_expansion")
            expanded = self._strip_meta_commentary(response.content.strip())
            expanded = self._deduplicate_headings(expanded, previous_content)

            # Validate expansion actually happened
            if len(expanded) <= len(previous_content):
                logger.warning(f"     ⚠️ Expansion failed - response is not longer than original")
                logger.warning(f"        Original: {len(previous_content)} chars, Expanded: {len(expanded)} chars")
                return previous_content

            # Re-evaluate
            image_count = self._count_images(expanded)
            new_quality = evaluate_content_quality(
                content=expanded,
                targets=targets,
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


    def _strip_meta_commentary(self, content: str) -> str:
        """Remove LLM meta-commentary about word counts or expansion status from output."""
        import re
        patterns = [
            r'이제\s+추가된\s+내용으로\s+인해[^\n]*\n?',
            r'이제\s+[\d,]+\s*단어[^\n]*\n?',
            r'총\s+[\d,]+\s*단어[^\n]*초과[^\n]*\n?',
            r'전체\s+글의?\s*길이가[^\n]*\n?',
            r'추가된\s+내용[^\n]*단어[^\n]*\n?',
            r'단어\s*수가[^\n]*초과[^\n]*\n?',
        ]
        stripped = content
        for pat in patterns:
            stripped = re.sub(pat, '', stripped, flags=re.MULTILINE | re.IGNORECASE)
        stripped = stripped.strip()
        if stripped != content:
            logger.debug("     🧹 Stripped meta-commentary from expanded content")
        return stripped

    def _deduplicate_headings(self, expanded: str, previous_content: str) -> str:
        """Remove heading blocks from expanded that already appear in previous_content.

        A heading block is the heading line plus all lines up to the next heading
        at the same or higher level. Only exact-match heading texts are removed,
        so similar-but-different headings are preserved.
        """
        import re

        heading_re = re.compile(r"^(#{1,4})\s+(.+)", re.MULTILINE)

        # Collect normalised headings already in previous_content
        existing = {
            m.group(2).strip().lower()
            for m in heading_re.finditer(previous_content)
        }
        if not existing:
            return expanded

        lines = expanded.splitlines(keepends=True)
        result = []
        skip_until_level: int = None  # skip lines until we see a heading ≤ this level

        for line in lines:
            m = heading_re.match(line)
            if m:
                level = len(m.group(1))
                text = m.group(2).strip().lower()

                # If we were skipping a block, stop when we hit a heading at same/higher level
                if skip_until_level is not None and level <= skip_until_level:
                    skip_until_level = None

                if skip_until_level is None and text in existing:
                    skip_until_level = level  # start skipping this block
                    continue

            if skip_until_level is not None:
                continue
            result.append(line)

        deduped = "".join(result).strip()
        if deduped != expanded.strip():
            logger.debug("     🧹 Removed duplicate heading blocks from expanded content")
        return deduped

    def _count_images(self, markdown: str) -> int:
        """Count the number of images in markdown content."""
        import re
        # Match markdown image syntax: ![alt](url)
        image_pattern = r'!\[.*?\]\(.*?\)'
        matches = re.findall(image_pattern, markdown)
        return len(matches)

