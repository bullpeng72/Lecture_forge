"""
Revision Agent - Revises lecture based on evaluation.
"""

import re
from copy import deepcopy

from lecture_forge.agents.base import BaseAgent
from lecture_forge.exceptions import ContentGenerationError
from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import Lecture, SectionContent, MermaidDiagram
from lecture_forge.utils import logger


def _build_expansion_code_section(with_code: bool, target_gap: int) -> str:
    """Return expansion-prompt code section only when with_code is enabled."""
    if not with_code:
        return ""
    return f"""2. **추가 코드 예제** (~{int(target_gap * 0.3)} words):
   ```python
   # 새로운 시나리오의 예제 (기존과 다른)
   # 최소 20-30줄
   # 상세한 주석 포함
   ```
   - 예제 전: 무엇을 보여주는가 설명
   - 예제 후: 각 라인 설명
   - 실행 결과 예측

"""


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks and clean up blank lines."""
    text = re.sub(r"```[\s\S]*?```", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class RevisionAgent(BaseAgent):
    """Agent for revising lecture content."""

    def __init__(self, with_code: bool = False):
        super().__init__()
        self.with_code = with_code
        logger.info("Initializing Revision Agent")

    def revise(self, lecture: Lecture, evaluation: EvaluationResult) -> Lecture:
        """
        Revise lecture based on evaluation.

        Args:
            lecture: Lecture to revise
            evaluation: Evaluation result with issues

        Returns:
            Revised lecture
        """
        logger.info(f"Revising lecture based on {len(evaluation.issues)} issues")

        # Create a deep copy to avoid modifying original
        revised_lecture = deepcopy(lecture)

        # Process issues by severity
        high_severity_issues = [i for i in evaluation.issues if i.severity == "high"]
        medium_severity_issues = [i for i in evaluation.issues if i.severity == "medium"]

        logger.info(
            f"Processing {len(high_severity_issues)} high and " f"{len(medium_severity_issues)} medium severity issues"
        )

        # Handle high severity issues first
        for issue in high_severity_issues:
            self._handle_issue(revised_lecture, issue)

        # Handle medium severity issues
        for issue in medium_severity_issues:
            self._handle_issue(revised_lecture, issue)

        # Recalculate statistics
        revised_lecture.total_word_count = sum(s.word_count for s in revised_lecture.sections)
        revised_lecture.total_diagrams = sum(len(s.diagrams) for s in revised_lecture.sections)
        revised_lecture.total_images = sum(len(s.images) for s in revised_lecture.sections)

        logger.info("Revision complete")
        return revised_lecture

    def _handle_issue(self, lecture: Lecture, issue: Issue) -> None:
        """Handle a specific issue."""
        logger.debug(f"Handling {issue.severity} issue in {issue.dimension}: {issue.description}")

        if issue.dimension == "content_completeness":
            # PRIORITY 1: Code examples (only when --with-code is enabled)
            if ("code" in issue.description.lower() or "NO code" in issue.description) and self.with_code:
                logger.info(f"  🚨 Handling critical code example shortage")
                self._add_code_examples(lecture, issue)
            # PRIORITY 2: Content length
            elif "short" in issue.description.lower():
                self._expand_content(lecture, issue)
            # PRIORITY 3: General completeness
            else:
                self._expand_content(lecture, issue)

        elif issue.dimension == "logical_flow":
            if "intro" in issue.description.lower():
                self._add_introduction(lecture)
            elif "conclusion" in issue.description.lower():
                self._add_conclusion(lecture)

        elif issue.dimension == "visual_quality":
            if "diagram" in issue.description.lower():
                self._add_diagrams(lecture, issue)
            elif "image" in issue.description.lower():
                logger.info("Image addition requires manual intervention")

        elif issue.dimension == "time_alignment":
            if "short" in issue.description.lower():
                self._expand_content(lecture, issue)
            elif "long" in issue.description.lower():
                logger.info("Content reduction requires manual review")

    def _add_code_examples(self, lecture: Lecture, issue: Issue) -> None:
        """Add code examples to sections that lack them."""
        # Find sections without code blocks
        sections_without_code = [
            s
            for s in lecture.sections
            if len(s.code_blocks) == 0 and "intro" not in s.section_id.lower() and "conclusion" not in s.section_id.lower()
        ]

        if not sections_without_code:
            return

        logger.info(f"Adding code examples to {len(sections_without_code)} section(s)")

        # Add code examples to up to 3 sections
        for section in sections_without_code[:3]:
            prompt = f"""🚨 CRITICAL: Generate code examples for lecture section

**Section:** {section.title}
**Audience:** {lecture.audience_level}

**REQUIREMENTS:**
- Generate 1-2 complete, runnable Python code examples
- Each example: 20-50 lines MINIMUM
- Include Korean comments explaining EVERY important line
- Show practical, real-world usage
- Include expected output

**FORMAT (MANDATORY):**

### 코드 예제 1: [제목]

[예제 설명 1-2 문장]

```python
# [예제가 보여주는 것]

# 코드 (20-50 lines)
# 각 라인에 한글 주석

# 예상 출력:
# [결과]
```

**설명:**
- [각 단계 설명]

Generate the code examples NOW (in Korean):"""

        try:
            response = self.invoke_llm(prompt, phase="revision")
            code_examples_content = response.content.strip()

            # Clean up outer markdown fences only
            if code_examples_content.startswith("```markdown"):
                code_examples_content = code_examples_content.split("```markdown")[1].split("```")[0].strip()
            elif code_examples_content.startswith("```") and "```python" not in code_examples_content[:20]:
                # Only remove outer fence if it's wrapping the whole content
                parts = code_examples_content.split("```")
                if len(parts) >= 3:
                    code_examples_content = "```".join(parts[1:-1])

            # Append to section
            section.markdown_content += "\n\n" + code_examples_content

            # Re-extract code blocks
            from lecture_forge.agents.content_writer import ContentWriterAgent

            temp_writer = ContentWriterAgent()
            new_code_blocks = temp_writer._extract_code_blocks(section.markdown_content)

            # Update code blocks list (keep only newly extracted ones)
            section.code_blocks = new_code_blocks

            # Recalculate word count
            section.word_count = len(section.markdown_content.split())

            logger.info(f"  ✅ Added {len(new_code_blocks) - len(section.code_blocks)} code example(s) to '{section.title}'")

        except Exception as e:
            logger.error(f"  ❌ {ContentGenerationError(f'Failed to generate code example: {e}')}")

    def _expand_content(self, lecture: Lecture, issue: Issue) -> None:
        """Strategic content expansion - analyzes all sections and expands intelligently."""
        # Import here to avoid circular dependency
        from lecture_forge.utils.content_metrics import calculate_target_metrics

        # Calculate total gap
        total_actual = lecture.total_word_count
        total_target = 0
        section_gaps = []

        for section in lecture.sections:
            # Skip intro/conclusion
            if "intro" in section.section_id.lower() or "conclusion" in section.section_id.lower():
                continue

            # Use section's actual estimated_time and difficulty_level
            estimated_time = section.estimated_time
            difficulty_level = section.difficulty_level

            targets = calculate_target_metrics(estimated_time, difficulty_level)
            gap = targets["target_words"] - section.word_count
            total_target += targets["target_words"]

            if gap > 0:
                section_gaps.append(
                    {
                        "section": section,
                        "gap": gap,
                        "targets": targets,
                        "estimated_time": estimated_time,
                        "priority": gap,  # Higher gap = higher priority
                    }
                )

        total_gap = total_target - total_actual

        if total_gap <= 0:
            logger.info("Word count already sufficient")
            return

        logger.info(f"Total word gap: {total_gap:,} words across {len(section_gaps)} sections")

        # Sort by priority (biggest gaps first)
        section_gaps.sort(key=lambda x: x["priority"], reverse=True)

        # Expand top N sections (up to 80% of total gap)
        target_expansion = int(total_gap * 0.8)
        expanded_total = 0
        max_sections_to_expand = min(3, len(section_gaps))

        for i in range(max_sections_to_expand):
            if expanded_total >= target_expansion:
                break

            item = section_gaps[i]
            section = item["section"]
            gap = item["gap"]

            # Expand this section
            added_words = self._expand_section_with_verification(section=section, target_gap=gap, lecture=lecture)

            expanded_total += added_words
            logger.info(f"  ✅ Expanded '{section.title}': +{added_words} words")

        coverage = (expanded_total / total_gap * 100) if total_gap > 0 else 0
        logger.info(f"Total expansion: +{expanded_total:,} words ({coverage:.1f}% of gap)")

    def _expand_section_with_verification(self, section: "SectionContent", target_gap: int, lecture: Lecture) -> int:
        """Expand a single section with verification."""
        original_content = section.markdown_content
        original_count = section.word_count

        # Build strong expansion prompt
        prompt = f"""🚨 URGENT EXPANSION NEEDED 🚨

**Current Section:** {section.title}
**Current Word Count:** {original_count:,}
**TARGET:** Add {target_gap:,}+ words MINIMUM

**EXISTING CONTENT (DO NOT DUPLICATE):**
{original_content[:1000]}...
{f"(... {original_count - 1000} more words)" if original_count > 1000 else ""}

**YOUR MISSION:**
Expand this section by adding {target_gap:,}+ NEW words.

**EXPANSION STRATEGY (add content in these areas):**

1. **더 깊이 있는 설명** (~{int(target_gap * (0.4 if self.with_code else 0.7))} words):
   - 각 개념을 3-4 문단으로 자세히 설명
   - 실생활 비유와 메타포 사용
   - 역사적 맥락이나 발전 과정 추가
   - "왜 그런가?"에 대한 답변

{_build_expansion_code_section(self.with_code, target_gap)}2. **고급 주제/응용** (~{int(target_gap * 0.2)} words):
   - 실전 팁 5-7가지
   - 성능 최적화 기법
   - 트러블슈팅 가이드
   - 업계 모범 사례

3. **추가 실습 문제** (~{int(target_gap * 0.1)} words):
   - 문제 2-3개 추가
   - 난이도: 쉬움, 보통, 어려움
   - 힌트와 기대 결과 포함

**⚠️ CRITICAL RULES:**
- ✅ MUST add {target_gap:,}+ words
- ✅ DO NOT duplicate existing content
- ✅ MAINTAIN coherence with existing text
- ✅ Use Korean language (한국어)
- ❌ NO summaries - only DETAILED content
- ❌ NO shortcuts

**Audience Level:** {lecture.audience_level}

Generate ONLY the additional content (will be appended to existing):
"""

        try:
            response = self.invoke_llm(prompt, phase="revision")
            additional_content = response.content.strip()

            # Clean up markdown fences
            if "```markdown" in additional_content:
                additional_content = additional_content.split("```markdown")[1].split("```")[0].strip()
            elif additional_content.startswith("```") and additional_content.count("```") >= 2:
                parts = additional_content.split("```")
                if len(parts) >= 3:
                    additional_content = parts[1].strip()

            # Validate expansion
            added_words = len(additional_content.split())

            if added_words < target_gap * 0.5:
                logger.warning(f"  ⚠️  Expansion insufficient: {added_words} < {target_gap * 0.5:.0f} words")
                logger.warning(f"     Retrying with stronger prompt...")

                # Retry with more urgent prompt
                retry_prompt = f"""❌ PREVIOUS ATTEMPT FAILED ❌

You only added {added_words} words but I need {target_gap:,}+ words!

THIS IS YOUR LAST CHANCE. Add {target_gap:,}+ words NOW or fail.

CRITICAL: Write MUCH MORE content. Be extremely detailed and thorough.

{prompt}

WRITE {target_gap:,}+ WORDS NOW (NOT {added_words}):
"""
                response = self.invoke_llm(retry_prompt, phase="revision")
                additional_content = response.content.strip()

                # Clean up again
                if "```markdown" in additional_content:
                    additional_content = additional_content.split("```markdown")[1].split("```")[0].strip()

                added_words = len(additional_content.split())

            # Strip code blocks when --with-code is not set
            if not self.with_code and "```" in additional_content:
                additional_content = _strip_code_blocks(additional_content)
                added_words = len(additional_content.split())

            # Check for duplication (simple check)
            if self._has_significant_overlap(original_content, additional_content):
                logger.warning(f"  ⚠️  Detected content duplication, filtering...")
                # Remove duplicated sentences
                additional_content = self._remove_duplicates(additional_content, original_content)
                added_words = len(additional_content.split())

            # Apply expansion
            section.markdown_content += "\n\n" + additional_content
            section.word_count = len(section.markdown_content.split())  # Recalculate

            actual_increase = section.word_count - original_count
            logger.info(f"     Verified increase: {actual_increase:,} words (added text: {added_words:,} words)")

            return actual_increase

        except Exception as e:
            logger.error(f"  ❌ {ContentGenerationError(f'Failed to expand section: {e}')}")
            import traceback

            logger.debug(traceback.format_exc())
            return 0

    def _has_significant_overlap(self, original: str, new: str) -> bool:
        """Simple duplicate detection."""
        # Check if first 100 words are very similar
        original_start = " ".join(original.split()[:100])
        new_start = " ".join(new.split()[:100])

        # Simple similarity check
        if len(original_start) == 0 or len(new_start) == 0:
            return False

        # Count matching characters
        matches = sum(1 for a, b in zip(original_start, new_start) if a == b)
        similarity = matches / max(len(original_start), len(new_start))

        return similarity > 0.7

    def _remove_duplicates(self, new_content: str, original_content: str) -> str:
        """Remove duplicated sentences."""
        # Split by sentences (simple approach)
        new_sentences = [s.strip() for s in new_content.split(". ") if s.strip()]
        original_sentences = set(s.strip() for s in original_content.split(". ") if s.strip())

        # Keep only unique sentences
        unique_sentences = [s for s in new_sentences if s not in original_sentences]

        if len(unique_sentences) < len(new_sentences) * 0.5:
            logger.warning(f"     Removed {len(new_sentences) - len(unique_sentences)} duplicate sentences")

        return ". ".join(unique_sentences) + "."

    def _add_introduction(self, lecture: Lecture) -> None:
        """Add introduction section."""
        prompt = f"""Create a brief introduction for a lecture on: {lecture.topic}

Duration: {lecture.duration} minutes
Audience: {lecture.audience_level}
Learning Objectives:
{chr(10).join('- ' + obj for obj in lecture.learning_objectives)}

Include:
- Course overview (2-3 sentences)
- What will be covered
- Prerequisites (if any)

Keep it under 300 words. Return markdown format."""

        try:
            response = self.invoke_llm(prompt, phase="revision")
            intro_content = response.content.strip()

            intro_section = SectionContent(
                section_id="section_0_intro",
                title="Introduction",
                markdown_content=intro_content,
                code_blocks=[],
                images=[],
                diagrams=[],
                word_count=len(intro_content.split()),
            )

            lecture.sections.insert(0, intro_section)
            logger.info("Added introduction section")

        except Exception as e:
            logger.error(f"Failed to add introduction: {e}")

    def _add_conclusion(self, lecture: Lecture) -> None:
        """Add conclusion section."""
        # Get key topics from sections
        key_topics = [s.title for s in lecture.sections if "intro" not in s.section_id.lower()][:5]

        prompt = f"""Create a conclusion for a lecture on: {lecture.topic}

Key topics covered:
{chr(10).join('- ' + topic for topic in key_topics)}

Include:
- Summary of key takeaways (3-5 bullet points)
- Next steps for further learning
- Practical applications

Keep it under 300 words. Return markdown format."""

        try:
            response = self.invoke_llm(prompt, phase="revision")
            conclusion_content = response.content.strip()

            conclusion_section = SectionContent(
                section_id=f"section_{len(lecture.sections)}_conclusion",
                title="Conclusion and Next Steps",
                markdown_content=conclusion_content,
                code_blocks=[],
                images=[],
                diagrams=[],
                word_count=len(conclusion_content.split()),
            )

            lecture.sections.append(conclusion_section)
            logger.info("Added conclusion section")

        except Exception as e:
            logger.error(f"Failed to add conclusion: {e}")

    def _add_diagrams(self, lecture: Lecture, issue: Issue) -> None:
        """Add diagrams to sections - FLOWCHART ONLY."""
        # Find sections without diagrams
        sections_without_diagrams = [s for s in lecture.sections if len(s.diagrams) == 0]

        if not sections_without_diagrams:
            return

        section = sections_without_diagrams[0]

        prompt = f"""Create a FLOWCHART diagram (NOT mindmap) for: {section.title}

Context (first 300 chars): {section.markdown_content[:300]}...

**CRITICAL RULES:**
1. Use 'flowchart TD' or 'flowchart LR' ONLY
2. Node IDs: single letters (A, B, C...)
3. Labels: [Korean text] - concise (2-5 words)
4. Connections: A --> B or A -->|label| B
5. Maximum 8 nodes
6. NO mindmaps allowed

**Example:**
```
flowchart TD
    A[개념 정의]
    B[주요 특징]
    C[실제 활용]
    A --> B
    B --> C
```

Return ONLY the flowchart code (no explanations):"""

        try:
            response = self.invoke_llm(prompt, phase="revision")
            mermaid_code = response.content.strip()

            # Clean up markdown code blocks
            if "```mermaid" in mermaid_code:
                mermaid_code = mermaid_code.split("```mermaid")[1].split("```")[0].strip()
            elif "```" in mermaid_code:
                mermaid_code = mermaid_code.split("```")[1].split("```")[0].strip()

            diagram = MermaidDiagram(
                id=f"diagram_{section.section_id}_revised",
                title=f"{section.title} Overview",
                mermaid_code=mermaid_code,
                diagram_type="flowchart",
            )

            section.diagrams.append(diagram)
            logger.info(f"Added diagram to section: {section.title}")

        except Exception as e:
            logger.error(f"Failed to add diagram: {e}")
