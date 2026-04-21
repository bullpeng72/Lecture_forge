"""
Content Writer Agent - Orchestrates lecture content generation with RAG.

This is the refactored version with extracted components:
- ImageSelector: Handles image selection logic
- CodeGenerator: Handles code extraction and generation
- ContentExpander: Handles content expansion
"""

from pathlib import Path
from typing import List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.agents.content_writer.code_generator import extract_code_blocks
from lecture_forge.agents.content_writer.content_expander import (
    ContentExpander,
    _format_context_with_metadata,
    _trim_contexts_by_tokens,
)
from lecture_forge.agents.content_writer.image_selector import ImageSelector
from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import ImageReference, SectionContent
from lecture_forge.utils import logger
from lecture_forge.utils.content_metrics import (
    calculate_target_metrics,
    evaluate_content_quality,
    format_quality_report,
)
from lecture_forge.utils.language_utils import detect_language
from lecture_forge.utils.prompt_manager import load_prompt


def parse_markdown_subsections(markdown: str) -> list:
    """
    v0.4.0: Split markdown into subsections based on ## / ### headings.

    Returns a list of dicts:
        [{"heading": "## 소제목", "heading_text": "소제목", "level": 2, "content": "..."}, ...]

    If no headings are found, the entire markdown is returned as a single subsection
    with an empty heading so the caller can treat it uniformly.
    """
    import re as _re

    pattern = _re.compile(r"^(#{2,3})\s+(.+)$", _re.MULTILINE)
    matches = list(pattern.finditer(markdown))

    if not matches:
        return [{"heading": "", "heading_text": "", "level": 2, "content": markdown}]

    subsections = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        subsections.append(
            {
                "heading": match.group(0),         # "## 소제목"
                "heading_text": match.group(2),    # "소제목"
                "level": len(match.group(1)),       # 2 or 3
                "content": markdown[start:end].strip(),
            }
        )

    return subsections


def _build_practice_fail_condition(require_practice: bool) -> str:
    if require_practice:
        return "3. ❌ NO PRACTICE PROBLEMS → REJECTED AND YOU WILL BE FIRED"
    return "3. ℹ️ Practice problems are not required for this section."


def _build_practice_requirement_section(require_practice: bool, target_practice_problems: int) -> str:
    if require_practice:
        return f"""4. **Practice Problems: {target_practice_problems}+ detailed exercises**
   - **Each problem: 100-150 words description**
   - Clear problem statement (what needs to be solved)
   - Requirements specification (3-5 requirements)
   - Difficulty level indicator (쉬움/보통/어려움)
   - 2-3 hints or guidance points
   - Expected outcome and success criteria
   - Bonus challenges for advanced learners"""
    return "4. **Practice Problems**: Not required for this section."


def _build_practice_checklist_item(require_practice: bool, target_practice_problems: int) -> str:
    if require_practice:
        return (
            f"✅ **Practice Problems**: I included {target_practice_problems}+ detailed problems\n"
            "   - Each 100-150 words with hints and requirements"
        )
    return "✅ **Practice Problems**: N/A (not required for this section)"


def _filter_chunks_by_similarity(
    docs: list,
    metas: list,
    ids: list,
    distances: list,
) -> tuple:
    """Filter retrieved chunks by similarity threshold (F).

    ChromaDB uses L2 distance (lower = more similar).
    Converts to similarity: similarity = max(0, 1 - distance / 2).
    Retains chunks with similarity >= RAG_SIMILARITY_THRESHOLD.
    Always keeps at least RAG_MIN_FALLBACK_RESULTS chunks (by best similarity).
    """
    if not docs or not distances:
        return docs, metas, ids

    threshold = Config.RAG_SIMILARITY_THRESHOLD     # default 0.3
    min_keep = Config.RAG_MIN_FALLBACK_RESULTS       # default 3

    # Pair with similarity scores (ChromaDB already sorts by distance)
    scored = [
        (max(0.0, 1.0 - d / 2.0), doc, meta, cid)
        for d, doc, meta, cid in zip(distances, docs, metas, ids)
    ]

    # Filter below threshold
    filtered = [(sim, doc, meta, cid) for sim, doc, meta, cid in scored if sim >= threshold]

    # Guarantee minimum results regardless of threshold
    if len(filtered) < min_keep:
        filtered = scored[:min_keep]

    f_docs  = [doc for _, doc, _, _  in filtered]
    f_metas = [meta for _, _, meta, _ in filtered]
    f_ids   = [cid for _, _, _, cid  in filtered]
    return f_docs, f_metas, f_ids


# LLM refusal patterns (case-insensitive prefix match)
_LLM_REFUSAL_PREFIXES = (
    "i'm sorry, but i can't",
    "i'm sorry, i can't",
    "i cannot assist with",
    "i apologize, but i cannot",
    "i'm unable to assist",
    "죄송합니다, 저는",
    "죄송하지만 저는",
)


def _build_structural_section_prompt(
    section_title: str,
    section_type: str,
    topic: str,
    audience_level: str,
    estimated_time: int,
    topics_list: str,
    learning_outcomes_list: str,
    min_words: int,
    target_words: int,
    context_text: str,
    language_instruction: str,
) -> str:
    """Build a safe, non-threatening prompt for structural sections (intro/conclusion)."""

    if section_type == "conclusion":
        structure_guide = """
### Structure to follow:

## 핵심 내용 요약 / Key Takeaways
(Bullet list summarizing the main points covered in the lecture)

## 학습 목표 달성 / Learning Objectives Review
(Brief review of how each learning objective was addressed)

## 실무 적용 / Practical Application
(2-3 concrete ways learners can apply what they learned)

## 다음 단계 / Next Steps
(3-5 recommended resources, topics, or actions for further learning)

## 마무리 / Closing Remarks
(2-3 sentences wrapping up the lecture warmly and encouragingly)"""
    else:
        structure_guide = """
### Structure to follow:

## 강의 개요 / Lecture Overview
(Brief overview of what this lecture covers and why it matters)

## 학습 목표 / Learning Objectives
(Clear list of what learners will be able to do after this lecture)

## 사전 지식 / Prerequisites
(What learners should already know before starting)

## 강의 구성 / Structure Preview
(Brief preview of the sections and topics to be covered)"""

    return f"""You are an expert educator writing a lecture section in {language_instruction}.

## Task
Write the {section_type} section for a lecture on: **{topic}**

## Section Information
- Section Title: {section_title}
- Section Type: {section_type.capitalize()}
- Target Audience: {audience_level}
- Estimated Time: {estimated_time} minutes
- Topics: {topics_list}

## Learning Outcomes
{learning_outcomes_list}

## Reference Material (from lecture knowledge base)
{context_text}

## Word Count Requirements
- Minimum: {min_words} words
- Target: {target_words} words
{structure_guide}

## Formatting Rules
- Use ## for main headings, ### for sub-headings (never use # H1)
- Write in {language_instruction}
- Be clear, engaging, and appropriate for {audience_level}-level learners
- Do not include code examples in this section

Write the complete {section_type} section now:"""


class ContentWriterAgent(BaseAgent):
    """Agent for writing lecture content with RAG."""

    def __init__(self, vector_store: VectorStore = None) -> None:
        """
        Initialize Content Writer Agent.

        Args:
            vector_store: Vector store for RAG queries
        """
        super().__init__(thinking=False)  # per-section calls: speed > deep reasoning
        logger.info("Initializing Content Writer Agent")
        self.vector_store = vector_store

        # Global image tracking for deduplication across sections
        self.used_image_ids = set()
        self.image_usage_count = {}
        # Coverage tracking: chunk IDs referenced across all sections
        self.used_chunk_ids: set = set()

        # Initialize helper components
        self.image_selector = ImageSelector(
            keyword_expander=self._expand_keywords,
            keyword_translator=self._get_keyword_translations
        )
        self.content_expander = ContentExpander(vector_store=vector_store)

    def write_all_sections(
        self,
        curriculum: Curriculum,
        available_images: List[dict] = None,
    ) -> List[SectionContent]:
        """
        Write content for all sections in curriculum with global image deduplication.

        Args:
            curriculum: Curriculum plan
            available_images: List of available images with metadata

        Returns:
            List of section contents
        """
        logger.info(f"📝 Writing content for {len(curriculum.sections)} sections with image deduplication")

        section_contents = []

        # Initialize global tracking
        self.used_image_ids.clear()
        self.image_usage_count.clear()
        self.used_chunk_ids.clear()

        # v0.5.1: Pre-assign all KB chunks to sections (Push strategy)
        if self.vector_store:
            self._pre_assign_chunks_to_sections(curriculum)

        for i, section in enumerate(curriculum.sections):
            logger.info(f"\n{'='*60}")
            logger.info(f"Section {i+1}/{len(curriculum.sections)}: {section.title}")
            logger.info(f"{'='*60}")

            # Filter available images (exclude already used ones)
            available_for_section = [img for img in (available_images or []) if img.get("id") not in self.used_image_ids]

            logger.info(
                f"   📷 Available images: {len(available_for_section)} " f"(filtered from {len(available_images or [])})"
            )

            total_sections = len(curriculum.sections)
            section_position = i / max(1, total_sections - 1) if total_sections > 1 else 0.5

            content = self.write_section(
                section=section,
                curriculum=curriculum,
                available_images=available_for_section,
                section_position=section_position,
            )

            # Track used images
            for img_ref in content.images:
                self.used_image_ids.add(img_ref.image_id)
                self.image_usage_count[img_ref.image_id] = self.image_usage_count.get(img_ref.image_id, 0) + 1

            logger.info(f"   ✅ Used {len(content.images)} images in this section")
            logger.info(f"   📊 Total unique images used so far: {len(self.used_image_ids)}")

            section_contents.append(content)

        # ── Coverage sweep: expand under-represented sections with unused KB chunks ──
        if self.vector_store:
            try:
                total_chunks = int(self.vector_store.get_total_chunk_count())
            except (TypeError, ValueError):
                total_chunks = 0
            if total_chunks > 0:
                coverage_ratio = len(self.used_chunk_ids) / total_chunks
                logger.info(f"\n📊 KB Coverage: {len(self.used_chunk_ids)}/{total_chunks} chunks used "
                            f"({coverage_ratio:.1%}) — target ≥ {Config.RAG_COVERAGE_MIN_RATIO:.0%}")

                for _round in range(2):
                    coverage_ratio = len(self.used_chunk_ids) / max(1, total_chunks)
                    if coverage_ratio >= Config.RAG_COVERAGE_MIN_RATIO:
                        break
                    logger.info(
                        f"   ⚡ Coverage sweep round {_round + 1} "
                        f"(current: {coverage_ratio:.1%}, target: {Config.RAG_COVERAGE_MIN_RATIO:.0%})..."
                    )
                    self._expand_sections_for_coverage(section_contents, curriculum)
                    new_coverage = len(self.used_chunk_ids) / max(1, total_chunks)
                    logger.info(f"   📈 Sweep round {_round + 1}: coverage = {new_coverage:.1%}")

        # Final statistics
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Image Usage Statistics:")
        logger.info(f"{'='*60}")
        logger.info(f"   • Total images available: {len(available_images or [])}")
        logger.info(f"   • Unique images used: {len(self.used_image_ids)}")
        logger.info(f"   • Images reused: {sum(1 for c in self.image_usage_count.values() if c > 1)}")
        logger.info(f"   • Unused images: {len(available_images or []) - len(self.used_image_ids)}")

        logger.info(f"Completed writing {len(section_contents)} sections")
        return section_contents


    def write_section(
        self,
        section: Section,
        curriculum: Curriculum,
        available_images: List[dict] = None,
        section_position: float = None,
    ) -> SectionContent:
        """
        Write content for a single section using RAG.

        Args:
            section: Section to write content for
            curriculum: Full curriculum for context
            available_images: Available images

        Returns:
            Section content
        """
        # 1. RAG query to get relevant context
        contexts, context_metadatas = self._query_knowledge(section, curriculum)

        # 2. Estimate image count for quality evaluation (section-level upper bound)
        max_section_images = max(3, section.estimated_time // 8)
        pre_image_count = min(max_section_images, len(available_images or []))

        # 3. Generate markdown content with LLM
        markdown_content = self._generate_content(
            section=section,
            curriculum=curriculum,
            contexts=contexts,
            available_image_count=pre_image_count,
            context_metadatas=context_metadatas,
        )

        # 4. Extract code blocks (if any)
        code_blocks = extract_code_blocks(markdown_content)

        # 5. Count words
        word_count = len(markdown_content.split())

        # 6. v0.5.0: Subsection-level image selection
        subsections = parse_markdown_subsections(markdown_content)
        subsection_images: dict = {s["heading"]: [] for s in subsections}
        all_images: List = []
        remaining_images = list(available_images or [])

        for sub in subsections:
            # Enforce section-level cap: stop once max_section_images is reached
            if len(all_images) >= max_section_images:
                break
            sub_imgs = self.image_selector.select_images_for_subsection(
                subsection_heading=sub["heading_text"],
                subsection_content=sub["content"],
                section=section,
                available_images=remaining_images,
                context_metadatas=context_metadatas,
                max_images=Config.IMAGE_MAX_PER_SUBSECTION,
                section_position=section_position,
            )
            if sub_imgs:
                subsection_images[sub["heading"]] = sub_imgs
                all_images.extend(sub_imgs)
                used_sub_ids = {img.image_id for img in sub_imgs}
                remaining_images = [img for img in remaining_images if img.get("id") not in used_sub_ids]

        # Final cap in case multiple subsections in one loop iteration would exceed the limit
        all_images = all_images[:max_section_images]

        # Minimum-image guarantee: long sections (≥2 subsections) that received 0 images
        # get up to 2 quality-matched fallback images from remaining_images.
        if len(all_images) == 0 and len(subsections) >= 2 and remaining_images:
            fallback = sorted(
                remaining_images,
                key=lambda img: img.get("quality_score", 0.0),
                reverse=True,
            )
            for fb_img in fallback[:2]:
                fb_id = fb_img.get("id", "")
                all_images.append(ImageReference(
                    image_id=fb_id,
                    path=fb_img.get("path", ""),
                    description=fb_img.get("description", ""),
                    caption=fb_img.get("alt_text", ""),
                    attribution=f"Source: {Path(fb_img.get('source', '')).name}",
                ))
            if all_images:
                logger.info(f"   🖼️  Minimum-image fallback: added {len(all_images)} quality images for zero-image section")

        logger.info(
            f"   🖼️  Subsection-level selection: {len(all_images)} images "
            f"across {len(subsections)} subsections (cap: {max_section_images})"
        )

        content = SectionContent(
            section_id=section.id,
            title=section.title,
            markdown_content=markdown_content,
            code_blocks=code_blocks,
            images=all_images,
            diagrams=[],  # Diagrams will be added by DiagramGenerator
            word_count=word_count,
            estimated_time=section.estimated_time,
            difficulty_level=section.difficulty_level,
            subsection_images=subsection_images,
            rag_key_chunks=contexts[:8],  # v0.5.0: preserve top chunks for DiagramGenerator
        )

        logger.info(f"Section '{section.title}': {word_count} words, {len(code_blocks)} code blocks, {len(all_images)} images")

        return content


    def _compute_dynamic_n_results(self, section: Section) -> int:
        """Compute RAG query chunk count scaled by section duration and difficulty (K).

        Formula: base × time_factor × difficulty_mult, clamped to [RAG_N_RESULTS_MIN, RAG_N_RESULTS_MAX].
        Baseline: 15 minutes → RAG_CONTENT_N_RESULTS chunks.
        """
        base = Config.RAG_CONTENT_N_RESULTS          # default 10
        time_factor = max(0.3, section.estimated_time / 15.0)
        difficulty = (getattr(section, "difficulty_level", None) or "intermediate").lower()
        mult = {"beginner": 0.8, "intermediate": 1.0, "advanced": 1.3}.get(difficulty, 1.0)
        n = int(base * time_factor * mult)
        result = max(Config.RAG_N_RESULTS_MIN, min(Config.RAG_N_RESULTS_MAX, n))
        logger.debug(
            f"   Dynamic n_results: base={base} × time_factor={time_factor:.1f} × diff_mult={mult} "
            f"→ {n} → clamped={result}"
        )
        return result

    def _rerank_by_metadata(
        self,
        all_docs: list,
        all_metas: list,
        section_language: str,
    ) -> tuple:
        """Re-rank retrieved chunks using metadata signals (G).

        Applies a language-match bonus: chunks in the same language as the section
        are promoted to the front so the LLM receives the most relevant signal first.
        Stable sort preserves the original similarity ordering within equal scores.
        """
        if not all_docs or not all_metas:
            return all_docs, all_metas

        lang_bonus = 0.1

        def meta_score(meta: dict) -> float:
            if not meta:
                return 0.0
            return lang_bonus if meta.get("language", "") == section_language else 0.0

        scored = [(meta_score(m), doc, m) for doc, m in zip(all_docs, all_metas)]
        scored.sort(key=lambda x: x[0], reverse=True)   # stable sort

        lang_matched = sum(1 for s, _, _ in scored if s > 0)
        if lang_matched > 0:
            logger.debug(
                f"   Metadata rerank: {lang_matched}/{len(all_docs)} chunks match "
                f"section language '{section_language}'"
            )

        return [doc for _, doc, _ in scored], [m for _, _, m in scored]

    def _distribute_images_to_subsections(
        self,
        images: List,
        subsections: list,
    ) -> dict:
        """
        v0.4.0: Distribute selected images to subsections using round-robin assignment.
        Kept as fallback; primary path is subsection-level selection in write_section().

        Returns:
            Dict mapping heading → List[ImageReference]
        """
        result = {s["heading"]: [] for s in subsections}
        if not images or not subsections:
            return result

        for i, img in enumerate(images):
            target_heading = subsections[i % len(subsections)]["heading"]
            result[target_heading].append(img)

        return result

    def _pre_assign_chunks_to_sections(self, curriculum: Curriculum) -> None:
        """v0.5.1: Pre-assign all KB chunks to sections (Push strategy).

        Performs one collection.get() call and routes each chunk to the content section
        whose title+topics keywords overlap most. Chunks with zero overlap are round-robin
        distributed. Result stored in curriculum.chunk_assignments (section_id → chunk texts).
        No LLM calls.
        """
        try:
            all_items = self.vector_store.collection.get(include=["documents", "ids"])
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.debug(f"Pre-assign KB get failed: {e}")
            return

        all_docs = all_items.get("documents") or []
        all_ids  = all_items.get("ids") or []

        content_sections = [
            s for s in curriculum.sections
            if not s.id.lower().endswith(("_intro", "_conclusion"))
        ]
        if not content_sections:
            return

        # Build keyword sets per section (title + all topics)
        section_kw = {
            s.id: set(
                w.lower()
                for t in ([s.title] + s.topics)
                for w in t.split()
                if len(w) > 1
            )
            for s in content_sections
        }

        assignments: dict = {s.id: [] for s in content_sections}
        tie_counter = 0

        for doc, doc_id in zip(all_docs, all_ids):
            if doc_id in self.used_chunk_ids:
                continue  # already used by RAG pull

            doc_words = set(w.lower() for w in doc.split() if len(w) > 1)
            scores = {sid: len(doc_words & kw) for sid, kw in section_kw.items()}
            max_score = max(scores.values(), default=0)

            if max_score == 0:
                # No keyword overlap → round-robin to ensure no chunk is abandoned
                best_sid = content_sections[tie_counter % len(content_sections)].id
                tie_counter += 1
            else:
                best_sid = max(scores, key=scores.get)

            assignments[best_sid].append(doc)

        curriculum.chunk_assignments = assignments
        total_assigned = sum(len(v) for v in assignments.values())
        logger.info(
            f"   📋 Pre-assigned {total_assigned}/{len(all_docs)} chunks "
            f"to {len(content_sections)} sections"
        )

    def _expand_sections_for_coverage(
        self,
        section_contents: List[SectionContent],
        curriculum: "Curriculum",
    ) -> None:
        """
        v0.5.1: Coverage sweep — append supplementary content from unused KB chunks.

        Retrieves chunks not yet referenced in this writing pass, groups them by
        similarity to existing sections (simple keyword overlap), and appends a
        short supplementary paragraph to the best-matching section's markdown.

        The sections list is modified in-place.
        """
        if not self.vector_store:
            return

        try:
            result = self.vector_store.get_unused_chunks(self.used_chunk_ids, n=2000)
            unused_docs, unused_metas = result
        except (TypeError, ValueError, Exception):
            return
        if not unused_docs:
            logger.info("   ✅ No unused chunks found — KB fully covered")
            return

        logger.info(f"   📦 {len(unused_docs)} unused chunks to distribute across sections")

        # Skip structural sections (intro/conclusion) for expansion
        content_indices = [
            i for i, sc in enumerate(section_contents)
            if not sc.section_id.lower().endswith("_intro")
            and not sc.section_id.lower().endswith("_conclusion")
        ]
        if not content_indices:
            return

        # v0.5.1: Use chunk_assignments for precise routing when available
        has_assignments = (
            hasattr(curriculum, "chunk_assignments") and curriculum.chunk_assignments
        )

        if has_assignments:
            # chunk_assignments path: each section pulls its own pre-assigned unused chunks
            for sec_idx in content_indices:
                sc = section_contents[sec_idx]
                sec_obj = curriculum.sections[sec_idx] if sec_idx < len(curriculum.sections) else None
                if not sec_obj:
                    continue
                pre_set = set(curriculum.chunk_assignments.get(sec_obj.id, []))
                unused_for_sec = [d for d in unused_docs if d in pre_set][:5]
                if not unused_for_sec:
                    continue
                supp = self._generate_supplementary_content(sc, unused_for_sec)
                if supp:
                    sc.markdown_content = sc.markdown_content.rstrip() + "\n\n" + supp
                    sc.word_count = len(sc.markdown_content.split())
                    logger.info(
                        f"   📝 Expanded '{sc.title}' with {len(unused_for_sec)} supplementary chunks"
                    )
        else:
            # Fallback: keyword-overlap routing (legacy)
            section_topic_sets = [
                set(" ".join(sc.title.lower().split() + [t.lower() for t in (
                    curriculum.sections[i].topics if i < len(curriculum.sections) else []
                )]))
                for i, sc in enumerate(section_contents)
            ]
            section_chunks: dict = {i: [] for i in content_indices}
            for doc, meta in zip(unused_docs, unused_metas):
                doc_words = set(doc.lower().split())
                best_idx = max(
                    content_indices,
                    key=lambda i: len(doc_words & section_topic_sets[i]),
                )
                section_chunks[best_idx].append(doc)
                if meta and meta.get("id"):
                    self.used_chunk_ids.add(meta["id"])

            for sec_idx, chunks in section_chunks.items():
                if not chunks:
                    continue
                sc = section_contents[sec_idx]
                supp = self._generate_supplementary_content(sc, chunks)
                if supp:
                    sc.markdown_content = sc.markdown_content.rstrip() + "\n\n" + supp
                    sc.word_count = len(sc.markdown_content.split())
                    logger.info(
                        f"   📝 Expanded '{sc.title}' with {len(chunks)} supplementary chunks"
                    )

    def _generate_supplementary_content(
        self,
        section_content: SectionContent,
        extra_chunks: List[str],
    ) -> str:
        """
        Generate a short supplementary paragraph from unused KB chunks.

        Uses a lightweight LLM call to produce 150–300 words of additional depth
        for the given section, grounded in the extra_chunks context.
        """
        context = "\n\n---\n\n".join(chunk[:400] for chunk in extra_chunks[:5])
        prompt = f"""다음은 '{section_content.title}' 섹션에 아직 다루지 않은 보충 자료입니다.

**보충 자료:**
{context}

위 자료를 바탕으로, 이미 작성된 섹션 내용을 깊이 있게 보완하는 **150~300단어** 분량의 보충 내용을 한국어로 작성하세요.
- 기존 내용과 중복 없이 새로운 관점이나 세부사항 추가
- ### 소제목으로 시작 (예: ### 추가 고려사항 또는 ### 심화 개념)
- 핵심 개념은 **굵게** 강조
- 간결하고 교육적으로 작성

보충 내용만 출력하세요 (제목 포함, 다른 설명 불필요):"""

        try:
            response = self.invoke_llm(prompt, phase="coverage_expansion")
            content = response.content.strip()
            # Strip accidental markdown fences
            if content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            return content
        except (RuntimeError, ValueError) as e:
            logger.debug(f"Coverage expansion LLM call failed: {e}")
            return ""

    def _query_knowledge(self, section: Section, curriculum: "Curriculum | None" = None) -> tuple:
        """Query vector DB with per-subtopic, cross-lingual, and fallback queries.

        Improvements applied (F/K/H/G/I):
          F – Similarity threshold filtering (RAG_SIMILARITY_THRESHOLD)
          K – Dynamic n_results scaled by section duration × difficulty
          H – Bidirectional cross-lingual: KO↔EN, not just KO→EN
          G – Metadata reranking: language-matched chunks promoted
          I – Sparse fallback: broadened queries if < RAG_SPARSE_THRESHOLD chunks

        Returns:
            Tuple of (documents, metadatas) for RAG context and location-based image matching.
        """
        if not self.vector_store:
            return [], []

        _sid = section.id.lower()
        is_structural = _sid.endswith("_intro") or _sid.endswith("_conclusion")

        # K: compute dynamic n_results for this section
        dynamic_n = self._compute_dynamic_n_results(section)

        # ── Structural sections: single enriched query ───────────────────────
        if is_structural and curriculum:
            content_titles = [
                s.title for s in curriculum.sections
                if not s.id.lower().endswith("_intro")
                and not s.id.lower().endswith("_conclusion")
            ]
            query = curriculum.topic + " " + " ".join(content_titles[:4])
            logger.info(f"   🔍 Structural section RAG query (enriched): '{query[:80]}'")
            try:
                results = self.vector_store.query(query, n_results=dynamic_n)
                if results and results["documents"]:
                    docs  = results["documents"][0]
                    metas = results.get("metadatas", [[]])[0]
                    ids   = results.get("ids", [[]])[0]
                    dists = results.get("distances", [[]])[0]
                    # F: filter by similarity threshold
                    docs, metas, ids = _filter_chunks_by_similarity(docs, metas, ids, dists)
                    # M: token-aware trimming for structural sections too
                    docs, metas = _trim_contexts_by_tokens(docs, metas, Config.RAG_MAX_CONTEXT_TOKENS)
                    return docs, metas
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.warning(f"Error querying vector DB for structural section: {e}")
            return [], []

        # ── Content sections: per-subtopic + cross-lingual + fallback ────────
        seen_ids: set = set()
        all_docs: list = []
        all_metas: list = []

        # Detect section language once (for cross-lingual + reranking)
        _lang_text = (
            " ".join(curriculum.learning_objectives)
            if (curriculum and curriculum.learning_objectives)
            else section.title
        )
        section_language = detect_language(_lang_text)

        # Number of results per individual sub-topic query
        per_query = max(4, dynamic_n // max(1, len(section.topics)))

        # ── Step 1: Per-subtopic queries with intent variants (L2) + similarity filter (F) ──
        # L2: two intent-aware query formulations per topic improve retrieval diversity:
        #   - conceptual: retrieves definitions, explanations, theory
        #   - practical:  retrieves tutorials, examples, implementation walkthroughs
        for sub_topic in section.topics:
            query_variants = [
                sub_topic,                                       # conceptual
                f"{sub_topic} example application tutorial",     # practical (L2)
            ]
            for query_str in query_variants:
                try:
                    results = self.vector_store.query(query_str, n_results=per_query)
                    docs  = (results.get("documents")  or [[]])[0]
                    metas = (results.get("metadatas")  or [[]])[0]
                    ids   = (results.get("ids")         or [[]])[0]
                    dists = (results.get("distances")   or [[]])[0]
                    # F: filter low-relevance chunks
                    docs, metas, ids = _filter_chunks_by_similarity(docs, metas, ids, dists)
                    for doc, meta, cid in zip(docs, metas, ids):
                        if cid not in seen_ids:
                            seen_ids.add(cid)
                            all_docs.append(doc)
                            all_metas.append(meta)
                except (RuntimeError, ValueError, AttributeError) as e:
                    logger.debug(f"Sub-topic query failed for '{query_str}': {e}")

        logger.info(
            f"   🔍 Per-subtopic RAG ({len(section.topics)} topics × 2 intents × {per_query}): "
            f"{len(all_docs)} unique chunks (post similarity-filter)"
        )

        # ── Step 2: Bidirectional cross-lingual query (H) ────────────────────
        try:
            from lecture_forge.utils.language_utils import translate_text
            topics_str = " ".join(section.topics)
            if section_language == "ko":
                translated_query = translate_text(topics_str, target_language="en")
                cross_label = "EN"
            else:
                translated_query = translate_text(topics_str, target_language="ko")
                cross_label = "KO"

            if translated_query and translated_query != topics_str:
                xresults = self.vector_store.query(translated_query, n_results=per_query)
                xdocs  = (xresults.get("documents")  or [[]])[0]
                xmetas = (xresults.get("metadatas")  or [[]])[0]
                xids   = (xresults.get("ids")         or [[]])[0]
                xdists = (xresults.get("distances")   or [[]])[0]
                # F: filter cross-lingual results too
                xdocs, xmetas, xids = _filter_chunks_by_similarity(xdocs, xmetas, xids, xdists)
                added = 0
                for doc, meta, cid in zip(xdocs, xmetas, xids):
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        all_docs.append(doc)
                        all_metas.append(meta)
                        added += 1
                if added:
                    logger.info(f"   🌐 Cross-lingual ({cross_label}) query added {added} chunks")
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.debug(f"Cross-lingual query failed (non-critical): {e}")

        # ── Step 3: Sparse fallback queries (I) ──────────────────────────────
        if len(all_docs) < Config.RAG_SPARSE_THRESHOLD and curriculum:
            logger.info(
                f"   ⚠️ Sparse RAG ({len(all_docs)} chunks < {Config.RAG_SPARSE_THRESHOLD}) "
                f"— running fallback queries"
            )
            fallback_queries = [section.title, curriculum.topic]
            for fq in fallback_queries:
                try:
                    fresults = self.vector_store.query(fq, n_results=per_query)
                    fdocs  = (fresults.get("documents")  or [[]])[0]
                    fmetas = (fresults.get("metadatas")  or [[]])[0]
                    fids   = (fresults.get("ids")         or [[]])[0]
                    fdists = (fresults.get("distances")   or [[]])[0]
                    fdocs, fmetas, fids = _filter_chunks_by_similarity(fdocs, fmetas, fids, fdists)
                    added = 0
                    for doc, meta, cid in zip(fdocs, fmetas, fids):
                        if cid not in seen_ids:
                            seen_ids.add(cid)
                            all_docs.append(doc)
                            all_metas.append(meta)
                            added += 1
                    if added:
                        logger.info(f"   🔄 Fallback '{fq[:50]}' added {added} chunks")
                    if len(all_docs) >= Config.RAG_SPARSE_THRESHOLD:
                        break
                except (RuntimeError, ValueError, AttributeError) as e:
                    logger.debug(f"Fallback query failed for '{fq}': {e}")

            if len(all_docs) < Config.RAG_SPARSE_THRESHOLD:
                logger.warning(
                    f"   ⚠️ Sparse KB coverage for '{section.title}': "
                    f"only {len(all_docs)} chunks after all fallbacks"
                )

        # ── Step 4: Metadata reranking — language-matched chunks first (G) ───
        all_docs, all_metas = self._rerank_by_metadata(all_docs, all_metas, section_language)

        # Cap is computed early so Step 5 can check against it
        cap = dynamic_n * 2

        # ── Step 5: Source diversity — include chunks from underrepresented sources (v0.4.0) ──
        if curriculum and hasattr(curriculum, "source_files") and curriculum.source_files:
            seen_sources = {m.get("source", "") for m in all_metas if m}
            for source_path in curriculum.source_files:
                if source_path and source_path not in seen_sources and len(all_docs) < cap:
                    try:
                        src_results = self.vector_store.query(
                            section.title,
                            n_results=3,
                            where={"source": source_path},
                        )
                        src_docs  = (src_results.get("documents")  or [[]])[0]
                        src_metas = (src_results.get("metadatas")  or [[]])[0]
                        src_ids   = (src_results.get("ids")         or [[]])[0]
                        added = 0
                        for doc, meta, cid in zip(src_docs, src_metas, src_ids):
                            if cid not in seen_ids and len(all_docs) < cap:
                                seen_ids.add(cid)
                                all_docs.append(doc)
                                all_metas.append(meta)
                                added += 1
                        if added:
                            seen_sources.add(source_path)
                            from pathlib import Path as _Path
                            logger.info(
                                f"   📎 Source-diversity: +{added} chunks from "
                                f"'{_Path(source_path).name}'"
                            )
                    except (RuntimeError, ValueError) as e:
                        logger.debug(f"Source-diversity where-filter skipped for '{source_path}': {e}")
        # v0.5.1: Inject pre-assigned chunks not yet pulled by RAG (Push補완)
        if curriculum and hasattr(curriculum, "chunk_assignments") and curriculum.chunk_assignments:
            pre_chunks = curriculum.chunk_assignments.get(section.id, [])
            injected = 0
            for chunk in pre_chunks:
                if chunk not in all_docs and len(all_docs) < cap * 2:
                    all_docs.append(chunk)
                    all_metas.append({})
                    injected += 1
            if injected:
                logger.info(f"   💉 Injected {injected} pre-assigned chunks for '{section.title}'")

        capped_docs  = all_docs[:cap]
        capped_metas = all_metas[:cap]
        trimmed_docs, trimmed_metas = _trim_contexts_by_tokens(
            capped_docs, capped_metas, Config.RAG_MAX_CONTEXT_TOKENS
        )
        logger.info(
            f"   📚 Final context: {len(trimmed_docs)}/{len(all_docs)} chunks "
            f"(cap={cap}, token_limit={Config.RAG_MAX_CONTEXT_TOKENS})"
        )
        # Coverage tracking: record which chunk IDs were used
        for meta in trimmed_metas:
            if meta and meta.get("id"):
                self.used_chunk_ids.add(meta["id"])
        # Also track via seen_ids (already deduped by the query loop above)
        self.used_chunk_ids.update(seen_ids)
        return trimmed_docs, trimmed_metas


    def _generate_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        available_image_count: int = 0,
        context_metadatas: list = None,
    ) -> str:
        """Generate detailed, comprehensive markdown content using LLM with RAG.

        Args:
            section: Section to write
            curriculum: Full curriculum
            contexts: RAG contexts
            available_image_count: Number of images selected for this section (for quality evaluation)
            context_metadatas: Metadata for each context chunk (K2: included in prompt)
        """
        # Calculate target metrics
        targets = calculate_target_metrics(section.estimated_time, section.difficulty_level)

        # Structural sections (intro/conclusion) should not require practice problems
        _section_id = section.id.lower()
        is_structural_section = _section_id.endswith("_intro") or _section_id.endswith("_conclusion")
        if is_structural_section:
            targets["target_practice_problems"] = 0

        # K2: format context with source metadata so LLM can reason about provenance
        context_text = _format_context_with_metadata(contexts, context_metadatas or [])

        # Determine language-aware labels for section headings.
        # learning_objectives are always generated in Korean (see curriculum_designer.py),
        # so they are a more reliable signal than the topic alone (e.g. "AI Engineering").
        _lang_text = " ".join(curriculum.learning_objectives) if curriculum.learning_objectives else curriculum.topic
        is_korean = detect_language(_lang_text) == "ko"
        intro_label = "도입부" if is_korean else "Introduction"
        summary_label = "핵심 요약" if is_korean else "Core Summary"

        # Prepare template variables
        template_vars = {
            # Basic information
            "topic": curriculum.topic,
            "audience_level": curriculum.audience_level,
            "section_title": section.title,
            "estimated_time": section.estimated_time,
            "difficulty_level": section.difficulty_level,
            # Topics and outcomes
            "topics_list": ', '.join(section.topics),
            "learning_outcomes_list": '\n'.join(f'- {outcome}' for outcome in section.learning_outcomes),
            # Target metrics
            "min_words": targets['min_words'],
            "target_words": targets['target_words'],
            "max_words": targets['max_words'],
            "target_subsections": targets['target_subsections'],
            "target_practice_problems": targets['target_practice_problems'],
            # Word count breakdown (using Config constants)
            "intro_words": int(targets['target_words'] * Config.CONTENT_INTRO_RATIO),
            "main_content_words": int(targets['target_words'] * Config.CONTENT_MAIN_RATIO),
            "summary_words": int(targets['target_words'] * Config.CONTENT_SUMMARY_RATIO),
            "words_per_subsection": int(targets['target_words'] * Config.CONTENT_MAIN_RATIO / max(1, targets['target_subsections'])),
            # Language-aware labels
            "intro_label": intro_label,
            "summary_label": summary_label,
            # Context
            "context_text": context_text,
            # Practice problems variables (disabled for intro/conclusion sections)
            "practice_fail_condition": _build_practice_fail_condition(
                targets['target_practice_problems'] > 0
            ),
            "practice_requirement_section": _build_practice_requirement_section(
                targets['target_practice_problems'] > 0, targets['target_practice_problems']
            ),
            "practice_checklist_item": _build_practice_checklist_item(
                targets['target_practice_problems'] > 0, targets['target_practice_problems']
            ),
        }

        # Load prompt from template (structural sections use a safer, focused prompt)
        if is_structural_section:
            section_type = "conclusion" if _section_id.endswith("_conclusion") else "introduction"
            language_instruction = "KOREAN (한국어)" if is_korean else "ENGLISH"
            prompt = _build_structural_section_prompt(
                section_title=section.title,
                section_type=section_type,
                topic=curriculum.topic,
                audience_level=curriculum.audience_level,
                estimated_time=section.estimated_time,
                topics_list=', '.join(section.topics),
                learning_outcomes_list='\n'.join(f'- {o}' for o in section.learning_outcomes),
                min_words=targets['min_words'],
                target_words=targets['target_words'],
                context_text=context_text,
                language_instruction=language_instruction,
            )
            logger.info(f"   📝 Using structural prompt for '{section.title}'")
        else:
            prompt = load_prompt("content_generation", **template_vars)

        try:
            response = self.invoke_llm(prompt, phase="content_writing")
            content = response.content.strip()

            # --- LLM refusal detection ---
            _content_lower = content.lower()
            if any(_content_lower.startswith(p) for p in _LLM_REFUSAL_PREFIXES):
                logger.warning(
                    f"  ⚠️ LLM refused prompt for '{section.title}'. Retrying with structural prompt..."
                )
                _stype = "conclusion" if _section_id.endswith("_conclusion") else (
                    "introduction" if _section_id.endswith("_intro") else "content"
                )
                _lang = "KOREAN (한국어)" if is_korean else "ENGLISH"
                _fallback = _build_structural_section_prompt(
                    section_title=section.title,
                    section_type=_stype,
                    topic=curriculum.topic,
                    audience_level=curriculum.audience_level,
                    estimated_time=section.estimated_time,
                    topics_list=', '.join(section.topics),
                    learning_outcomes_list='\n'.join(f'- {o}' for o in section.learning_outcomes),
                    min_words=targets['min_words'],
                    target_words=targets['target_words'],
                    context_text=context_text,
                    language_instruction=_lang,
                )
                response = self.invoke_llm(_fallback, phase="content_writing_fallback")
                content = response.content.strip()
                logger.info(f"  ✅ Fallback content generated for '{section.title}'")
            # --- LLM refusal detection end ---

            # Clean up markdown fences
            if content.startswith("```markdown"):
                content = content.split("```markdown")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            # RMC: Self-review of generated content
            content = self._review_content_with_rmc(content, section, curriculum, targets)

            # Validate content quality (use actual image count from selected images)
            quality = evaluate_content_quality(
                content=content,
                targets=targets,
                image_count=available_image_count,
            )

            logger.info(f"  📊 Initial quality score: {quality['overall_score']}/100 (with {available_image_count} images)")

            # If quality is too low, try to expand with multiple iterations
            if not quality["meets_requirements"]:
                logger.warning(f"  ⚠️ Content below target. Attempting to expand...")
                logger.info(format_quality_report(quality))

                # Try up to N iterations of expansion (from Config)
                max_iterations = Config.CONTENT_MAX_EXPANSION_ITERATIONS
                previous_quality_score = quality["overall_score"]  # Track for improvement check

                for iteration in range(max_iterations):
                    logger.info(f"  🔄 Expansion attempt {iteration + 1}/{max_iterations}")

                    try:
                        expanded_content = self.content_expander.expand_content(
                            section=section,
                            curriculum=curriculum,
                            contexts=contexts,
                            targets=targets,
                            previous_content=content,
                            previous_quality=quality,
                            context_metadatas=context_metadatas,  # K2: pass metadata
                        )

                        # Check if expansion was successful (content changed)
                        if expanded_content != content and len(expanded_content) > len(content):
                            content = expanded_content

                            # Re-evaluate (use actual image count)
                            quality = evaluate_content_quality(
                                content=content,
                                targets=targets,
                                image_count=available_image_count,
                            )

                            logger.info(f"  📊 Quality after expansion {iteration + 1}: {quality['overall_score']}/100")

                            # Check improvement effectiveness (prevent wasteful iterations)
                            if iteration > 0:
                                improvement = quality["overall_score"] - previous_quality_score
                                if improvement < Config.CONTENT_MIN_QUALITY_IMPROVEMENT:
                                    logger.warning(
                                        f"  ⚠️ Minimal improvement (+{improvement:.1f} points). "
                                        "Stopping early to prevent wasteful iterations."
                                    )
                                    break

                            # Stop if meets requirements
                            if quality["meets_requirements"]:
                                logger.info(f"  ✅ Quality threshold met after {iteration + 1} expansion(s)")
                                break

                            # Update previous score for next iteration comparison
                            previous_quality_score = quality["overall_score"]
                        else:
                            logger.warning(f"  ⚠️ Expansion {iteration + 1} produced no change - stopping")
                            break

                    except (RuntimeError, ValueError) as e:
                        logger.error(f"  ❌ Expansion {iteration + 1} failed: {e}")
                        break

            return content

        except Exception as e:
            logger.error(f"Error generating content: {e}", exc_info=True)
            return f"# {section.title}\n\n*Content generation error: {str(e)}*"


    def _get_keyword_translations(self) -> dict:
        """Comprehensive Korean-English keyword mapping for AI/ML terms."""
        return {
            # ===== AI/ML General =====
            "인공지능": ["artificial intelligence", "ai"],
            "기계학습": ["machine learning", "ml"],
            "딥러닝": ["deep learning", "dl", "deep neural network"],
            "신경망": ["neural network", "nn", "network"],
            # ===== LLM Related =====
            "대형 언어 모델": ["large language model", "llm", "language model", "transformer"],
            "언어 모델": ["language model", "llm", "lm"],
            "트랜스포머": ["transformer", "attention", "self-attention"],
            "어텐션": ["attention", "attention mechanism", "self-attention"],
            "파인튜닝": ["fine-tuning", "finetuning", "fine tuning", "finetune", "training"],
            "프롬프트": ["prompt", "prompting", "prompt engineering"],
            "프롬프트 엔지니어링": ["prompt engineering", "prompting", "prompt design"],
            "컨텍스트": ["context", "contextual", "context window"],
            "컨텍스트 엔지니어링": ["context engineering", "context", "contextual"],
            # ===== Models =====
            "GPT": ["gpt", "generative pre-trained transformer"],
            "BERT": ["bert", "bidirectional encoder"],
            "ChatGPT": ["chatgpt", "chat gpt", "gpt"],
            "LLM": ["llm", "large language model", "language model"],
            # ===== RAG & Vector DB =====
            "RAG": ["rag", "retrieval augmented generation", "retrieval", "augmented"],
            "정보 검색": ["retrieval", "information retrieval", "search", "ir"],
            "검색": ["search", "retrieval", "query", "lookup"],
            "임베딩": ["embedding", "embeddings", "vector embedding", "word embedding"],
            "벡터": ["vector", "vectors", "vectorization"],
            "벡터 데이터베이스": ["vector database", "vector db", "vectordb", "embedding database"],
            "데이터베이스": ["database", "db", "datastore", "storage"],
            "색인": ["index", "indexing"],
            "유사도": ["similarity", "cosine similarity", "distance"],
            # ===== AI Agents =====
            "에이전트": ["agent", "agents", "ai agent", "autonomous"],
            "AI 에이전트": ["ai agent", "agent", "autonomous agent"],
            "자율": ["autonomous", "automation", "automatic"],
            "계획": ["planning", "plan", "strategy"],
            "도구": ["tool", "tools", "function", "api"],
            "실행": ["execution", "execute", "action"],
            "추론": ["reasoning", "inference", "thinking"],
            "의사결정": ["decision making", "decision"],
            # ===== Generation Parameters =====
            "파라미터": ["parameter", "parameters", "hyperparameter", "config"],
            "하이퍼파라미터": ["hyperparameter", "hyper-parameter", "parameter"],
            "온도": ["temperature", "temp", "sampling"],
            "토큰": ["token", "tokens", "tokenization"],
            "생성": ["generation", "generate", "output", "inference"],
            "생성 파라미터": ["generation parameters", "sampling", "decoding"],
            "샘플링": ["sampling", "sample", "decoding"],
            "빔 서치": ["beam search", "beam"],
            "탐욕": ["greedy", "greedy search"],
            # ===== Reinforcement Learning =====
            "강화학습": ["reinforcement learning", "rl", "reward", "policy"],
            "보상": ["reward", "rewards"],
            "정책": ["policy", "policies"],
            "가치함수": ["value function", "value"],
            "Q-학습": ["q-learning", "q learning"],
            "병목": ["bottleneck", "constraint"],
            "병목 현상": ["bottleneck", "bottleneck problem"],
            # ===== Architecture =====
            "아키텍처": ["architecture", "model architecture", "structure"],
            "레이어": ["layer", "layers", "hidden layer"],
            "인코더": ["encoder", "encoding"],
            "디코더": ["decoder", "decoding"],
            "어텐션 메커니즘": ["attention mechanism", "attention", "self-attention"],
            "순환 신경망": ["recurrent neural network", "rnn"],
            "합성곱": ["convolution", "convolutional", "cnn"],
            "완전 연결": ["fully connected", "dense", "fc"],
            # ===== Training Process =====
            "학습": ["training", "learning", "train"],
            "훈련": ["training", "train"],
            "사전학습": ["pre-training", "pretraining", "pretrain"],
            "사전 학습": ["pre-training", "pretraining", "pretrain"],
            "미세조정": ["fine-tuning", "finetuning", "fine tuning"],
            "미세 조정": ["fine-tuning", "finetuning", "fine tuning"],
            "튜닝": ["tuning", "fine-tuning"],
            "최적화": ["optimization", "optimizer", "optimize"],
            "손실함수": ["loss function", "loss", "objective"],
            "손실": ["loss", "loss function"],
            "경사하강": ["gradient descent", "backpropagation", "gradient"],
            "역전파": ["backpropagation", "backprop"],
            "배치": ["batch", "batching", "mini-batch"],
            "에포크": ["epoch", "epochs"],
            # ===== Evaluation =====
            "평가": ["evaluation", "eval", "assessment", "metric"],
            "성능": ["performance", "accuracy", "precision"],
            "정확도": ["accuracy", "acc"],
            "정밀도": ["precision"],
            "재현율": ["recall"],
            "F1": ["f1", "f1-score"],
            "지표": ["metric", "metrics", "measure"],
            # ===== Data =====
            "데이터": ["data", "dataset"],
            "데이터셋": ["dataset", "data", "corpus"],
            "말뭉치": ["corpus", "corpora", "dataset"],
            "전처리": ["preprocessing", "preprocess", "data cleaning"],
            "정규화": ["normalization", "normalize"],
            "토큰화": ["tokenization", "tokenize"],
            "레이블": ["label", "labels", "annotation"],
            # ===== Common CS Terms =====
            "알고리즘": ["algorithm", "algo"],
            "모델": ["model", "models"],
            "예측": ["prediction", "inference", "predict"],
            "분류": ["classification", "classify"],
            "회귀": ["regression"],
            "군집화": ["clustering", "cluster"],
            "차원": ["dimension", "dimensional"],
            "특징": ["feature", "features"],
            # ===== Visualization =====
            "다이어그램": ["diagram", "chart", "visualization"],
            "그래프": ["graph", "plot", "chart"],
            "시각화": ["visualization", "visual", "plot"],
            "플롯": ["plot", "plotting"],
            # ===== Domain Specific =====
            "자연어처리": ["natural language processing", "nlp", "language processing"],
            "컴퓨터비전": ["computer vision", "cv", "image processing"],
            "이미지 처리": ["image processing", "computer vision"],
            "음성인식": ["speech recognition", "speech", "audio"],
            "텍스트 생성": ["text generation", "generation"],
            "번역": ["translation", "machine translation"],
            # ===== Concepts =====
            "개념": ["concept", "concepts"],
            "원리": ["principle", "principles"],
            "방법": ["method", "methods", "approach"],
            "기법": ["technique", "techniques"],
            "전략": ["strategy", "strategies"],
            "패턴": ["pattern", "patterns"],
            "구조": ["structure", "structures"],
            "시스템": ["system", "systems"],
            "프레임워크": ["framework", "frameworks"],
            "라이브러리": ["library", "libraries"],
        }


    def _review_content_with_rmc(
        self,
        content: str,
        section: "Section",
        curriculum: "Curriculum",
        targets: dict,
    ) -> str:
        """
        RMC (Reflective Meta-Cognition) self-review of generated section content.

        Layer 1: Check for conceptual leaps, unclear explanations, code-text gaps, flow breaks, repetition.
        Layer 2: Re-examine review to avoid over-correction of good content.
        Returns revised content, or original if review fails or produces something shorter.
        """
        original_word_count = len(content.split())

        # Skip RMC review if the initial content is empty — nothing to review
        if original_word_count == 0:
            logger.warning("RMC content review skipped: initial content is empty")
            return content

        # Slice content to avoid token overload while keeping enough for review
        content_slice = content[:4000] if len(content) > 4000 else content
        truncated_note = f"\n[Note: content truncated to 4000 chars for review; full word count: {original_word_count}]" if len(content) > 4000 else ""

        prompt = f"""You are an expert educational content reviewer. Review the following lecture section content and improve it if needed.

## Section Context
- Lecture Topic: {curriculum.topic}
- Section Title: {section.title}
- Audience Level: {curriculum.audience_level}
- Target Word Count: {targets['target_words']} words (current: {original_word_count} words)

## Content to Review
{content_slice}{truncated_note}

---

## Layer 1 — Educational Quality Review (check each item):
1. **Conceptual leaps**: Are there concepts introduced without sufficient prior explanation for a {curriculum.audience_level}-level learner?
2. **Unclear explanations**: Are there sentences or paragraphs that would confuse the target audience?
3. **Code-text connection**: If code examples are present, do they have adequate before/after explanation?
4. **Flow breaks**: Are there abrupt transitions between subsections that disrupt logical flow?
5. **Repetition**: Is the same explanation given more than once without adding new insight?

## Layer 2 — Review of the Review:
- Are your judgments calibrated for a {curriculum.audience_level}-level audience (not too strict, not too lenient)?
- Is the content actually problematic, or are you flagging things that are fine?
- Would fixing the flagged items genuinely help learners, or would it just change the style?

---

## Instructions:
- Output the COMPLETE revised content with only the necessary corrections applied.
- If the content is already high quality, output it UNCHANGED.
- Do NOT add a preamble, explanation, or meta-commentary — just output the content itself.
- Do NOT shorten the content; maintain or slightly increase word count.
- Preserve all code blocks exactly as they are.

## Revised Content:"""

        try:
            response = self.invoke_llm(prompt, phase="content_rmc_review")
            revised = response.content.strip()

            # Validate: revised must be at least 80% of original word count
            revised_word_count = len(revised.split())
            min_words = int(original_word_count * 0.8)

            if revised_word_count < min_words:
                logger.warning(
                    f"RMC content review returned too-short result "
                    f"({revised_word_count} < {min_words} words) — using original"
                )
                return content

            logger.info(
                f"RMC content review applied: {original_word_count} → {revised_word_count} words "
                f"for section '{section.title}'"
            )
            return revised

        except (RuntimeError, ValueError) as e:
            logger.warning(f"RMC content review failed (returning original): {e}")
            return content

    def _expand_keywords(self, topic: str, keyword_map: dict) -> List[str]:
        """Expand topic with English translations and variations."""
        keywords = [topic]  # Original topic

        # Add mapped translations
        for ko_term, en_terms in keyword_map.items():
            if ko_term in topic:
                keywords.extend(en_terms)

        # Extract acronyms (e.g., "LLM" from "대형 언어 모델(LLM)")
        import re

        acronyms = re.findall(r"\b[A-Z]{2,}\b", topic)
        keywords.extend([a.lower() for a in acronyms])

        # Extract English words already in topic
        english_words = re.findall(r"\b[a-zA-Z]{3,}\b", topic)
        keywords.extend([w.lower() for w in english_words])

        # Remove duplicates and empty strings
        keywords = list(set(k for k in keywords if k))

        return keywords

