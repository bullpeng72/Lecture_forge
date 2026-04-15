"""
Slide notes generator for adding presenter notes to Reveal.js slides.
"""

import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage

from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry

_BATCH_SIZE = 10
_MAX_CONTENT_CHARS = 400  # truncate slide text sent to LLM to save tokens


@make_api_retry("SlideNotes")
def _invoke_notes_llm(messages: list):
    """Invoke LLM for notes generation with retry."""
    from lecture_forge.config import create_llm

    llm = create_llm(temperature=0.5, max_tokens=1000, thinking=False)
    return llm.invoke(messages)


def _parse_notes_response(response: str, expected_count: int) -> List[str]:
    """Parse ===SLIDE_N=== delimited response into per-slide note strings."""
    results: List[Optional[str]] = [None] * expected_count

    parts = re.split(r"===SLIDE_(\d+)===", response)

    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        try:
            idx = int(parts[i])
        except ValueError:
            continue
        content = parts[i + 1].strip()
        if 0 <= idx < expected_count and content:
            results[idx] = content

    # Replace None (missing) with empty string
    return [r or "" for r in results]


def _process_notes_batch(slide_infos: List[Dict]) -> List[str]:
    """Generate presenter notes for a batch of slides in a single LLM call."""
    try:
        sections_text = "\n\n".join(
            f"===SLIDE_{i}===\n제목: {info['title']}\n내용: {info['text'][:_MAX_CONTENT_CHARS]}"
            for i, info in enumerate(slide_infos)
        )

        prompt = f"""다음 {len(slide_infos)}개 슬라이드에 대한 발표자 노트를 생성해주세요.
발표자가 청중 앞에서 참고할 수 있는 간결하고 유용한 설명을 작성하세요.

요구사항:
- 2~4문장으로 슬라이드 내용을 자연스럽게 설명
- 핵심 포인트 강조, 실제 예시, 추가 컨텍스트 제공
- 필요시 청중에게 던질 수 있는 질문 1개 포함 가능
- 강사가 말하는 듯한 구어체 사용
- 한국어로 작성

각 슬라이드 노트를 ===SLIDE_N=== 구분자로 구분하여 출력하세요.

{sections_text}

발표자 노트 (===SLIDE_0===, ===SLIDE_1=== 등으로 구분):"""

        response = _invoke_notes_llm([HumanMessage(content=prompt)])
        return _parse_notes_response(response.content.strip(), len(slide_infos))

    except Exception as e:
        logger.warning(f"Notes batch generation failed: {e}")
        return [""] * len(slide_infos)


class SlideNotesGenerator:
    """Injects LLM-generated presenter notes into Reveal.js slides HTML."""

    def generate(self, slides_html: str) -> str:
        """Post-process slides HTML to add presenter notes to every slide section.

        Args:
            slides_html: Raw Reveal.js HTML string (output of RevealJsTemplate.generate)

        Returns:
            Modified HTML with <aside class="notes"> injected into each <section>
        """
        soup = BeautifulSoup(slides_html, "html.parser")

        slides_div = soup.find("div", class_="slides")
        if not slides_div:
            logger.warning("SlideNotesGenerator: no .slides div found — skipping")
            return slides_html

        sections = slides_div.find_all("section", recursive=False)
        if not sections:
            return slides_html

        # Build per-slide info (title + visible text)
        slide_infos: List[Dict] = []
        for sec in sections:
            title = self._extract_title(sec)
            # Get text content, excluding existing aside.notes
            for aside in sec.find_all("aside"):
                aside.extract()
            text = sec.get_text(separator=" ", strip=True)
            slide_infos.append({"title": title, "text": text})

        # Generate notes in batches
        all_notes: List[str] = []
        for i in range(0, len(slide_infos), _BATCH_SIZE):
            batch = slide_infos[i : i + _BATCH_SIZE]
            all_notes.extend(_process_notes_batch(batch))

        # Inject <aside class="notes"> into each section
        for sec, notes_text in zip(sections, all_notes):
            if notes_text:
                aside = soup.new_tag("aside", attrs={"class": "notes"})
                aside.string = notes_text
                sec.append(aside)

        # BeautifulSoup's str() encodes text-node '>' as '&gt;', which breaks
        # Mermaid syntax (e.g. 'A --> B' becomes 'A --&gt; B').
        # Fix: stash each mermaid div's text behind a plain-ASCII placeholder
        # BEFORE serialisation, then restore after.  O(n) — no regex backtracking.
        mermaid_store: dict[str, str] = {}
        for idx, mdiv in enumerate(soup.find_all("div", class_="mermaid")):
            placeholder = f"MERMAIDPLACEHOLDER{idx}END"
            mermaid_store[placeholder] = mdiv.get_text()
            mdiv.clear()
            mdiv.string = placeholder   # ASCII-only → BS4 won't alter it

        result = str(soup)

        for placeholder, raw_text in mermaid_store.items():
            result = result.replace(placeholder, raw_text)

        return result

    @staticmethod
    def _extract_title(section) -> str:
        """Extract the most prominent heading from a slide section."""
        for tag in ("h2", "h3", "h1"):
            h = section.find(tag)
            if h:
                return h.get_text(strip=True)
        return ""
