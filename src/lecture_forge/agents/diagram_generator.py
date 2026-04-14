"""
Diagram Generator Agent - Generates Mermaid diagrams.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import MermaidDiagram, SectionContent
from lecture_forge.utils import logger
from lecture_forge.utils.mermaid_validator import MermaidValidator, clean_mermaid_code


class DiagramGeneratorAgent(BaseAgent):
    """Agent for generating Mermaid diagrams."""

    def __init__(self):
        super().__init__(thinking=False)
        self.validator = MermaidValidator()
        logger.info("Initializing Diagram Generator Agent with validator")

    def generate_diagrams(
        self,
        section_contents: List[SectionContent],
        curriculum: Optional[Curriculum] = None,
    ) -> List[SectionContent]:
        """
        Generate diagrams for sections and add them to section content.

        Args:
            section_contents: List of section contents
            curriculum: Optional curriculum for section topic context (v0.5.0)

        Returns:
            Updated list of section contents with diagrams
        """
        logger.info(f"Generating diagrams for {len(section_contents)} sections")

        for i, section in enumerate(section_contents):
            # Skip intro and conclusion sections
            if "intro" in section.section_id.lower() or "conclusion" in section.section_id.lower():
                continue

            # v0.5.0: resolve matching Section from curriculum (same index, safe fallback)
            section_obj: Optional[Section] = None
            if curriculum and i < len(curriculum.sections):
                section_obj = curriculum.sections[i]

            # v0.4.0: generate multiple diagrams based on section length
            num_diagrams = min(
                Config.DIAGRAM_MAX_PER_SECTION,
                max(1, section.estimated_time // Config.DIAGRAM_MINUTES_PER),
            )
            logger.info(f"Generating {num_diagrams} diagram(s) for section: {section.title} ({section.estimated_time} min)")

            if num_diagrams == 1:
                diagram = self._generate_diagram_for_section(
                    section, diagram_idx=0, section_obj=section_obj
                )
                if diagram:
                    section.diagrams.append(diagram)
                    logger.info(f"  ✅ Generated {diagram.diagram_type} diagram (#1)")
                else:
                    logger.info("  ℹ️  No diagram generated (#1)")
            else:
                # Parallelize diagram generation when multiple diagrams are needed per section.
                # Results are collected into a dict keyed by diagram_idx to preserve insertion order.
                results: dict = {}
                with ThreadPoolExecutor(max_workers=num_diagrams) as executor:
                    futures = {
                        executor.submit(
                            self._generate_diagram_for_section,
                            section,
                            idx,
                            section_obj,
                        ): idx
                        for idx in range(num_diagrams)
                    }
                    for future in as_completed(futures):
                        idx = futures[future]
                        try:
                            results[idx] = future.result()
                        except Exception as e:
                            logger.error(f"  ❌ Diagram #{idx + 1} generation failed: {e}")
                            results[idx] = None

                for idx in range(num_diagrams):
                    diagram = results.get(idx)
                    if diagram:
                        section.diagrams.append(diagram)
                        logger.info(f"  ✅ Generated {diagram.diagram_type} diagram (#{idx + 1})")
                    else:
                        logger.info(f"  ℹ️  No diagram generated (#{idx + 1})")

        return section_contents

    def _generate_diagram_for_section(
        self,
        section: SectionContent,
        diagram_idx: int = 0,
        section_obj: Optional[Section] = None,
    ) -> Optional[MermaidDiagram]:
        """Generate a Mermaid diagram with validation and retry.

        Args:
            section: Section content to generate diagram for
            diagram_idx: Index within section (0 = primary, 1+ = secondary types)
            section_obj: Optional curriculum Section for topic/RAG context (v0.5.0)
        """
        max_retries = 3
        content_preview = section.markdown_content[:6000] if len(section.markdown_content) > 6000 else section.markdown_content

        for attempt in range(max_retries):
            try:
                # Generate diagram
                mermaid_code = self._call_llm_for_diagram(
                    section, content_preview, attempt,
                    diagram_idx=diagram_idx, section_obj=section_obj,
                )

                if not mermaid_code:
                    continue

                # Clean code
                mermaid_code = clean_mermaid_code(mermaid_code)

                # Detect type
                diagram_type = self._detect_diagram_type(mermaid_code)

                # Validate syntax
                is_valid, error_msg = self.validator.validate(mermaid_code, diagram_type)

                if is_valid:
                    # Evaluate diagram quality
                    quality_score = self._evaluate_diagram_quality(mermaid_code)

                    # Quality threshold from config (.env)
                    min_quality = Config.DIAGRAM_QUALITY_THRESHOLD
                    if quality_score["score"] >= min_quality or attempt == max_retries - 1:
                        if quality_score["score"] >= min_quality:
                            logger.info(
                                f"  ✅ Valid {diagram_type} diagram generated (attempt {attempt + 1}, quality: {quality_score['score']}/100)"
                            )
                        else:
                            logger.warning(
                                f"  ⚠️ Accepting diagram on final attempt (quality: {quality_score['score']}/{min_quality})"
                            )
                        if quality_score["feedback"]:
                            logger.debug(f"     Quality notes: {', '.join(quality_score['feedback'][:2])}")
                        diagram_suffix = f"_{diagram_idx}" if diagram_idx > 0 else ""
                        return MermaidDiagram(
                            id=f"diagram_{section.section_id}{diagram_suffix}",
                            title=f"{section.title} 개요" if diagram_idx == 0 else f"{section.title} 상세 {diagram_idx}",
                            mermaid_code=mermaid_code,
                            diagram_type=diagram_type,
                        )
                    else:
                        logger.warning(f"  ⚠️ Attempt {attempt + 1}: Quality too low ({quality_score['score']}/{min_quality})")
                        logger.warning(f"     Issues: {', '.join(quality_score['feedback'])}")
                        # Continue to retry for better quality
                else:
                    logger.warning(f"  ⚠️ Attempt {attempt + 1}: Invalid syntax: {error_msg}")
                    # Continue to retry

            except Exception as e:
                logger.error(f"  ❌ Attempt {attempt + 1} failed: {e}")

        # v0.4.0: All retries failed — use fallback mindmap instead of skipping
        logger.warning(f"  ⚠️ All {max_retries} attempts failed - using template fallback")
        return self._generate_fallback_diagram(section, diagram_idx=diagram_idx, section_obj=section_obj)

    def _call_llm_for_diagram(
        self,
        section: SectionContent,
        content_preview: str,
        attempt: int,
        diagram_idx: int = 0,
        section_obj: Optional[Section] = None,
    ) -> str:
        """Call LLM to generate diagram with improved prompt.

        diagram_idx=0: primary flowchart (existing logic)
        diagram_idx>0: secondary type (sequence or mindmap)
        section_obj: Optional curriculum Section for topic list and RAG context (v0.5.0)
        """
        # v0.4.0: secondary diagrams use different types
        if diagram_idx > 0:
            section_type = self._detect_secondary_diagram_type(section, diagram_idx)
        else:
            # Detect section type (using both title and content)
            section_type = self._detect_section_type(section.title, content_preview)

        # For sequence/mindmap types use dedicated lightweight prompts
        if section_type == "sequence" and Config.DIAGRAM_ENABLE_SEQUENCE:
            return self._call_llm_for_sequence_diagram(section, content_preview, attempt)
        if section_type == "mindmap" and Config.DIAGRAM_ENABLE_MINDMAP:
            return self._call_llm_for_mindmap_diagram(section, content_preview, attempt)

        # Get appropriate template
        template = self._get_diagram_template(section_type)

        # Add more strict requirements based on attempt number
        strictness_note = ""
        if attempt > 0:
            strictness_note = f"""
**⚠️ PREVIOUS ATTEMPT FAILED - STRICTER RULES:**
- Simplify diagram to max {8 - attempt*2} nodes
- Use ONLY basic Korean text (no parentheses, brackets, quotes)
- Every label MUST be 2-8 words, NO special chars
- Follow the template EXACTLY
"""

        # v0.5.0: enrich prompt with section topics and RAG key chunks
        topics_text = ""
        if section_obj and section_obj.topics:
            topics_text = "\n## 핵심 토픽:\n" + "\n".join(f"- {t}" for t in section_obj.topics)

        rag_context = ""
        if section.rag_key_chunks:
            top_chunks = section.rag_key_chunks[:3]
            rag_context = "\n\n## 원문 참고 자료:\n" + "\n---\n".join(
                chunk[:400] for chunk in top_chunks
            )

        prompt = f"""Create a DETAILED FLOWCHART using SPECIFIC TERMS from the content.

**Section:** {section.title}
**Type:** {section_type}
{topics_text}

**Content (first 6000 chars):**
{content_preview}{rag_context}

**🎯 YOUR TASK: Extract CONCRETE concepts from the content above and show their relationships.**

DO NOT use vague labels like:
❌ "개념 설명", "주요 특징", "작동 원리" (too abstract)
❌ "대규모 언어 모델", "자연어 이해 향상" (disconnected concepts)

INSTEAD, use SPECIFIC technical terms from the content:
✅ "트랜스포머 아키텍처", "셀프 어텐션 계층", "인코더 블록"
✅ "토큰화", "임베딩 생성", "어텐션 계산", "출력 레이어"
✅ "데이터 수집", "전처리 파이프라인", "모델 훈련", "성능 평가"

**🔒 MANDATORY RULES:**

1. **Format**: MUST start with 'flowchart TD' or 'flowchart LR'
2. **Node IDs**: Single uppercase letters (A, B, C, D, E, F, G, H, I, J)
3. **Labels**: [구체적인 기술 용어] - Use ACTUAL terms from content
4. **Connections**: A --> B or A -->|설명| B
5. **Min nodes**: 6-8 (show the actual process/structure)
6. **Max nodes**: 10
7. **NO mindmaps, NO graphs** - ONLY flowcharts
8. **Include decision points** where the content describes choices: A{{조건?}}
9. **Show feedback loops** if the content describes iteration
10. **CRITICAL**: Read the content carefully and extract REAL concepts

**✅ SAFE LABEL FORMAT (USE THESE):**
```
A[개념 설명]              ✓ SAFE - Plain text
B[주요 특징]              ✓ SAFE - Simple Korean
C[작동 원리]              ✓ SAFE - No special chars
D[데이터 수집 단계]       ✓ SAFE - Spaces OK
E[모델 훈련 과정]         ✓ SAFE - Multi-word OK
```

**❌ UNSAFE PATTERNS (WILL BREAK BROWSER RENDERING - DO NOT USE):**
```
A[개념(설명)]             ✗ BREAKS - Has parentheses ()
B[개념: 설명]             ✗ BREAKS - Has colon :
C["특징"]                 ✗ BREAKS - Has quotes ""
D[A->B 흐름]              ✗ BREAKS - Has arrows
E[모델[LLM]]              ✗ BREAKS - Nested brackets
F[중요! 주의]             ✗ BREAKS - Has exclamation !
```

**⚠️ CRITICAL WARNING:**
If you use ANY of the unsafe patterns above, the diagram will:
- Fail to render in browser
- Show parsing errors
- Break the entire lecture page

ONLY use plain Korean text and spaces. NO special characters.

**Examples of converting unsafe to safe:**
```
❌ UNSAFE              →    ✅ SAFE
대형 언어 모델(LLM)    →    대형 언어 모델 LLM
주요 특징: 이해        →    주요 특징 - 이해
데이터(수집)           →    데이터 수집
```

**📋 Template for {section_type}:**
{template}

**🎯 Your Task:**
{self._get_task_instruction_for_type(section_type)}

**💡 Quality Guidelines:**
- Aim for 6-8 nodes (minimum 6, maximum 10)
- Include at least one decision point if the content involves choices/conditions
- Show feedback loops if the process is iterative
- Use concrete technical terms from the content, not abstract concepts
- Create meaningful connections that show actual relationships
- Avoid simple A→B→C→D linear flows

**❌ BAD Example (too abstract - DO NOT do this):**
```
flowchart TD
    A[대규모 언어 모델 LLM]
    B[자연어 이해 향상]
    C[다양한 응용 분야]
    A --> B --> C
```
Problem: Generic concepts, no real information, linear flow

**✅ GOOD Example (specific and informative):**
```
flowchart TD
    A[입력 텍스트 토큰화] --> B[토큰 임베딩 생성]
    B --> C[위치 인코딩 추가]
    C --> D[셀프 어텐션 레이어]
    D --> E[피드포워드 네트워크]
    E --> F{{추가 레이어 필요}}
    F -->|Yes| D
    F -->|No| G[출력 레이어]
    G --> H[확률 분포 생성]
```
Why good: Uses specific technical terms, shows actual process, has decision point and loop

{strictness_note}

Return ONLY the flowchart code (no markdown, no explanations):"""

        response = self.invoke_llm(prompt, phase="diagram_generation")
        diagram_code = response.content.strip()

        # Post-process to remove unsafe patterns that break rendering
        diagram_code = self._clean_unsafe_patterns(diagram_code)

        return diagram_code

    def _clean_unsafe_patterns(self, diagram_code: str) -> str:
        """
        Clean unsafe patterns from LLM-generated Mermaid code.

        Removes patterns that cause browser rendering failures:
        - Parentheses in node labels: A[text(more)] -> A[text more]
        - Colons in node labels: A[text: more] -> A[text - more]

        Args:
            diagram_code: Raw Mermaid code from LLM

        Returns:
            Cleaned Mermaid code safe for rendering
        """
        lines = diagram_code.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip non-node lines (diagram type, connections, empty)
            if not line.strip() or line.strip().startswith("flowchart") or "-->" in line:
                cleaned_lines.append(line)
                continue

            # Process node definition lines: "    A[label text]"
            node_match = re.match(r"^(\s*)([A-Z0-9_]+)\[(.*?)\](.*)$", line)

            if node_match:
                indent, node_id, label, rest = node_match.groups()

                # Clean the label
                original_label = label

                # 1. Remove parentheses and their content or convert to spaces
                # Pattern 1: text(content) -> text content
                label = re.sub(r"\(([^)]*)\)", r" \1", label)

                # 2. Replace colons with hyphens
                label = re.sub(r":\s*", " - ", label)

                # 3. Clean up multiple spaces
                label = " ".join(label.split())

                # 4. Truncate if too long (keep under 50 chars)
                if len(label) > 50:
                    label = label[:50].rsplit(" ", 1)[0]

                # Reconstruct the line
                cleaned_line = f"{indent}{node_id}[{label}]{rest}"

                # Log if changes were made
                if label != original_label:
                    logger.debug(f"Cleaned label: '{original_label}' -> '{label}'")

                cleaned_lines.append(cleaned_line)
            else:
                # Keep the line as-is if it doesn't match node pattern
                cleaned_lines.append(line)

        cleaned_code = "\n".join(cleaned_lines)

        # Log summary of changes
        if cleaned_code != diagram_code:
            logger.info("  🧹 Post-processed diagram to remove unsafe patterns")

        return cleaned_code

    def _get_task_instruction_for_type(self, section_type: str) -> str:
        """
        Get type-specific task instruction for LLM diagram generation.

        Args:
            section_type: Section type (process, architecture, comparison, concept)

        Returns:
            Task instruction string
        """
        instructions = {
            "process": """Extract the SEQUENTIAL STEPS from the content.
- Identify action verbs (수집, 처리, 훈련, 평가, etc.)
- Create a LEFT-TO-RIGHT workflow (flowchart LR)
- Each node = one step in the process
- Connect sequentially: A --> B --> C --> D
- Focus on: Step 1 → Step 2 → Step 3 → Step 4 → Result""",
            "architecture": """Extract the SYSTEM COMPONENTS from the content.
- Identify main system/concept and its components
- Create a TOP-DOWN hierarchy (flowchart TD)
- Use hub-and-spoke or hierarchical structure
- Focus on: System → Components → Sub-components → Output""",
            "comparison": """Extract the COMPARISON ELEMENTS from the content.
- Identify what is being compared
- Create a COMPARISON structure (flowchart TD)
- Show options, characteristics, and conclusions
- Focus on: Topic → Options → Features → Selection""",
            "concept": """Extract the CONCEPT RELATIONSHIPS from the content.
- Identify main concept and its features
- Create a CONCEPTUAL map (flowchart TD)
- Show characteristics, mechanisms, and applications
- Focus on: Concept → Features → Mechanism → Applications""",
            # v0.4.0: new types (handled by dedicated LLM callers, not this flowchart path)
            "sequence": "Show system interaction flows using sequenceDiagram syntax.",
            "mindmap": "Show concept relationships using mindmap syntax.",
        }

        return instructions.get(section_type, instructions["concept"])

    def _detect_secondary_diagram_type(self, section: SectionContent, idx: int) -> str:
        """
        v0.4.0: Determine diagram type for 2nd+ diagrams in a section.

        Chooses a type different from the primary type to add variety.
        Respects DIAGRAM_ENABLE_SEQUENCE and DIAGRAM_ENABLE_MINDMAP config flags.
        """
        content_preview = section.markdown_content[:500]
        primary_type = self._detect_section_type(section.title, content_preview)

        fallback_order = {
            "process":      ["sequence", "mindmap", "concept"],
            "architecture": ["mindmap", "concept", "process"],
            "comparison":   ["concept", "mindmap", "architecture"],
            "concept":      ["mindmap", "sequence", "process"],
        }
        candidates = fallback_order.get(primary_type, ["mindmap", "concept"])

        # Filter out disabled types
        if not Config.DIAGRAM_ENABLE_SEQUENCE:
            candidates = [c for c in candidates if c != "sequence"]
        if not Config.DIAGRAM_ENABLE_MINDMAP:
            candidates = [c for c in candidates if c != "mindmap"]
        if not candidates:
            candidates = ["concept"]

        return candidates[(idx - 1) % len(candidates)]

    def _detect_section_type(self, title: str, content: str = "") -> str:
        """
        Detect section type for appropriate diagram template.

        Args:
            title: Section title
            content: Section content (optional, for content-based detection)

        Returns:
            Section type: "process", "architecture", "comparison", "concept",
                          "sequence", or "mindmap"
        """
        title_lower = title.lower()
        content_preview = content[:500].lower() if content else ""

        # ===== Priority 1: Title-based detection =====

        # Process/Flow (strong indicators)
        process_keywords = ["프로세스", "과정", "방법", "절차", "단계", "훈련", "생성", "구축"]
        if any(k in title_lower for k in process_keywords):
            return "process"

        # Architecture/Structure
        arch_keywords = ["모델", "아키텍처", "구조", "시스템", "프레임워크"]
        if any(k in title_lower for k in arch_keywords):
            # Except for "훈련 방법", "생성 방법" - these are processes
            if not any(k in title_lower for k in ["방법", "과정"]):
                return "architecture"

        # Comparison
        comparison_keywords = ["비교", "차이", "vs", "대비"]
        if any(k in title_lower for k in comparison_keywords):
            return "comparison"

        # ===== Priority 2: Content-based detection =====

        if content_preview:
            # v0.4.0: Sequence detection (API/interaction patterns)
            sequence_keywords = ["api", "요청", "응답", "호출", "통신", "인터페이스", "클라이언트", "서버", "상호작용"]
            seq_count = sum(1 for k in sequence_keywords if k in content_preview)
            if seq_count >= 2 and Config.DIAGRAM_ENABLE_SEQUENCE:
                logger.debug(f"Section type: sequence (keywords: {seq_count})")
                return "sequence"

            # Count sequential indicators in content
            sequential_indicators = [
                "첫째", "둘째", "셋째", "넷째", "먼저", "다음", "그다음", "마지막",
                "1.", "2.", "3.", "4.", "5.", "단계 1", "단계 2", "step 1", "step 2",
            ]
            sequential_count = sum(1 for indicator in sequential_indicators if indicator in content_preview)

            # Strong evidence of process if 3+ sequential indicators
            if sequential_count >= 3:
                logger.debug(f"Section type: process (sequential indicators: {sequential_count})")
                return "process"

            # Check for process action verbs
            action_verbs = [
                "수집", "전처리", "훈련", "검증", "평가", "설정", "초기화",
                "실행", "분석", "구성", "준비", "변환", "적용", "조정",
            ]
            action_count = sum(1 for verb in action_verbs if verb in content_preview)

            if action_count >= 4:
                logger.debug(f"Section type: process (action verbs: {action_count})")
                return "process"

            # Check for component/module keywords (architecture)
            component_keywords = ["컴포넌트", "모듈", "레이어", "계층", "블록", "유닛", "요소"]
            component_count = sum(1 for keyword in component_keywords if keyword in content_preview)

            if component_count >= 2:
                logger.debug(f"Section type: architecture (components: {component_count})")
                return "architecture"

        # ===== Default: Concept =====
        return "concept"

    def _get_diagram_template(self, section_type: str) -> str:
        """
        Get flowchart template based on section type.

        Returns:
            Template string with instructions and example
        """
        templates = {
            "architecture": """flowchart TD
    A[시스템명]
    B[핵심 컴포넌트 1]
    C[핵심 컴포넌트 2]
    D[지원 모듈]
    E[출력]

    A --> B
    A --> C
    B --> D
    C --> D
    D --> E

**DIAGRAM STRUCTURE:**
- Root node (A): Main system/concept name
- Middle nodes (B,C,D): Core components
- Output node (E): Result or output
- Use hub-and-spoke or hierarchical connections""",
            "process": """flowchart LR
    A[단계 1 시작]
    B[단계 2 처리]
    C[단계 3 변환]
    D[단계 4 검증]
    E[단계 5 완료]

    A --> B --> C --> D --> E

**DIAGRAM STRUCTURE:**
- SEQUENTIAL FLOW (left to right)
- Each node = ONE step in the process
- Use action verbs (수집, 처리, 훈련, 평가, etc.)
- Chain connections: A --> B --> C --> D
- NO branches unless parallel paths exist""",
            "comparison": """flowchart TD
    A[비교 주제]
    B[방법 A]
    C[방법 B]
    D[A의 장점]
    E[B의 장점]
    F[선택 기준]

    A --> B
    A --> C
    B --> D
    C --> E
    D --> F
    E --> F

**DIAGRAM STRUCTURE:**
- Root (A): Comparison topic
- Options (B,C): Things being compared
- Features (D,E): Characteristics or advantages
- Conclusion (F): Selection criteria or recommendation""",
            "concept": """flowchart TD
    A[핵심 개념명]
    B[특징 1]
    C[특징 2]
    D[작동 방식]
    E[응용 분야]

    A --> B
    A --> C
    B --> D
    C --> D
    D --> E

**DIAGRAM STRUCTURE:**
- Root (A): Main concept
- Features (B,C): Key characteristics
- Mechanism (D): How it works
- Applications (E): Use cases
- Use hierarchical connections""",
            # v0.4.0: new diagram types
            "sequence": """sequenceDiagram
    participant A as 사용자
    participant B as 시스템
    participant C as 외부서비스

    A->>B: 요청
    B->>C: 처리요청
    C-->>B: 결과반환
    B-->>A: 응답

**DIAGRAM STRUCTURE:**
- participant: 시스템 구성 요소 이름 (실제 컴포넌트명 사용)
- ->>: 동기 요청, -->>: 응답/반환
- 실제 섹션 내용의 시스템 간 상호작용 묘사""",
            "mindmap": """mindmap
    root((핵심주제))
        개념1
            세부내용1
            세부내용2
        개념2
            세부내용3
        개념3
            세부내용4

**DIAGRAM STRUCTURE:**
- root(()): 중심 주제 (짧게 2-3단어)
- 1단계: 주요 개념 (3-4개)
- 2단계: 세부 내용 (각 2-3개)
- 공백과 한글만 사용, 특수문자 금지""",
        }

        return templates.get(section_type, templates["concept"])

    def _detect_diagram_type(self, mermaid_code: str) -> str:
        """Detect diagram type from code."""
        first_line = mermaid_code.strip().split("\n")[0].lower()

        if first_line.startswith("flowchart"):
            return "flowchart"
        elif first_line.startswith("graph"):
            return "graph"
        elif first_line.startswith("mindmap"):
            return "mindmap"
        elif first_line.startswith("classdiagram"):
            return "class"
        elif first_line.startswith("sequencediagram"):
            return "sequence"
        else:
            return "flowchart"  # default

    def _call_llm_for_sequence_diagram(
        self, section: SectionContent, content_preview: str, attempt: int
    ) -> str:
        """v0.4.0: Generate a sequenceDiagram showing system interactions."""
        template = self._get_diagram_template("sequence")
        strictness = ""
        if attempt > 0:
            strictness = f"\n**⚠️ PREVIOUS ATTEMPT FAILED: Simplify to max {4 - attempt} participants and {6 - attempt * 2} messages.**"

        prompt = f"""Create a sequenceDiagram showing interactions for: **{section.title}**

**Content:**
{content_preview}

**Template:**
{template}

**Rules:**
1. MUST start with 'sequenceDiagram'
2. Use 3-4 participants with real names from the content
3. Show 5-8 meaningful messages using actual terminology
4. Use ->>  for requests and -->> for responses/returns
5. Use Korean participant names (실제 시스템명 사용)
6. NO special characters in participant/message names
{strictness}

Return ONLY the sequenceDiagram code (no markdown fences, no explanations):"""

        response = self.invoke_llm(prompt, phase="diagram_generation")
        return response.content.strip()

    def _call_llm_for_mindmap_diagram(
        self, section: SectionContent, content_preview: str, attempt: int
    ) -> str:
        """v0.4.0: Generate a mindmap showing concept relationships."""
        template = self._get_diagram_template("mindmap")
        strictness = ""
        if attempt > 0:
            strictness = f"\n**⚠️ PREVIOUS ATTEMPT FAILED: Simplify to 3 main branches, 2 sub-items each. Plain Korean only.**"

        prompt = f"""Create a mindmap for: **{section.title}**

**Content:**
{content_preview}

**Template:**
{template}

**Rules:**
1. MUST start with 'mindmap'
2. root(()) contains the central topic (2-3 words)
3. 3-4 main branches using real concepts from the content
4. 2-3 sub-items per branch
5. Use ONLY plain Korean text — NO special characters, NO parentheses, NO colons
6. Max 20 nodes total
{strictness}

Return ONLY the mindmap code (no markdown fences, no explanations):"""

        response = self.invoke_llm(prompt, phase="diagram_generation")
        return response.content.strip()

    def _generate_fallback_diagram(
        self,
        section: SectionContent,
        diagram_idx: int = 0,
        section_obj: Optional[Section] = None,
    ) -> Optional[MermaidDiagram]:
        """
        v0.5.0: LLM 실패 시 키워드/토픽 기반 구조화된 flowchart 생성 (LLM 호출 없음).

        Prefers section_obj.topics for node labels; falls back to keyword extraction.
        Returns None only if no usable keywords can be extracted.
        """
        section_type = self._detect_section_type(section.title, section.markdown_content[:500])

        # v0.5.0: use curriculum topics if available for meaningful labels
        if section_obj and section_obj.topics:
            topics = [self._clean_text_for_mermaid(t)[:30] for t in section_obj.topics if t]
            topics = [t for t in topics if t]
        else:
            topics = self._extract_keywords_simple(section.markdown_content, section.title, section_type)

        if not topics:
            return None

        # Build a simple flowchart TD from topics list
        root = self._clean_text_for_mermaid(section.title)[:25] or "핵심개념"
        lines = ["flowchart TD", f"    ROOT[{root}]"]
        for i, topic in enumerate(topics[:6]):
            node_id = chr(65 + i)  # A, B, C, ...
            lines.append(f"    {node_id}[{topic}]")
            lines.append(f"    ROOT --> {node_id}")

        mermaid_code = "\n".join(lines)

        diagram_suffix = f"_{diagram_idx}_fallback" if diagram_idx > 0 else "_fallback"
        return MermaidDiagram(
            id=f"diagram_{section.section_id}{diagram_suffix}",
            title=f"{section.title} 개념 구조",
            mermaid_code=mermaid_code,
            diagram_type="flowchart",
        )

    def _evaluate_sequence_quality(self, mermaid_code: str) -> dict:
        """v0.4.0: Evaluate quality of a sequenceDiagram."""
        participant_count = mermaid_code.count("participant ")
        message_count = mermaid_code.count("->>") + mermaid_code.count("-->>")
        score = min(100, participant_count * 15 + message_count * 10)
        feedback = []
        if participant_count < 2:
            feedback.append("Too few participants (need 3+)")
        if message_count < 4:
            feedback.append("Too few messages (need 5+)")
        return {"score": score, "pass": score >= 60, "feedback": feedback}

    def _evaluate_mindmap_quality(self, mermaid_code: str) -> dict:
        """v0.4.0: Evaluate quality of a mindmap."""
        node_count = len([ln for ln in mermaid_code.split("\n") if ln.strip() and not ln.strip().startswith("mindmap") and not ln.strip().startswith("root")])
        score = min(100, node_count * 8)
        feedback = []
        if node_count < 5:
            feedback.append("Too few nodes (need 6+)")
        return {"score": score, "pass": score >= 60, "feedback": feedback}

    def _create_fallback_diagram(self, section: SectionContent) -> MermaidDiagram:
        """Create a meaningful fallback diagram using content keywords."""
        # Detect section type for targeted keyword extraction
        section_type = self._detect_section_type(section.title, section.markdown_content)

        # Extract key concepts from section content
        keywords = self._extract_keywords_simple(section.markdown_content, section.title, section_type)

        # Create flowchart with type-appropriate structure
        if section_type == "process":
            flowchart_code = self._create_process_fallback(keywords)
        else:
            flowchart_code = self._create_general_fallback(keywords, section.title)

        logger.info(f"  📝 Created {section_type} fallback with {len(keywords)} concepts")

        return MermaidDiagram(
            id=f"diagram_{section.section_id}_fallback",
            title=section.title,
            mermaid_code=flowchart_code.strip(),
            diagram_type="flowchart",
        )

    def _create_process_fallback(self, keywords: list) -> str:
        """
        Create a sequential process flowchart (Left-to-Right).

        Args:
            keywords: List of process steps

        Returns:
            Mermaid flowchart code
        """
        flowchart_code = "flowchart LR\n"

        if len(keywords) >= 3:
            # Sequential chain: A --> B --> C --> D
            for i, kw in enumerate(keywords[:7]):
                node_id = chr(65 + i)
                flowchart_code += f"    {node_id}[{kw}]\n"

            flowchart_code += "    \n"

            # Chain connections
            for i in range(len(keywords[:7]) - 1):
                flowchart_code += f"    {chr(65 + i)} --> {chr(65 + i + 1)}\n"
        else:
            # Minimal process
            for i, kw in enumerate(keywords, 0):
                node_id = chr(65 + i)
                flowchart_code += f"    {node_id}[{kw}]\n"
            if len(keywords) >= 2:
                flowchart_code += f"    A --> B\n"

        return flowchart_code

    def _create_general_fallback(self, keywords: list, title: str) -> str:
        """
        Create a hierarchical concept flowchart (Top-Down).

        Args:
            keywords: List of concepts
            title: Section title

        Returns:
            Mermaid flowchart code
        """
        flowchart_code = "flowchart TD\n"

        if len(keywords) >= 4:
            # Hub-and-spoke with some hierarchy
            flowchart_code += f"    A[{keywords[0]}]\n"
            flowchart_code += f"    B[{keywords[1]}]\n"
            flowchart_code += f"    C[{keywords[2]}]\n"
            flowchart_code += f"    D[{keywords[3]}]\n"
            flowchart_code += "    \n"
            flowchart_code += "    A --> B\n"
            flowchart_code += "    A --> C\n"
            flowchart_code += "    B --> D\n"
            flowchart_code += "    C --> D\n"

            # Add additional nodes if available
            if len(keywords) >= 5:
                flowchart_code += f"    E[{keywords[4]}]\n"
                flowchart_code += "    D --> E\n"
            if len(keywords) >= 6:
                flowchart_code += f"    F[{keywords[5]}]\n"
                flowchart_code += "    D --> F\n"
            if len(keywords) >= 7:
                flowchart_code += f"    G[{keywords[6]}]\n"
                flowchart_code += "    E --> G\n"
        else:
            # Minimal hub-and-spoke
            main_topic = self._clean_text_for_mermaid(title)[:30]
            flowchart_code += f"    A[{main_topic}]\n"
            for i, kw in enumerate(keywords[:3], 1):
                node_id = chr(65 + i)
                flowchart_code += f"    {node_id}[{kw}]\n"
                flowchart_code += f"    A --> {node_id}\n"

        return flowchart_code

    def _extract_keywords_simple(self, content: str, title: str, section_type: str = "concept") -> list:
        """
        Extract key concepts without LLM (rule-based approach).

        Args:
            content: Section markdown content
            title: Section title
            section_type: Section type for targeted extraction

        Returns:
            List of cleaned keywords (max 7)
        """
        keywords = []

        # 1. Main keyword from title (always first)
        title_clean = title.replace("(", "").replace(")", "")
        main_word = " ".join(title_clean.split()[:3]) if title_clean.split() else "주제"
        keywords.append(self._clean_text_for_mermaid(main_word))

        # 2. Type-specific extraction
        if section_type == "process":
            keywords.extend(self._extract_process_keywords(content))
        elif section_type == "architecture":
            keywords.extend(self._extract_architecture_keywords(content))
        else:
            # Concept or comparison - general extraction
            keywords.extend(self._extract_general_keywords(content))

        # 3. Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw) > 1:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        # 4. Ensure minimum keywords
        if len(unique_keywords) < 4:
            defaults = self._get_default_keywords(section_type)
            for default in defaults:
                if len(unique_keywords) >= 6:
                    break
                if default.lower() not in seen:
                    unique_keywords.append(default)

        return unique_keywords[:7]  # Max 7 keywords

    def _extract_process_keywords(self, content: str) -> list:
        """Extract process/workflow keywords (action verbs and steps)."""
        keywords = []

        # Extract numbered steps (1., 2., 3.)
        step_pattern = r"(\d+)\.\s*\*?\*?([가-힣\s]{2,20})\*?\*?"
        step_matches = re.findall(step_pattern, content)
        for num, step in step_matches[:6]:
            clean_step = self._clean_text_for_mermaid(step)
            if clean_step and not any(meta in clean_step.lower() for meta in ["정의", "중요성", "소개", "서론"]):
                keywords.append(clean_step)

        # Extract action verbs
        action_verbs = [
            "데이터 수집",
            "전처리",
            "모델 훈련",
            "검증",
            "평가",
            "배포",
            "데이터 준비",
            "학습",
            "테스트",
            "최적화",
            "초기화",
            "설정",
            "구성",
            "실행",
            "분석",
            "변환",
        ]
        content_lower = content.lower()
        for verb in action_verbs:
            if verb in content_lower:
                keywords.append(verb)
                if len(keywords) >= 6:
                    break

        return keywords

    def _extract_architecture_keywords(self, content: str) -> list:
        """Extract architecture/component keywords."""
        keywords = []

        # Extract component/module mentions
        component_patterns = [
            r"([가-힣\s]{2,15})\s*컴포넌트",
            r"([가-힣\s]{2,15})\s*모듈",
            r"([가-힣\s]{2,15})\s*레이어",
            r"([가-힣\s]{2,15})\s*계층",
        ]

        for pattern in component_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:3]:
                clean_match = self._clean_text_for_mermaid(match)
                if clean_match:
                    keywords.append(clean_match)

        # Extract from headers (architecture often has clear sections)
        keywords.extend(self._extract_headers(content))

        return keywords

    def _extract_general_keywords(self, content: str) -> list:
        """Extract general keywords from headers and bold text."""
        keywords = []

        # Extract from headers
        keywords.extend(self._extract_headers(content))

        # Extract from bold text
        keywords.extend(self._extract_bold_text(content))

        return keywords

    def _extract_headers(self, content: str) -> list:
        """Extract keywords from markdown headers."""
        keywords = []
        lines = content.split("\n")

        # Filter meta headers
        meta_keywords = ["서론", "결론", "정의", "중요성", "소개", "요약", "개요"]

        for line in lines:
            stripped = line.strip()
            # h4 headers (####)
            if stripped.startswith("####") and not stripped.startswith("#####"):
                header = stripped.replace("#", "").strip()
                if header and len(header) < 25:
                    if not any(meta in header for meta in meta_keywords):
                        clean_h = self._clean_text_for_mermaid(header)
                        if clean_h:
                            keywords.append(clean_h)

        return keywords[:5]

    def _extract_bold_text(self, content: str) -> list:
        """Extract keywords from bold text (technical terms)."""
        keywords = []

        bold_pattern = r"\*\*([^*]{2,20})\*\*"
        bold_matches = re.findall(bold_pattern, content)

        for match in bold_matches[:10]:
            if match.strip() and len(match.split()) <= 4:  # Max 4 words
                clean_match = self._clean_text_for_mermaid(match)
                if clean_match:
                    keywords.append(clean_match)

        return keywords

    def _get_default_keywords(self, section_type: str) -> list:
        """Get default keywords based on section type."""
        defaults = {
            "process": ["시작", "처리", "변환", "검증", "완료"],
            "architecture": ["시스템", "핵심 모듈", "처리 계층", "출력"],
            "comparison": ["옵션 A", "옵션 B", "장점", "선택"],
            "concept": ["핵심 개념", "주요 특징", "작동 방식", "활용"],
        }
        return defaults.get(section_type, defaults["concept"])

    def _clean_text_for_mermaid(self, text: str) -> str:
        """
        Clean text to be safe for Mermaid labels.

        Handles Korean text + special characters that cause rendering issues.
        """
        # Replace colons with hyphens (safer for Mermaid)
        text = text.replace(":", " -")

        # Replace parentheses with spaces (preserve content)
        # e.g., "LLM(Large Language Model)" → "LLM Large Language Model"
        text = text.replace("(", " ").replace(")", " ")

        # Remove brackets that conflict with Mermaid syntax
        text = text.replace("[", "").replace("]", "")
        text = text.replace("{", "").replace("}", "")

        # Remove quotes
        text = text.replace('"', "").replace("'", "")

        # Remove exclamation and question marks
        text = text.replace("!", "").replace("?", "")

        # Remove markdown symbols
        text = text.replace("*", "").replace("#", "")

        # Keep only safe characters: alphanumeric, spaces, and basic punctuation
        # Allow Korean characters, English, numbers, spaces, hyphens, underscores, commas, periods
        clean = "".join(c for c in text if c.isalnum() or c in " -_,.")

        # Remove multiple spaces
        clean = " ".join(clean.split())

        # Limit length to prevent overflow
        if len(clean) > 40:
            clean = clean[:40].rsplit(" ", 1)[0]  # Cut at word boundary

        return clean.strip()

    def _evaluate_diagram_quality(self, mermaid_code: str) -> dict:
        """
        Evaluate diagram complexity and quality.

        v0.4.0: Dispatches to type-specific evaluators for sequence/mindmap.

        Returns:
            dict with 'score' (0-100), 'pass' (bool), 'feedback' (list)
        """
        first_line = mermaid_code.strip().split("\n")[0].lower()
        if first_line.startswith("sequencediagram"):
            return self._evaluate_sequence_quality(mermaid_code)
        if first_line.startswith("mindmap"):
            return self._evaluate_mindmap_quality(mermaid_code)

        # Existing flowchart/graph quality evaluation
        lines = [line.strip() for line in mermaid_code.split("\n") if line.strip() and not line.strip().startswith("flowchart")]

        # Count nodes and connections
        node_lines = [line for line in lines if "[" in line and "]" in line and "-->" not in line]
        connection_lines = [line for line in lines if "-->" in line]
        decision_lines = [line for line in lines if "{" in line and "}" in line and "-->" not in line]

        node_count = len(node_lines)
        connection_count = len(connection_lines)
        decision_count = len(decision_lines)

        # Check for feedback loops (connections going backwards)
        has_loop = False
        for line in connection_lines:
            if "-->" in line:
                parts = line.split("-->")
                if len(parts) >= 2:
                    from_node = parts[0].strip().split()[0]
                    to_node = parts[1].strip().split()[0]
                    if from_node > to_node:  # Simple heuristic for backwards connection
                        has_loop = True
                        break

        # Scoring
        score = 0
        feedback = []

        # Node count (max 40 points)
        if node_count < 4:
            feedback.append("Too few nodes (need 6-8)")
            score += node_count * 5
        elif node_count < 6:
            feedback.append("Below optimal node count (need 6-8)")
            score += 25
        elif 6 <= node_count <= 10:
            score += 40
        else:
            feedback.append("Too many nodes (keep under 10)")
            score += 30

        # Connection complexity (max 30 points)
        avg_connections_per_node = connection_count / max(node_count, 1)
        if avg_connections_per_node < 1.0:
            feedback.append("Too linear: Add branches or loops")
            score += 10
        elif avg_connections_per_node >= 1.2:
            score += 30
        else:
            score += 20

        # Decision points (max 15 points)
        if decision_count == 0:
            feedback.append("No decision points: Consider adding conditional logic")
            score += 0
        elif decision_count == 1:
            score += 10
        else:
            score += 15

        # Feedback loops (max 15 points)
        if has_loop:
            score += 15
        else:
            feedback.append("No feedback loops: Consider adding if process is iterative")
            score += 0

        return {
            "score": min(score, 100),
            "pass": score >= 60,
            "feedback": feedback,
            "node_count": node_count,
            "connection_count": connection_count,
            "decision_count": decision_count,
            "has_loop": has_loop,
        }
