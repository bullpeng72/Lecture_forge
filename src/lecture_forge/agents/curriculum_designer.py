"""
Curriculum Designer Agent - Designs lecture structure and curriculum.
"""

import json
from typing import Dict, List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.models.analysis import AnalysisResult
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.utils import logger


class CurriculumDesignerAgent(BaseAgent):
    """Agent for designing lecture curriculum and structure."""

    def __init__(self):
        super().__init__()
        logger.info("Initializing Curriculum Designer Agent")

    def design(
        self,
        analysis_result: AnalysisResult,
        topic: str,
        duration: int,
        audience_level: str = "intermediate",
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

        # 1. Generate learning objectives
        learning_objectives = self._generate_learning_objectives(topic, analysis_result, audience_level)

        # 2. Select and sequence topics
        selected_topics = self._select_topics(analysis_result, duration, audience_level)

        # 3. Create sections with time allocation
        sections = self._create_sections(selected_topics, analysis_result, duration, audience_level, topic=topic)

        # 4. Build prerequisite map
        prerequisite_map = self._build_prerequisite_map(sections, analysis_result)

        # Calculate total estimated time
        total_time = sum(section.estimated_time for section in sections)

        curriculum = Curriculum(
            topic=topic,
            duration=duration,
            audience_level=audience_level,
            learning_objectives=learning_objectives,
            sections=sections,
            total_estimated_time=total_time,
            prerequisite_map=prerequisite_map,
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

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            objectives = json.loads(content)

            if isinstance(objectives, list):
                return objectives[:5]
            else:
                logger.warning(f"Unexpected objectives format: {objectives}")
                return [f"Understand the fundamentals of {topic}"]

        except Exception as e:
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

        # Estimate how many topics we can cover (roughly 10-20 min per topic)
        avg_time_per_topic = 15  # minutes
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
    ) -> List[Section]:
        """Create curriculum sections from topics."""
        from lecture_forge.utils.language_utils import detect_language

        is_korean = detect_language(topic) == "ko"

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
        """
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

            # Strip markdown fences if present
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            review = json.loads(raw)

            if review.get("no_changes"):
                logger.info("RMC curriculum review: no changes needed")
                return curriculum

            # Log identified issues
            for issue in review.get("issues", []):
                logger.info(f"RMC curriculum issue: {issue}")

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

            logger.info(f"RMC curriculum review applied: {review.get('reasoning', '')[:100]}")

        except Exception as e:
            logger.warning(f"RMC curriculum review failed (returning original): {e}")

        return curriculum

    def _build_prerequisite_map(
        self,
        sections: List[Section],
        analysis_result: AnalysisResult,
    ) -> Dict[str, List[str]]:
        """Build prerequisite map between sections."""
        prerequisite_map = {}

        # Simple heuristic: earlier sections are prerequisites for later ones
        # with similar topics
        for i, section in enumerate(sections):
            prerequisites = []

            # Check if any earlier section covers prerequisite topics
            for j, earlier_section in enumerate(sections[:i]):
                # Check for prerequisite relationships
                for relation in analysis_result.concept_relations:
                    if (
                        relation.relation_type == "prerequisite"
                        and relation.target in section.topics
                        and relation.source in earlier_section.topics
                    ):
                        prerequisites.append(earlier_section.id)
                        break

            if prerequisites:
                prerequisite_map[section.id] = list(set(prerequisites))

        return prerequisite_map
