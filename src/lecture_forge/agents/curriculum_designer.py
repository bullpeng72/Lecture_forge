"""
Curriculum Designer Agent - Designs lecture structure and curriculum.
"""

import json
from typing import List, Optional

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.analysis import AnalysisResult
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.utils import logger
from lecture_forge.utils.json_utils import strip_json_fence


class CurriculumDesignerAgent(BaseAgent):
    """Agent for designing lecture curriculum and structure."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        super().__init__()
        self.vector_store = vector_store
        logger.info("Initializing Curriculum Designer Agent")

    def design(
        self,
        analysis_result: AnalysisResult,
        topic: str,
        duration: int,
        audience_level: str = "intermediate",
        source_files: Optional[List[str]] = None,
    ) -> Curriculum:
        """
        Design curriculum based on analysis and user inputs.

        Args:
            analysis_result: Result from ContentAnalyzer
            topic: Main lecture topic
            duration: Lecture duration in minutes
            audience_level: Target audience (beginner/intermediate/advanced)

        Returns:
            Curriculum plan
        """
        logger.info(f"Designing curriculum for {duration}-minute lecture on '{topic}'")
        logger.info(f"Target audience: {audience_level}")

        # v0.4.0: extract source_files from analysis metadata if not explicitly provided
        if source_files is None:
            source_files = analysis_result.metadata.get("source_files", [])
        if source_files:
            logger.info(f"   📂 Source files for coverage tracking: {len(source_files)}")

        # 1. Generate learning objectives
        learning_objectives = self._generate_learning_objectives(topic, analysis_result, audience_level)

        # 2. Select and sequence topics
        selected_topics = self._select_topics(analysis_result, duration, audience_level)

        # 3. Create sections with time allocation
        sections = self._create_sections(
            selected_topics, analysis_result, duration, audience_level, topic=topic,
            learning_objectives=learning_objectives,
        )

        # 4. Validate sections against the knowledge base and fill coverage gaps
        sections = self._validate_and_enrich_sections(sections, duration, audience_level, topic, source_files=source_files)

        # Calculate total estimated time
        total_time = sum(section.estimated_time for section in sections)

        curriculum = Curriculum(
            topic=topic,
            duration=duration,
            audience_level=audience_level,
            learning_objectives=learning_objectives,
            sections=sections,
            total_estimated_time=total_time,
            source_files=source_files,  # v0.4.0: for content writer diversity query
        )

        # RMC: Self-review of generated curriculum
        curriculum = self._review_with_rmc(curriculum, analysis_result)

        logger.info(f"Curriculum designed: {len(curriculum.sections)} sections, {curriculum.total_estimated_time} minutes total")
        return curriculum

    def _generate_learning_objectives(
        self,
        topic: str,
        analysis_result: AnalysisResult,
        audience_level: str,
    ) -> List[str]:
        """Generate learning objectives using LLM."""
        key_topics = analysis_result.key_topics[:5]  # Top 5 topics

        prompt = f"""Create 3-5 clear learning objectives for a {audience_level}-level lecture on "{topic}".

The lecture will cover these topics:
{', '.join(key_topics)}

Learning objectives should:
- Start with action verbs (이해하다, 설명하다, 적용하다, 분석하다, etc.)
- Be specific and measurable
- Be appropriate for {audience_level} level

IMPORTANT: Write all learning objectives in KOREAN language.
Return ONLY a JSON array of learning objective strings in Korean. Example: ["...을 이해한다", "...을 설명할 수 있다", "...을 적용할 수 있다"]"""

        try:
            response = self.invoke_llm(prompt, phase="curriculum_design")
            content = response.content.strip()

            content = strip_json_fence(content)
            objectives = json.loads(content)

            if isinstance(objectives, list):
                return objectives[:5]
            else:
                logger.warning(f"Unexpected objectives format: {objectives}")
                return [f"Understand the fundamentals of {topic}"]

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Error generating learning objectives: {e}")
            return [
                f"Understand the fundamentals of {topic}",
                f"Apply {topic} concepts to real-world problems",
            ]

    def _select_topics(
        self,
        analysis_result: AnalysisResult,
        duration: int,
        audience_level: str,
    ) -> List[str]:
        """Select topics appropriate for the duration and audience level."""
        all_topics = analysis_result.key_topics
        difficulty_scores = analysis_result.difficulty_scores

        # Filter topics by audience level
        if audience_level == "beginner":
            # Prefer easier topics
            selected = [topic for topic in all_topics if difficulty_scores.get(topic, 0.5) < 0.6]
        elif audience_level == "advanced":
            # Prefer harder topics
            selected = [topic for topic in all_topics if difficulty_scores.get(topic, 0.5) > 0.4]
        else:  # intermediate
            selected = all_topics

        # Estimate how many topics we can cover (v0.4.0: 15→10 min per topic for denser coverage)
        avg_time_per_topic = 10  # minutes
        max_topics = max(3, duration // avg_time_per_topic)

        # Return top topics up to the limit
        return selected[:max_topics]

    def _create_sections(
        self,
        topics: List[str],
        analysis_result: AnalysisResult,
        duration: int,
        audience_level: str,
        topic: str = "",
        learning_objectives: List[str] = None,
    ) -> List[Section]:
        """Create curriculum sections from topics."""
        from lecture_forge.utils.language_utils import detect_language

        # Use learning_objectives for language detection: they are always generated in Korean
        # by _generate_learning_objectives(), so mixed-language topics like "AI Engineering"
        # correctly resolve to Korean output.
        _lang_text = " ".join(learning_objectives) if learning_objectives else topic
        is_korean = detect_language(_lang_text) == "ko"

        sections = []

        # Reserve time for intro and conclusion
        intro_time = max(5, duration // 20)  # 5% for intro
        conclusion_time = max(5, duration // 20)  # 5% for conclusion
        content_time = duration - intro_time - conclusion_time

        # 1. Introduction section
        sections.append(
            Section(
                id="section_0_intro",
                title="소개" if is_korean else "Introduction",
                topics=["강의 개요", "학습 목표"] if is_korean else ["Course overview", "Learning objectives"],
                estimated_time=intro_time,
                difficulty_level="beginner",
                learning_outcomes=[
                    "강의 구조를 이해한다" if is_korean else "Understand the course structure",
                    "다룰 내용을 파악한다" if is_korean else "Know what will be covered",
                ],
            )
        )

        # 2. Main content sections
        if not topics:
            topics = ["Overview"]

        time_per_topic = content_time // len(topics)

        for i, topic in enumerate(topics):
            # Get related concepts from topic clusters
            related_concepts = []
            for cluster in analysis_result.topic_clusters:
                if cluster.name == topic or topic in cluster.concepts:
                    related_concepts = cluster.concepts[:3]
                    break

            # Determine difficulty
            difficulty_score = analysis_result.difficulty_scores.get(topic, 0.5)
            if difficulty_score < 0.4:
                difficulty = "beginner"
            elif difficulty_score > 0.7:
                difficulty = "advanced"
            else:
                difficulty = "intermediate"

            # Generate learning outcomes for this section
            outcomes = [
                f"Understand {topic}",
                f"Apply {topic} concepts",
            ]

            section = Section(
                id=f"section_{i+1}_{topic.lower().replace(' ', '_')}",
                title=topic,
                topics=[topic] + related_concepts,
                estimated_time=time_per_topic,
                difficulty_level=difficulty,
                learning_outcomes=outcomes,
            )
            sections.append(section)

        # 3. Conclusion section
        sections.append(
            Section(
                id=f"section_{len(topics)+1}_conclusion",
                title="결론 및 다음 단계" if is_korean else "Conclusion and Next Steps",
                topics=["요약", "핵심 내용", "심화 학습"] if is_korean else ["Summary", "Key takeaways", "Further learning"],
                estimated_time=conclusion_time,
                difficulty_level="beginner",
                learning_outcomes=[
                    "핵심 개념을 정리한다" if is_korean else "Summarize key concepts",
                    "다음 학습 단계를 파악한다" if is_korean else "Identify next steps for learning",
                ],
            )
        )

        return sections

    def _review_with_rmc(self, curriculum: "Curriculum", analysis_result: "AnalysisResult") -> "Curriculum":
        """
        RMC (Reflective Meta-Cognition) self-review of the generated curriculum.

        Layer 1: Review the curriculum for logical ordering, coverage, and coherence.
        Layer 2: Review the review itself to avoid over-correction.
        Applies corrections to the curriculum object before returning.

        Bounded by Config.MAX_RMC_ROUNDS (default 1) to prevent runaway LLM calls.
        Exits early when the LLM reports no_changes=True.
        """
        max_rounds = Config.MAX_RMC_ROUNDS

        for rmc_round in range(max_rounds):
            # Build section summary for the prompt
            section_lines = []
            for i, s in enumerate(curriculum.sections):
                section_lines.append(
                    f"  {i+1}. [{s.id}] {s.title} | {s.estimated_time}min | {s.difficulty_level}"
                )
            sections_str = "\n".join(section_lines)
            objectives_str = "\n".join(f"  - {obj}" for obj in curriculum.learning_objectives)

            prompt = f"""You are a senior curriculum reviewer. Critically evaluate the following lecture curriculum.

## Curriculum Details
- Topic: {curriculum.topic}
- Total Duration: {curriculum.duration} minutes
- Audience Level: {curriculum.audience_level}

## Learning Objectives
{objectives_str}

## Sections (in current order)
{sections_str}

---

## Layer 1 — Curriculum Review (answer each item):
1. **Difficulty progression**: Are sections ordered from simpler to more complex? If not, which sections should swap?
2. **Time consistency**: Does the sum of section times roughly match the total duration ({curriculum.duration} min)?
3. **Objective coverage**: Is there at least one section that addresses each learning objective?
4. **Redundancy**: Are any sections overlapping or too broad to be useful?
5. **Prerequisite order**: Are foundational topics placed before sections that depend on them?

## Layer 2 — Review of the Review:
- Are your judgments appropriate for a {curriculum.audience_level}-level audience?
- Did you overlook important pedagogical dimensions (engagement, real-world relevance, pacing)?
- Are your suggested changes actually necessary, or is the curriculum already sound?

---

## Response Format (strict JSON, no markdown fences):
{{
  "revised_objectives": ["objective 1", "objective 2"] or null,
  "section_reorder": ["section_id_1", "section_id_2", ...] or null,
  "issues": ["issue description 1", "issue description 2"],
  "reasoning": "Brief explanation of decisions",
  "no_changes": true or false
}}

Rules:
- "section_reorder": include ALL section IDs in the desired order, or null if order is fine
- "revised_objectives": only if objectives need rewording, otherwise null
- "issues": list real problems found (empty list [] if none)
- "no_changes": true only if curriculum is already well-structured"""

            try:
                response = self.invoke_llm(prompt, phase="curriculum_rmc_review")
                raw = response.content.strip()

                review = json.loads(strip_json_fence(raw))

                if review.get("no_changes"):
                    logger.info(f"RMC curriculum review: stable after {rmc_round + 1} round(s)")
                    return curriculum

                # Log identified issues
                for issue in review.get("issues", []):
                    logger.info(f"RMC curriculum issue (round {rmc_round + 1}): {issue}")

                # Apply revised objectives
                if review.get("revised_objectives"):
                    curriculum.learning_objectives = review["revised_objectives"]
                    logger.info(f"RMC: updated {len(curriculum.learning_objectives)} learning objectives")

                # Apply section reordering
                if review.get("section_reorder"):
                    reorder_ids = review["section_reorder"]
                    section_map = {s.id: s for s in curriculum.sections}
                    reordered = []
                    for sid in reorder_ids:
                        if sid in section_map:
                            reordered.append(section_map[sid])
                    # Keep any sections not mentioned (append at end)
                    mentioned = set(reorder_ids)
                    for s in curriculum.sections:
                        if s.id not in mentioned:
                            reordered.append(s)
                    if len(reordered) == len(curriculum.sections):
                        curriculum.sections = reordered
                        logger.info(f"RMC: reordered {len(reordered)} curriculum sections")

                logger.info(f"RMC curriculum review (round {rmc_round + 1}/{max_rounds}) applied: {review.get('reasoning', '')[:100]}")

            except (json.JSONDecodeError, ValueError, KeyError, RuntimeError) as e:
                logger.warning(f"RMC curriculum review failed (returning current state): {e}")
                break

        return curriculum

    def _validate_and_enrich_sections(
        self,
        sections: List[Section],
        duration: int,
        audience_level: str,
        topic: str,
        source_files: Optional[List[str]] = None,
    ) -> List[Section]:
        """
        Validate each section against the knowledge base and discover topics
        that are well-covered in the KB but not yet in the curriculum.

        Steps:
        1. Query the KB for each section title; log a warning if no chunks match.
        2. Ask the KB for topics NOT yet covered by the current section list
           and insert new sections if significant content exists.
        """
        if not self.vector_store:
            return sections

        try:
            stats = self.vector_store.get_stats()
            if stats.get("document_count", 0) == 0:
                return sections
        except (RuntimeError, ValueError, AttributeError):
            return sections

        # ── Step 1: validate existing sections ──────────────────────────────
        validated: List[Section] = []
        content_sections = [
            s for s in sections
            if not s.id.lower().endswith("_intro")
            and not s.id.lower().endswith("_conclusion")
        ]
        structural = [
            s for s in sections
            if s.id.lower().endswith("_intro") or s.id.lower().endswith("_conclusion")
        ]

        for section in content_sections:
            try:
                results = self.vector_store.query(section.title, n_results=3)
                docs = (results.get("documents") or [[]])[0]
                if docs:
                    validated.append(section)
                else:
                    logger.warning(
                        f"   ⚠️  CurriculumDesigner: no KB content for section "
                        f"'{section.title}' — keeping anyway (may be derivable)"
                    )
                    validated.append(section)  # keep; LLM may still generate useful content
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.debug(f"KB validation query failed for '{section.title}': {e}")
                validated.append(section)

        # ── Step 2: discover uncovered KB topics (v0.5.1: full-KB uniform sampling) ──
        try:
            validated = self._enrich_curriculum_from_full_kb(
                validated, duration, topic, structural
            )
        except (RuntimeError, ValueError, AttributeError, json.JSONDecodeError) as e:
            logger.warning(f"KB enrichment step failed (non-critical): {e}")

        # ── Step 3: v0.4.0 — source file coverage check ──────────────────────
        if source_files:
            try:
                uncovered = self._check_source_coverage(validated, source_files)
                if uncovered:
                    logger.info(f"   📂 Uncovered sources: {[s.split('/')[-1] for s in uncovered]}")
                    # Query KB for content from uncovered sources and propose new sections
                    for src_path in uncovered[:3]:  # limit to 3 uncovered sources
                        try:
                            src_results = self.vector_store.query(
                                src_path.split("/")[-1].replace(".pdf", "").replace("_", " "),
                                n_results=4,
                            )
                            src_chunks = (src_results.get("documents") or [[]])[0]
                            if not src_chunks:
                                continue
                            src_hint = "\n\n".join(src_chunks[:3])[:2000]
                            covered_str = ", ".join(s.title for s in validated)
                            prompt = f"""A lecture on "{topic}" currently covers: {covered_str}.
The following content from source "{src_path.split('/')[-1]}" is NOT yet covered.
Based on this content, suggest 1-2 additional section topics that would enrich the lecture.

Content excerpt:
{src_hint}

Return ONLY a JSON array of short topic names in Korean (max 5 words each).
If the content is already covered, return [].
Example: ["추가 주제 1", "추가 주제 2"]"""
                            resp = self.invoke_llm(prompt, phase="curriculum_source_coverage")
                            raw = resp.content.strip()
                            new_topics = json.loads(strip_json_fence(raw))
                            if isinstance(new_topics, list):
                                existing_titles = {s.title.lower() for s in validated}
                                used_time = sum(s.estimated_time for s in validated)
                                intro_t = next((s.estimated_time for s in structural if "_intro" in s.id), 5)
                                concl_t = next((s.estimated_time for s in structural if "_conclusion" in s.id), 5)
                                remaining = duration - used_time - intro_t - concl_t
                                time_per = max(10, remaining // max(1, len(new_topics)))
                                for j, new_title in enumerate(new_topics[:2]):
                                    if new_title.lower() not in existing_titles:
                                        new_section = Section(
                                            id=f"section_src_{j}_{new_title.lower().replace(' ', '_')[:20]}",
                                            title=new_title,
                                            topics=[new_title],
                                            estimated_time=time_per,
                                            difficulty_level="intermediate",
                                            learning_outcomes=[
                                                f"{new_title}를 이해한다",
                                                f"{new_title}를 적용할 수 있다",
                                            ],
                                        )
                                        validated.append(new_section)
                                        logger.info(
                                            f"   ✅ CurriculumDesigner: added source-coverage section '{new_title}'"
                                        )
                        except (RuntimeError, ValueError, json.JSONDecodeError) as src_e:
                            logger.debug(f"Source coverage enrichment failed for '{src_path}': {src_e}")
            except (RuntimeError, ValueError, AttributeError) as cov_e:
                logger.debug(f"Source coverage check failed (non-critical): {cov_e}")

        # Rebuild with structural sections (intro first, conclusion last)
        intro_sections = [s for s in structural if "_intro" in s.id]
        conclusion_sections = [s for s in structural if "_conclusion" in s.id]
        result = intro_sections + validated + conclusion_sections

        if len(result) != len(sections):
            logger.info(
                f"   📋 CurriculumDesigner: {len(sections)} → {len(result)} sections "
                f"after KB validation"
            )

        return result

    def _enrich_curriculum_from_full_kb(
        self,
        validated: List[Section],
        duration: int,
        topic: str,
        structural: List[Section],
    ) -> List[Section]:
        """v0.5.1: Enrich curriculum by sampling the full KB uniformly (30 chunks).

        Replaces the probe_queries approach: instead of 5 fixed queries retrieving ~6 chunks each,
        we sample the entire KB at equal intervals to capture diverse content that probe queries miss.
        """
        try:
            all_items = self.vector_store.collection.get(include=["documents"])
            all_docs = all_items.get("documents") or []
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.debug(f"KB full-sample get failed: {e}")
            return validated

        if not all_docs:
            return validated

        # Uniform-interval sampling for diversity
        step = max(1, len(all_docs) // 30)
        sampled = [all_docs[i][:300] for i in range(0, len(all_docs), step)][:30]
        sample_text = "\n---\n".join(sampled)[:6000]

        existing_titles = {s.title.lower() for s in validated}
        covered_str = ", ".join(s.title for s in validated)

        prompt = f"""강의 주제: "{topic}"
현재 커리큘럼 섹션: {covered_str}

강의 자료 전체 내용의 대표 샘플:
{sample_text}

위 자료에 있으나 커리큘럼에서 다루지 않는 중요 기술 토픽을 최대 5개 한국어로 나열.
없으면 빈 배열. JSON: ["토픽1", "토픽2"]"""

        try:
            response = self.invoke_llm(prompt, phase="curriculum_kb_enrichment")
            raw = response.content.strip()
            new_topics = json.loads(strip_json_fence(raw))
            if isinstance(new_topics, list):
                used_time = sum(s.estimated_time for s in validated)
                intro_time = next(
                    (s.estimated_time for s in structural if "_intro" in s.id), 5
                )
                conclusion_time = next(
                    (s.estimated_time for s in structural if "_conclusion" in s.id), 5
                )
                remaining = duration - used_time - intro_time - conclusion_time
                time_per_new = max(10, remaining // max(1, len(new_topics)))

                for i, new_title in enumerate(new_topics[:5]):
                    if new_title.lower() not in existing_titles:
                        new_section = Section(
                            id=f"section_kb_{i}_{new_title.lower().replace(' ', '_')[:20]}",
                            title=new_title,
                            topics=[new_title],
                            estimated_time=time_per_new,
                            difficulty_level="intermediate",
                            learning_outcomes=[
                                f"{new_title}를 이해한다",
                                f"{new_title}를 적용할 수 있다",
                            ],
                        )
                        validated.append(new_section)
                        logger.info(
                            f"   ✅ CurriculumDesigner: added KB-discovered section '{new_title}'"
                        )
        except (RuntimeError, ValueError, json.JSONDecodeError) as e:
            logger.debug(f"KB enrichment LLM call failed: {e}")

        return validated

    def _check_source_coverage(
        self,
        sections: List[Section],
        source_files: List[str],
    ) -> List[str]:
        """
        v0.4.0: Check which source files have NO chunks matched by any existing section.

        Returns a list of uncovered source file paths.
        """
        if not self.vector_store or not source_files:
            return []

        covered_sources: set = set()
        for section in sections:
            try:
                results = self.vector_store.query(section.title, n_results=5)
                metas = (results.get("metadatas") or [[]])[0]
                for meta in metas:
                    src = meta.get("source", "")
                    if src:
                        covered_sources.add(src)
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.debug(f"Coverage query failed for '{section.title}': {e}")

        uncovered = [s for s in source_files if s and s not in covered_sources]
        return uncovered

