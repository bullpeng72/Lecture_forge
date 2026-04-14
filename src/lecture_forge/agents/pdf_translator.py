"""
PDF Translator Agent - Translates English PDF documents to Korean lecture materials.

Extracts chapter structure from PDF (TOC → font size → page groups),
translates each chapter to Korean, and assigns PDF images by page location.
CurriculumDesigner is bypassed — original PDF chapter order is preserved exactly.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lecture_forge.agents.base import BaseAgent
from lecture_forge.agents.content_writer.image_selector import ImageSelector
from lecture_forge.exceptions import PDFStructureExtractionError, TranslationError
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import SectionContent
from lecture_forge.utils import logger


class PDFTranslatorAgent(BaseAgent):
    """
    Agent that translates English PDF documents to Korean lecture materials.

    Pipeline:
      1. extract_structure()     — PDF chapter detection (TOC / font / groups)
      2. build_curriculum()      — Curriculum creation, preserving PDF order
      3. translate_chapters()    — Per-chapter LLM translation
      4. assign_images_to_sections() — Page-range image matching
    """

    TRANSLATION_TOKEN_LIMIT = 2500  # word count per LLM call

    def __init__(self, pdf_path: str) -> None:
        super().__init__(thinking=False)
        self.pdf_path = str(Path(pdf_path).resolve())
        self.image_selector = ImageSelector()

    # ── Public Interface ───────────────────────────────────────────────────────

    def extract_structure(self) -> List[dict]:
        """
        Extract chapter structure from PDF.

        Priority: TOC → font size analysis → page groups.

        Returns:
            List of chapter dicts:
            [{title, level, start_page, end_page, pages, raw_text}, ...]
        """
        try:
            import fitz
        except ImportError:
            raise PDFStructureExtractionError(
                "PyMuPDF (fitz) is required. Install with: pip install pymupdf"
            )

        doc = fitz.open(self.pdf_path)
        logger.info(
            f"PDFTranslatorAgent: Opened '{Path(self.pdf_path).name}' ({len(doc)} pages)"
        )

        # Priority 1: TOC
        chapters = self._extract_from_toc(doc)
        if chapters:
            logger.info(f"  ✅ TOC found: {len(chapters)} chapters")
            chapters = self._add_raw_text(doc, chapters)
            return self._filter_chapters(chapters)

        # Priority 2: Font size analysis
        chapters = self._extract_by_font_size(doc)
        if chapters:
            logger.info(f"  ✅ Font-based structure: {len(chapters)} chapters")
            chapters = self._add_raw_text(doc, chapters)
            return self._filter_chapters(chapters)

        # Priority 3: Page groups (fallback)
        chapters = self._extract_by_page_groups(doc)
        logger.info(f"  ✅ Page-group fallback: {len(chapters)} chapters")
        chapters = self._add_raw_text(doc, chapters)
        return self._filter_chapters(chapters)

    def build_curriculum(
        self,
        chapters: List[dict],
        topic: str,
        audience_level: str = "intermediate",
    ) -> Tuple[Curriculum, Dict[str, List[int]]]:
        """
        Build a Curriculum from extracted chapters, preserving PDF order.

        Note: chapter_page_map is returned separately (not stored in Curriculum)
        because Pydantic BaseModel does not allow dynamic attributes.

        Returns:
            (curriculum, chapter_page_map)
            where chapter_page_map = {"section_0_intro": [1, 2, 3], ...}
        """
        sections: List[Section] = []
        chapter_page_map: Dict[str, List[int]] = {}

        total_pages = sum(len(ch.get("pages", [])) for ch in chapters)
        total_minutes = max(30, total_pages * 2)
        per_section_time = max(10, total_minutes // max(1, len(chapters)))

        for idx, chapter in enumerate(chapters):
            section_id = f"section_{idx}_{self._slugify(chapter['title'])}"
            section = Section(
                id=section_id,
                title=chapter["title"],
                topics=[chapter["title"]],
                estimated_time=per_section_time,
                difficulty_level=audience_level,
                learning_outcomes=[],
            )
            sections.append(section)
            chapter_page_map[section_id] = chapter.get("pages", [])

        # Use fixed Korean objectives to avoid English title bleed-through
        _default_objectives = [
            f"핵심 개념 이해 및 실무 적용 능력 배양 ({topic})",
            "주요 이론과 기술 스택의 작동 원리 파악",
            "단계별 예시를 통한 개념 내재화",
            "실제 사례 분석을 통한 문제 해결 역량 습득",
            "최신 트렌드와 모범 사례(Best Practice) 이해",
        ]
        learning_objectives = _default_objectives[:min(5, len(chapters))]

        curriculum = Curriculum(
            topic=topic,
            duration=total_minutes,
            audience_level=audience_level,
            learning_objectives=learning_objectives,
            sections=sections,
            total_estimated_time=total_minutes,
            source_files=[self.pdf_path],
        )

        return curriculum, chapter_page_map

    def translate_chapters(
        self,
        chapters: List[dict],
        curriculum: Curriculum,
        skip_translation: bool = False,
    ) -> List[SectionContent]:
        """
        Translate each chapter to Korean and return SectionContent list.

        Args:
            chapters: Chapter dicts from extract_structure()
            curriculum: Built curriculum (sections used for metadata)
            skip_translation: If True, keep original English text

        Returns:
            List of SectionContent objects (images not yet assigned)
        """
        section_contents: List[SectionContent] = []
        prev_title: Optional[str] = None

        for idx, (chapter, section) in enumerate(zip(chapters, curriculum.sections)):
            icon = "⏭️ " if skip_translation else "🌐"
            logger.info(f"  {icon} [{idx + 1}/{len(chapters)}] {chapter['title']}")

            raw_text = chapter.get("raw_text", "")

            if skip_translation:
                translated_body = raw_text
                translated_title = chapter["title"]
            else:
                # Protect code blocks before translation
                protected_text, code_map = self._protect_code_blocks(raw_text)

                # Translate body
                translated_body = self._translate_chapter_text(
                    protected_text, chapter["title"], prev_title
                )

                # Restore code blocks
                translated_body = self._restore_code_blocks(translated_body, code_map)

                # Translate section title
                translated_title = self._translate_title(chapter["title"])

            # Sync translated title back into curriculum.sections[idx]
            curriculum.sections[idx] = Section(
                id=section.id,
                title=translated_title,
                topics=section.topics,
                estimated_time=section.estimated_time,
                difficulty_level=section.difficulty_level,
                learning_outcomes=section.learning_outcomes,
            )

            content = SectionContent(
                section_id=section.id,
                title=translated_title,
                markdown_content=translated_body,
                word_count=len(translated_body.split()),
                estimated_time=section.estimated_time,
                difficulty_level=section.difficulty_level,
            )
            section_contents.append(content)
            prev_title = chapter["title"]

        return section_contents

    def assign_images_to_sections(
        self,
        section_contents: List[SectionContent],
        chapter_page_map: Dict[str, List[int]],
        available_images: List[dict],
        curriculum: Curriculum,
    ) -> List[SectionContent]:
        """
        Assign PDF images to sections based on their page range.

        Builds synthetic context_metadatas (matching _calculate_page_importance()
        key format) for each section and delegates to the existing ImageSelector.

        Args:
            section_contents: Translated section contents (images=[] initially)
            chapter_page_map: Maps section_id → list of PDF page numbers
            available_images: Images collected by ImageCollectorAgent
            curriculum: Curriculum with Section objects (for ImageSelector)

        Returns:
            section_contents with .images populated
        """
        if not available_images:
            logger.info("  ⚠️  No images available — skipping image assignment")
            return section_contents

        # Track globally used image IDs to prevent cross-section duplication
        globally_used_ids: set = set()

        for section_content in section_contents:
            section_id = section_content.section_id
            pages = chapter_page_map.get(section_id, [])

            if not pages:
                continue

            # Look up the Section object (needed by ImageSelector.select_images)
            section = next(
                (s for s in curriculum.sections if s.id == section_id), None
            )
            if section is None:
                continue

            # Exclude images already used in previous sections
            remaining_images = [
                img for img in available_images
                if img.get("id") not in globally_used_ids
            ]
            if not remaining_images:
                logger.debug(f"     🖼️  {section.title}: no remaining images after dedup")
                continue

            # Build synthetic context_metadatas for _calculate_page_importance()
            context_metadatas = self._build_synthetic_context_metadatas(pages)

            # Delegate to existing ImageSelector
            selected = self.image_selector.select_images(
                section, remaining_images, context_metadatas
            )
            section_content.images = selected

            # Register selected image IDs globally
            for img_ref in selected:
                globally_used_ids.add(img_ref.image_id)

            logger.debug(
                f"     🖼️  {section.title}: {len(selected)} images assigned"
            )

        return section_contents

    # ── Structure Extraction (private) ────────────────────────────────────────

    def _extract_from_toc(self, doc) -> List[dict]:
        """Extract chapter structure using PDF TOC (most accurate method)."""
        toc = doc.get_toc()  # [[level, title, page_num], ...]
        if not toc:
            return []

        # Use only top 2 nesting levels to avoid micro-chapter fragmentation
        levels_present = sorted(set(item[0] for item in toc))
        top_levels = set(levels_present[:2])
        toc_filtered = [item for item in toc if item[0] in top_levels]

        if len(toc_filtered) < 2:
            return []

        total_pages = len(doc)
        chapters = []

        for i, (level, title, page_num) in enumerate(toc_filtered):
            # end_page = start of next entry - 1 (or last page)
            if i + 1 < len(toc_filtered):
                end_page = toc_filtered[i + 1][2] - 1
            else:
                end_page = total_pages

            start_page = page_num
            pages = list(range(start_page, min(end_page + 1, total_pages + 1)))

            chapters.append(
                {
                    "title": title.strip(),
                    "level": level,
                    "start_page": start_page,
                    "end_page": end_page,
                    "pages": pages,
                    "raw_text": "",
                }
            )

        return chapters

    def _extract_by_font_size(self, doc) -> List[dict]:
        """Detect chapter headings by comparing font size to body text median."""
        total_pages = len(doc)

        # Gather all font sizes to compute body (median) size
        all_sizes: List[float] = []
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        if size > 0:
                            all_sizes.append(size)

        if not all_sizes:
            return []

        all_sizes.sort()
        body_size = all_sizes[len(all_sizes) // 2]
        heading_threshold = body_size * 1.2

        chapters: List[dict] = []
        seen_titles: set = set()

        for page_num, page in enumerate(doc, start=1):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        text = span.get("text", "").strip()

                        if (
                            size >= heading_threshold
                            and 3 < len(text) < 200
                            and text not in seen_titles
                        ):
                            seen_titles.add(text)
                            chapters.append(
                                {
                                    "title": text,
                                    "level": 1,
                                    "start_page": page_num,
                                    "end_page": page_num,
                                    "pages": [page_num],
                                    "raw_text": "",
                                }
                            )

        if not chapters:
            return []

        # Set end_page for each chapter = start_page of next chapter - 1
        for i in range(len(chapters) - 1):
            chapters[i]["end_page"] = chapters[i + 1]["start_page"] - 1
            chapters[i]["pages"] = list(
                range(chapters[i]["start_page"], chapters[i]["end_page"] + 1)
            )
        chapters[-1]["end_page"] = total_pages
        chapters[-1]["pages"] = list(range(chapters[-1]["start_page"], total_pages + 1))

        # Remove empty chapters
        chapters = [ch for ch in chapters if ch["pages"]]

        # If too many micro-chapters, subsample to keep ≤ 30
        if len(chapters) > 30:
            step = max(1, len(chapters) // 20)
            chapters = chapters[::step]

        return chapters[:30]

    def _extract_by_page_groups(self, doc, group_size: int = 5) -> List[dict]:
        """Fallback: split PDF into equal-sized page groups."""
        total_pages = len(doc)
        chapters: List[dict] = []

        for start in range(1, total_pages + 1, group_size):
            end = min(start + group_size - 1, total_pages)
            chapters.append(
                {
                    "title": f"Part {len(chapters) + 1} (pp. {start}–{end})",
                    "level": 1,
                    "start_page": start,
                    "end_page": end,
                    "pages": list(range(start, end + 1)),
                    "raw_text": "",
                }
            )

        return chapters

    def _add_raw_text(self, doc, chapters: List[dict]) -> List[dict]:
        """Extract raw text from PDF pages for each chapter (1-indexed pages)."""
        total_pages = len(doc)
        for chapter in chapters:
            text_parts = []
            for page_num in chapter.get("pages", []):
                if 1 <= page_num <= total_pages:
                    page = doc[page_num - 1]  # fitz is 0-indexed
                    text_parts.append(page.get_text())
            chapter["raw_text"] = self._clean_raw_text("\n\n".join(text_parts))
        return chapters

    def _clean_raw_text(self, text: str) -> str:
        """Remove PDF artifacts: page numbers, watermarks, and short artifact lines."""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Skip standalone page numbers (1-4 digits alone on a line)
            if re.match(r"^\d{1,4}$", stripped):
                continue
            # Skip common PDF watermarks / repeated domain URLs (e.g. DailyDoseofDS.com)
            if re.match(r"^[\w.-]+\.(com|org|net|io|ai)\s*$", stripped, re.IGNORECASE):
                continue
            # Skip very short artifact lines (1-2 non-space chars)
            if len(stripped) <= 2:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    # Minimum word count for a section to be included
    _MIN_SECTION_WORDS = 30
    # Minimum alphanumeric characters required for a valid TOC title
    _MIN_TITLE_ALNUM = 2

    def _is_toc_content(self, text: str) -> bool:
        """Detect if text is a Table of Contents page (dot-leaders + page numbers)."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 5:
            return False
        dot_number = re.compile(r"\.{3,}\s*\d+\s*$")
        matches = sum(1 for l in lines if dot_number.search(l))
        return matches / len(lines) > 0.4

    def _extract_fallback_title(self, raw_text: str) -> Optional[str]:
        """
        Infer a chapter title from raw text when the PDF TOC title is empty.

        Scans the first lines for a short, meaningful phrase (3–80 chars).
        Returns None if no suitable candidate is found.
        """
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        for line in lines[:20]:
            # Skip standalone page numbers
            if re.match(r"^\d{1,4}$", line):
                continue
            # Skip domain watermarks / URLs
            if re.match(r"^[\w.-]+\.(com|org|net|io|ai)\s*$", line, re.IGNORECASE):
                continue
            # Must be in title-like length range and have enough content
            if len(line) < 3 or len(line) > 80:
                continue
            if sum(1 for c in line if c.isalnum()) < 3:
                continue
            return line
        # Fallback: truncate first long line at word boundary (same guards as above)
        for line in lines[:10]:
            if re.match(r"^\d{1,4}$", line):
                continue
            if re.match(r"^[\w.-]+\.(com|org|net|io|ai)\s*$", line, re.IGNORECASE):
                continue
            if len(line) >= 3 and sum(1 for c in line if c.isalnum()) >= 3:
                return line[:80].rsplit(" ", 1)[0]
        return None

    def _filter_chapters(self, chapters: List[dict]) -> List[dict]:
        """
        Remove low-quality chapters:
          - TOC pages (table of contents embedded as body text)
          - Empty / near-empty sections (< _MIN_SECTION_WORDS words)
          - Chapters with empty/meaningless TOC titles (recover from raw_text or discard)
        """
        before = len(chapters)
        filtered = []
        for ch in chapters:
            raw = ch.get("raw_text", "")
            if self._is_toc_content(raw):
                logger.debug(f"  🗑️  Filtered TOC page: '{ch['title']}'")
                continue
            if len(raw.split()) < self._MIN_SECTION_WORDS:
                logger.debug(
                    f"  🗑️  Filtered empty section ({len(raw.split())} words): '{ch['title']}'"
                )
                continue
            # Recover chapters whose PDF TOC title is empty or purely decorative
            title_alnum = sum(1 for c in ch["title"] if c.isalnum())
            if title_alnum < self._MIN_TITLE_ALNUM:
                fallback = self._extract_fallback_title(raw)
                if fallback:
                    logger.info(
                        f"  🔧 Recovered empty TOC title from content → '{fallback[:60]}'"
                    )
                    ch = {**ch, "title": fallback}
                else:
                    logger.debug(f"  🗑️  Filtered untitled section: no fallback found")
                    continue
            filtered.append(ch)
        removed = before - len(filtered)
        if removed:
            logger.info(f"  🧹 Filtered {removed} low-quality sections ({before} → {len(filtered)})")
        return filtered

    # ── Translation (private) ─────────────────────────────────────────────────

    def _protect_code_blocks(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Replace code blocks and inline code with __CODE_BLOCK_N__ placeholders."""
        code_map: Dict[str, str] = {}
        counter = [0]

        def replace_block(match: re.Match) -> str:
            key = f"__CODE_BLOCK_{counter[0]}__"
            code_map[key] = match.group(0)
            counter[0] += 1
            return key

        # Fenced code blocks (``` or ~~~)
        text = re.sub(r"```[\s\S]*?```", replace_block, text)
        text = re.sub(r"~~~[\s\S]*?~~~", replace_block, text)
        # Inline code
        text = re.sub(r"`[^`\n]+`", replace_block, text)

        return text, code_map

    def _restore_code_blocks(self, text: str, code_map: Dict[str, str]) -> str:
        """Restore __CODE_BLOCK_N__ placeholders to original code."""
        for key, original in code_map.items():
            text = text.replace(key, original)
        return text

    # AI/ML 표준 용어 사전 (번역 일관성 보장)
    _TERM_GLOSSARY = """
AI/ML 표준 용어 사전 (반드시 아래 표를 따를 것):
- Transformer → 트랜스포머 (변압기 X)
- Agent / Agents → 에이전트 (대리인 X)
- Agentic → 에이전틱 (주체적 X, 행동적 X)
- Multi-Agent → 멀티 에이전트
- Context Engineering → 컨텍스트 엔지니어링 (맥락 공학 X)
- Context Window → 컨텍스트 윈도우
- Prompt Engineering → 프롬프트 엔지니어링
- Fine-tuning → 파인튜닝 (미세 조정으로 병기 가능: 파인튜닝(미세 조정))
- Embedding → 임베딩
- Token / Tokenization → 토큰 / 토크나이제이션
- Inference → 추론
- Attention / Self-Attention → 어텐션 / 셀프 어텐션
- Hallucination → 환각(Hallucination)
- RAG (Retrieval-Augmented Generation) → RAG (검색 증강 생성)
- Vector Database → 벡터 데이터베이스
- LLM (Large Language Model) → LLM (대형 언어 모델)
- Reinforcement Learning → 강화 학습
- Quantization → 양자화(Quantization)
- Benchmark → 벤치마크
- Pipeline → 파이프라인
- Framework → 프레임워크
- Dataset → 데이터셋
고유명사 (번역하지 않고 원문 유지):
- LitServe, LangChain, ChromaDB, OpenAI, Anthropic, Claude, GPT, BERT, LoRA, MCP,
  HyDE, REFRAG, CAG, GRPO, ReAct, vLLM, Opik, Reveal.js, PyTorch, TensorFlow
"""

    # LLM이 제목 대신 반환하는 대화형 응답 패턴 (원본 제목으로 폴백)
    _TITLE_FILLER_PATTERNS = [
        "입력해 주세요",
        "제공해 주시면",
        "번역해 드리겠습니다",
        "알려 주세요",
        "주시면 번역",
    ]

    def _translate_title(self, title: str) -> str:
        """Translate a single section title to Korean (concise)."""
        clean_title = title.strip()

        # Input guard: 비어있거나 의미있는 문자(alphanumeric)가 2개 미만이면 LLM 호출 불필요
        alnum_count = sum(1 for c in clean_title if c.isalnum())
        if alnum_count < 2:
            return title  # 장식 문자 전용(✦ ◆ 등) 또는 공백 — 번역 불가

        prompt = (
            f"다음 영어 챕터 제목을 한국어로 번역하세요.\n"
            f"번역 결과 텍스트만 출력하세요. '제목:', '타이틀:' 같은 접두어를 붙이지 마세요.\n"
            f"간결하게(25자 이내) 번역하세요.\n"
            f"예: 'Introduction' → '소개', 'Chapter 1' → '1장', 'Getting Started' → '시작하기'\n\n"
            f"번역할 제목: {title}"
        )
        try:
            response = self.invoke_llm(prompt, phase="translate_title")
            translated = response.content.strip()
            # Strip common LLM label prefixes
            for prefix in ["제목:", "타이틀:", "Title:", "번역:", "**번역**:", "한국어:"]:
                if translated.startswith(prefix):
                    translated = translated[len(prefix):].strip()
            # Remove surrounding markdown bold markers if present
            translated = translated.strip("*").strip()
            # Output guard: LLM이 번역 대신 대화형 응답을 반환한 경우 원본 유지
            if any(p in translated for p in self._TITLE_FILLER_PATTERNS):
                logger.debug(f"  ⚠️  Title filler response detected for '{title}' — keeping original")
                return title
            return translated if translated else title
        except Exception as e:
            logger.debug(f"  ⚠️  Title translation failed for '{title}': {e}")
            return title  # Fallback: keep original

    def _translate_chapter_text(
        self,
        raw_text: str,
        chapter_title: str,
        prev_title: Optional[str] = None,
    ) -> str:
        """
        Translate a chapter's text to Korean.

        If text exceeds TRANSLATION_TOKEN_LIMIT words, splits by paragraphs
        and translates each chunk separately (sliding window approach).
        """
        words = raw_text.split()
        if not words:
            return ""

        if len(words) <= self.TRANSLATION_TOKEN_LIMIT:
            return self._translate_chunk(raw_text, chapter_title, prev_title)

        # Split into paragraph-delimited chunks
        paragraphs = raw_text.split("\n\n")
        chunks: List[str] = []
        current: List[str] = []
        current_words = 0

        for para in paragraphs:
            para_words = len(para.split())
            if current_words + para_words > self.TRANSLATION_TOKEN_LIMIT and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_words = para_words
            else:
                current.append(para)
                current_words += para_words

        if current:
            chunks.append("\n\n".join(current))

        translated_parts: List[str] = []
        for i, chunk in enumerate(chunks):
            translated_part = self._translate_chunk(
                chunk, chapter_title, prev_title, is_continuation=(i > 0)
            )
            translated_parts.append(translated_part)

        return "\n\n".join(translated_parts)

    def _translate_chunk(
        self,
        text: str,
        chapter_title: str,
        prev_title: Optional[str] = None,
        is_continuation: bool = False,
    ) -> str:
        """Translate a single text chunk to Korean using the LLM."""
        context = ""
        if prev_title:
            context += f"이전 챕터: '{prev_title}'\n"
        if is_continuation:
            context += "이 텍스트는 이전 번역의 연속입니다.\n"

        prompt = f"""당신은 전문 AI/ML 기술 문서 번역가입니다. 다음 영어 학술/기술 문서를 한국어 강의자료로 번역하세요.

{context}현재 챕터: '{chapter_title}'

{self._TERM_GLOSSARY}

번역 규칙:
1. 위 용어 사전의 표준 번역어를 반드시 사용할 것 (임의 의역 금지)
2. 용어 사전에 없는 기술 용어는 한국어 + 영문 병기: 예) 신경망(Neural Network)
3. __CODE_BLOCK_N__ 형식의 플레이스홀더는 절대 번역하지 말고 그대로 보존
4. 마크다운 헤딩(##, ###)은 한국어로 번역 (용어 사전 준수)
5. 수식($...$, $$...$$), URL, 변수명, 파일명은 번역하지 않음
6. 원문의 마크다운 구조(헤딩, 목록, 강조 등)를 그대로 유지

⛔ 절대 금지:
- 원문에 없는 내용을 새로 생성하거나 추가하지 말 것
- "Welcome to...", "This lecture covers..." 같은 소개 문장을 생성하지 말 것
- 원문이 짧더라도 확장하거나 보충하지 말 것 — 있는 내용만 충실히 번역할 것

원문:
{text}

한국어 번역 (원문 내용만, 추가 생성 없이):"""

        try:
            response = self.invoke_llm(prompt, phase="translate_chapter")
            translated = response.content.strip()

            # Strip common LLM preamble patterns
            for prefix in ["한국어 번역:", "번역:", "Translation:", "**번역**:"]:
                if translated.startswith(prefix):
                    translated = translated[len(prefix):].strip()

            return translated
        except Exception as e:
            logger.error(f"Translation chunk failed for '{chapter_title}': {e}")
            raise TranslationError(
                f"Translation failed for chapter '{chapter_title}': {e}"
            )

    # ── Image Assignment (private) ────────────────────────────────────────────

    def _build_synthetic_context_metadatas(
        self, section_pages: List[int]
    ) -> List[dict]:
        """
        Build synthetic RAG context metadatas for ImageSelector._calculate_page_importance().

        Keys used by _calculate_page_importance():
          - "source": absolute PDF path (must end with ".pdf")
          - "page_number": 1-indexed integer page number

        Pages are listed in importance order (earlier = higher rank = higher weight).
        """
        return [
            {
                "source": self.pdf_path,
                "page_number": page_num,
                "language": "en",
                "source_type": "pdf",
            }
            for page_num in section_pages
        ]

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a safe ASCII slug for use in section IDs."""
        import hashlib

        slug = re.sub(r"[^a-zA-Z0-9]+", "_", text)
        slug = slug.strip("_").lower()
        if slug:
            return slug[:30]
        # 비ASCII 제목(한국어 등): 결정론적 해시로 고유 ID 생성 (section 중복 방지)
        return "s" + hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:7]
