"""
Language detection and translation utilities for multilingual support.
"""

from typing import Optional

from langdetect import LangDetectException, detect

from lecture_forge.config import Config, create_llm
from lecture_forge.utils import logger


def detect_language(text: str, default: str = "unknown") -> str:
    """
    Detect the language of a text.

    Args:
        text: Text to analyze
        default: Default language code if detection fails

    Returns:
        Language code (e.g., "en", "ko", "ja", "zh-cn")
    """
    if not text or not text.strip():
        return default

    # Check Korean character ratio before calling langdetect.
    # langdetect often misidentifies mixed Korean-English text (e.g., "판다스(Pandas)가 뭔가요?").
    # If >= 30% of alphabetic characters are Korean (가-힣 or ㄱ-ㅣ), treat as Korean.
    korean_chars = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3' or '\u3130' <= c <= '\u318F')
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha > 0 and korean_chars / total_alpha >= 0.25:
        return "ko"

    try:
        # langdetect returns ISO 639-1 codes (2-letter)
        lang = detect(text)
        return lang
    except (LangDetectException, Exception) as e:
        logger.debug(f"Language detection failed: {e}")
        return default


def is_korean(text: str) -> bool:
    """
    Check if text is primarily Korean.

    Args:
        text: Text to check

    Returns:
        True if Korean, False otherwise
    """
    lang = detect_language(text, default="unknown")
    return lang == "ko"


def is_english(text: str) -> bool:
    """
    Check if text is primarily English.

    Args:
        text: Text to check

    Returns:
        True if English, False otherwise
    """
    lang = detect_language(text, default="unknown")
    return lang == "en"


def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Translate text to target language using LLM.

    Args:
        text: Text to translate
        target_language: Target language code or name ("en", "ko", "English", "Korean")
        source_language: Source language (auto-detected if None)
        model: LLM model to use for translation

    Returns:
        Translated text
    """
    if not text or not text.strip():
        return text

    # Auto-detect source language if not provided
    if source_language is None:
        source_language = detect_language(text, default="unknown")

    # Normalize language names
    language_map = {
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh-cn": "Chinese (Simplified)",
        "zh-tw": "Chinese (Traditional)",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
    }

    source_lang_name = language_map.get(source_language, source_language)
    target_lang_name = language_map.get(target_language, target_language)

    # Check if translation is needed
    if source_language == target_language:
        logger.debug(f"Source and target language are the same ({source_language}), skipping translation")
        return text

    # Initialize LLM for translation
    try:
        llm = create_llm(model=model, temperature=0.0, max_tokens=2000)

        # Create translation prompt
        prompt = f"""Translate the following text from {source_lang_name} to {target_lang_name}.

IMPORTANT INSTRUCTIONS:
1. Preserve technical terms and proper nouns
2. Maintain the original meaning and tone
3. Keep code snippets, URLs, and special formatting unchanged
4. Output ONLY the translated text, no explanations

Original text:
{text}

Translation:"""

        # Get translation
        response = llm.invoke(prompt)
        translated = response.content.strip()

        logger.debug(f"Translated text from {source_lang_name} to {target_lang_name}")
        return translated

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        # Fallback to original text
        return text


def translate_to_english(text: str) -> str:
    """
    Translate text to English.

    Args:
        text: Text to translate

    Returns:
        English translation
    """
    return translate_text(text, target_language="en")


def translate_to_korean(text: str) -> str:
    """
    Translate text to Korean.

    Args:
        text: Text to translate

    Returns:
        Korean translation
    """
    return translate_text(text, target_language="ko")


def get_language_name(language_code: str) -> str:
    """
    Get full language name from code.

    Args:
        language_code: ISO 639-1 language code

    Returns:
        Full language name
    """
    language_names = {
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh-cn": "Chinese (Simplified)",
        "zh-tw": "Chinese (Traditional)",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "unknown": "Unknown",
    }
    return language_names.get(language_code, language_code)
