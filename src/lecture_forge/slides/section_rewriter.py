"""
Section Rewriter - Rewrites lecture content section-by-section for slide presentation.

Plan D: Per-section LLM rewrite that replaces the generic paragraph→bullet pipeline
with a context-aware restructuring pass.  Code, image, and diagram blocks pass
through unchanged; only text blocks (subsection headings, paragraphs, lists) are
rewritten so each bullet is ≤35 Korean characters and semantically complete.
"""

import re
from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage

from lecture_forge.config import create_llm
from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry

_TARGET_BULLET_CHARS = 35  # Aim for this length; hard truncation limits are 80


@make_api_retry("SectionRewriter")
def _invoke_llm(messages: list) -> AIMessage:
    """Invoke LLM with retry logic."""
    llm = create_llm(temperature=0.3, max_tokens=800, thinking=False)
    return llm.invoke(messages)


def _blocks_to_text(blocks: List[Dict]) -> str:
    """Convert text blocks to readable text for LLM input.

    Skips code, image, and diagram blocks (they pass through unchanged).
    """
    parts = []
    for block in blocks:
        btype = block["type"]
        if btype == "subsection":
            parts.append(f"\n### {block['content']}")
        elif btype == "subsubsection":
            parts.append(f"\n#### {block['content']}")
        elif btype == "paragraph":
            parts.append(block["content"])
        elif btype == "list":
            for item in block["items"]:
                plain = re.sub(r"<[^>]+>", "", item)  # strip HTML formatting
                parts.append(f"- {plain}")
    return "\n".join(parts)


def _parse_rewriter_response(response: str) -> List[Dict]:
    """Parse the LLM markdown response back into content block dicts."""
    blocks: List[Dict] = []
    current_items: List[str] = []

    def flush_items() -> None:
        if current_items:
            blocks.append({"type": "list", "items": list(current_items), "ordered": False})
            current_items.clear()

    for line in response.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        if line_stripped.startswith("### "):
            flush_items()
            content = line_stripped[4:].strip()
            if content:
                blocks.append({"type": "subsection", "content": content})
        elif line_stripped.startswith("#### "):
            flush_items()
            content = line_stripped[5:].strip()
            if content:
                blocks.append({"type": "subsubsection", "content": content})
        elif line_stripped.startswith(("- ", "• ", "* ")):
            item = line_stripped[2:].strip()
            if item:
                current_items.append(item)
        elif re.match(r"^\d+\.\s+", line_stripped):
            item = re.sub(r"^\d+\.\s+", "", line_stripped).strip()
            if item:
                current_items.append(item)

    flush_items()
    return blocks


def rewrite_section_for_slides(
    section_title: str,
    blocks: List[Dict],
    section_num: int = 0,
) -> List[Dict]:
    """Rewrite one section's content blocks optimized for slide presentation.

    Code, image, and diagram blocks pass through unchanged and are appended
    after the rewritten text blocks.  Text blocks (subsection headings,
    paragraphs, lists) are fed to an LLM that produces concise, complete bullets
    with no trailing ellipsis.

    Args:
        section_title: Title of the section (used in the LLM prompt).
        blocks: Content block list from the parser.
        section_num: Section index, used for log messages only.

    Returns:
        Rewritten block list, or the original on any failure.
    """
    passthrough_blocks = [b for b in blocks if b["type"] in ("code", "image", "diagram")]
    text_blocks = [b for b in blocks if b["type"] not in ("code", "image", "diagram")]

    if not text_blocks:
        return blocks

    text_input = _blocks_to_text(text_blocks)
    if len(text_input.strip()) < 50:
        # Too little content to rewrite; return as-is
        return blocks

    prompt = f"""다음은 강의 슬라이드 섹션 "{section_title}"의 내용입니다.
이 내용을 프레젠테이션 슬라이드에 최적화된 형태로 재구성해 주세요.

원본 내용:
{text_input}

재구성 규칙:
1. 핵심 내용만 추출하여 간결한 bullet point로 정리
2. 각 bullet point는 한글 기준 {_TARGET_BULLET_CHARS}자 이내 (말줄임표 절대 금지)
3. 긴 개념은 여러 줄로 나누어 각각 완결된 의미를 갖도록 표현
4. 소주제 제목(###)은 원본 구조 최대한 유지
5. bullet point는 - 로 시작
6. 명사형 종결 또는 간결한 동사형 사용 (불필요한 접속사 최소화)
7. 슬라이드당 4-5개 bullet 기준으로 소주제별 그룹화
8. 코드 예제·이미지·다이어그램은 이 텍스트에 없으며 별도 처리됨

출력 형식 (이 형식만 사용):
### 소주제 제목

- 첫 번째 핵심 포인트
- 두 번째 포인트
- 세 번째 포인트

### 다음 소주제

- 포인트 1
- 포인트 2

위 형식으로만 출력하세요. 추가 설명이나 주석은 포함하지 마세요."""

    try:
        logger.debug(f"   📝 Rewriting '{section_title}' ({len(text_input)} chars)")
        response = _invoke_llm([HumanMessage(content=prompt)])
        rewritten_text = response.content.strip()

        rewritten_blocks = _parse_rewriter_response(rewritten_text)

        if not rewritten_blocks:
            logger.warning(f"   ⚠️ Rewriter returned empty result for '{section_title}', using original")
            return blocks

        # Append pass-through blocks (code/image/diagram) after rewritten text blocks
        final_blocks = rewritten_blocks + passthrough_blocks

        logger.info(
            f"   ✅ Rewrote section {section_num + 1} '{section_title}': "
            f"{len(blocks)} → {len(final_blocks)} blocks"
        )
        return final_blocks

    except Exception as e:
        logger.warning(f"   ⚠️ Section rewriter failed for '{section_title}': {e}")
        return blocks  # Fall back to original on any error


def rewrite_sections_for_slides(sections: List[Dict]) -> List[Dict]:
    """Rewrite all sections for slide presentation.

    Args:
        sections: List of section dicts from the parser
                  (each has 'title' and 'blocks').

    Returns:
        List of rewritten section dicts.
    """
    rewritten = []
    n = len(sections)
    for i, section in enumerate(sections):
        title = section["title"]
        blocks = section["blocks"]
        logger.info(f"  🔄 Rewriting section {i + 1}/{n}: '{title}'")
        rewritten_blocks = rewrite_section_for_slides(title, blocks, section_num=i)
        rewritten.append({"title": title, "blocks": rewritten_blocks})
    return rewritten
