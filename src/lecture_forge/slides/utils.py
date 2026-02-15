"""
Utility functions for slide generation.
"""

import re
from typing import List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from lecture_forge.config import Config
from lecture_forge.utils import logger


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

        llm = ChatOpenAI(model=Config.DEFAULT_MODEL, temperature=0.3, api_key=Config.OPENAI_API_KEY)

        prompt = f"""다음 서술식 텍스트를 프레젠테이션 슬라이드에 적합한 개조식 표현으로 변환해주세요.

요구사항:
- 핵심 내용만 간결하게 추출
- 각 포인트는 한 줄로 요약
- 불필요한 접속사나 서술어 제거
- 명사형 종결 또는 간결한 동사형 사용
- 3-5개의 bullet points로 정리
- 각 bullet point는 한글 50자 이내

원문:
{text}

개조식 bullet points (각 줄을 구분하여 출력):"""

        response = llm.invoke([HumanMessage(content=prompt)])
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
                bullets.append(line)

        return bullets if bullets else [text]

    except Exception as e:
        logger.warning(f"Failed to convert to bullet points: {e}")
        # Fallback: split by sentences
        sentences = re.split(r"[.!?]\s+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10][:5]
