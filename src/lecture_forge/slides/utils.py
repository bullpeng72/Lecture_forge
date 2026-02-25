"""
Utility functions for slide generation.
"""

import re
from typing import List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from lecture_forge.config import Config
from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry

_BATCH_SIZE = 15
_MAX_BULLET_CHARS = 80  # hard limit for a single bullet point (한글 기준)


def _truncate_bullet(text: str, max_chars: int = _MAX_BULLET_CHARS) -> str:
    """Truncate a bullet point to max_chars at a natural language boundary.

    Priority: complete sentence > colon > comma > Korean clause marker > last space.
    Returns original text if already within limit.
    When a complete sentence fits, returns it WITHOUT ellipsis ("…").
    """
    if len(text) <= max_chars:
        return text

    window = text[:max_chars]

    # 0) Prefer complete sentence boundary: find the last ". " within the window
    #    and return WITHOUT ellipsis — a complete sentence is cleaner than a fragment
    last_period = window.rfind(". ")
    if last_period >= max(10, max_chars // 3):
        return text[:last_period + 1].rstrip()  # Complete sentence, no "…"

    # 1) Natural break at colon (topic: description pattern)
    for sep in (":", "："):
        pos = window.find(sep)
        if 10 <= pos < max_chars:
            return text[: pos + 1].rstrip() + "…"

    # 2) Comma / Korean clause boundary
    for sep in (",", "，", " —", " -"):
        pos = window.rfind(sep)
        if pos > max_chars // 2:
            return text[:pos].rstrip() + "…"

    # 3) Last space
    last_space = window.rfind(" ")
    if last_space > max_chars // 2:
        return text[:last_space] + "…"

    return window + "…"


@make_api_retry("Slides")
def _invoke_llm(messages: list) -> AIMessage:
    """Invoke the slides LLM with retry logic."""
    llm = ChatOpenAI(
        model=Config.DEFAULT_MODEL,
        temperature=0.3,
        api_key=Config.OPENAI_API_KEY,
        max_tokens=800,
    )
    return llm.invoke(messages)


def _parse_batch_response(response: str, expected_count: int) -> List[List[str]]:
    """Parse a batch LLM response (===PARA_N=== delimited) into per-text bullet lists.

    Args:
        response: Raw LLM response string
        expected_count: Number of texts that were submitted in the batch

    Returns:
        List of bullet-point lists, one per input text (fallback to empty list if missing)
    """
    results: List[List[str]] = [[] for _ in range(expected_count)]

    # Split on ===PARA_N=== markers; re.split with a capturing group gives
    # [pre, idx0, content0, idx1, content1, ...]
    parts = re.split(r"===PARA_(\d+)===", response)

    # parts[0] is text before the first marker (ignored)
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        try:
            para_idx = int(parts[i])
        except ValueError:
            continue
        content = parts[i + 1].strip()
        if not (0 <= para_idx < expected_count):
            continue

        bullets = []
        for line in content.split("\n"):
            line = line.strip().lstrip("•-*").strip()
            line = re.sub(r"^\d+[\.)]\s*", "", line)
            if line and len(line) > 5:
                bullets.append(_truncate_bullet(line))

        if bullets:
            results[para_idx] = bullets

    return results


def _process_batch(texts: List[str]) -> List[List[str]]:
    """Convert a batch of texts to bullet-point lists in a single LLM call.

    Falls back to returning each text as a one-element list on error.
    """
    try:
        sections = "\n\n".join(f"===PARA_{i}===\n{text}" for i, text in enumerate(texts))

        prompt = f"""다음 {len(texts)}개의 서술식 텍스트를 각각 프레젠테이션 슬라이드에 적합한 개조식 표현으로 변환해주세요.

요구사항:
- 핵심 내용만 간결하게 추출
- 각 포인트는 한 줄로 요약
- 불필요한 접속사나 서술어 제거
- 명사형 종결 또는 간결한 동사형 사용
- 3-5개의 bullet points로 정리
- 각 bullet point는 한글 35자 이내로 완결된 의미를 담을 것 (말줄임표 절대 금지)
- 긴 개념은 2개의 bullet로 나누어 각각 완결되게 표현

각 텍스트의 변환 결과를 ===PARA_N=== 구분자로 구분하여 출력하세요.

{sections}

변환 결과 (===PARA_0===, ===PARA_1=== 등으로 구분):"""

        response = _invoke_llm([HumanMessage(content=prompt)])
        return _parse_batch_response(response.content.strip(), len(texts))

    except Exception as e:
        logger.warning(f"Batch bullet-point conversion failed: {e}")
        return [[text] for text in texts]


def batch_convert_to_bullet_points(texts: List[str]) -> List[List[str]]:
    """Convert multiple narrative texts to bullet-point lists using batched LLM calls.

    Texts shorter than 100 characters or already in bullet format are returned
    immediately without an LLM call.  The remaining texts are grouped into
    batches of up to 15 and processed in a single LLM call each.

    Args:
        texts: List of narrative texts to convert

    Returns:
        List of bullet-point lists, one per input text
    """
    if not texts:
        return []

    # Partition into instant-return vs needs-LLM
    # Each entry: (needs_llm: bool, result or None)
    partitioned: List = []
    llm_indices: List[int] = []  # original indices of texts needing LLM
    llm_texts: List[str] = []

    for idx, text in enumerate(texts):
        if len(text) < 100 or text.strip().startswith(("•", "-", "*")):
            partitioned.append((False, [text]))
        else:
            partitioned.append((True, None))
            llm_indices.append(idx)
            llm_texts.append(text)

    if not llm_texts:
        return [r for _, r in partitioned]

    # Process in batches
    llm_results: List[List[str]] = []
    for i in range(0, len(llm_texts), _BATCH_SIZE):
        batch = llm_texts[i : i + _BATCH_SIZE]
        llm_results.extend(_process_batch(batch))

    # Merge results back
    llm_iter = iter(llm_results)
    final: List[List[str]] = []
    for needs_llm, cached in partitioned:
        if needs_llm:
            final.append(next(llm_iter))
        else:
            final.append(cached)

    return final


def convert_to_bullet_points(text: str) -> List[str]:
    """Convert narrative text to concise bullet points for presentation.

    Args:
        text: Narrative text to convert

    Returns:
        List of bullet point strings
    """
    try:
        # Skip if text is already short or already in bullet format
        if len(text) < 100 or text.strip().startswith(("•", "-", "*")):
            return [text]

        prompt = f"""다음 서술식 텍스트를 프레젠테이션 슬라이드에 적합한 개조식 표현으로 변환해주세요.

요구사항:
- 핵심 내용만 간결하게 추출
- 각 포인트는 한 줄로 요약
- 불필요한 접속사나 서술어 제거
- 명사형 종결 또는 간결한 동사형 사용
- 3-5개의 bullet points로 정리
- 각 bullet point는 한글 35자 이내로 완결된 의미를 담을 것 (말줄임표 절대 금지)
- 긴 개념은 2개의 bullet로 나누어 각각 완결되게 표현

원문:
{text}

개조식 bullet points (각 줄을 구분하여 출력):"""

        response = _invoke_llm([HumanMessage(content=prompt)])
        bullet_text = response.content.strip()

        # Parse bullet points
        bullets = []
        for line in bullet_text.split("\n"):
            line = line.strip()
            # Remove bullet markers if present
            line = line.lstrip("•-*").strip()
            # Remove numbering if present
            line = re.sub(r"^\d+[\.)]\s*", "", line)
            if line and len(line) > 5:  # Filter out very short lines
                bullets.append(_truncate_bullet(line))

        return bullets if bullets else [text]

    except Exception as e:
        logger.warning(f"Failed to convert to bullet points: {e}")
        # Fallback: split by sentences
        sentences = re.split(r"[.!?]\s+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10][:5]
