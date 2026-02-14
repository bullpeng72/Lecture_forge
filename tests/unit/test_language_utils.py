"""
Unit tests for language utilities.
"""

import pytest

from lecture_forge.utils import (
    detect_language,
    get_language_name,
    is_english,
    is_korean,
)


class TestLanguageDetection:
    """Test language detection functions."""

    def test_detect_korean(self):
        """Test Korean language detection."""
        text = "파이썬은 배우기 쉬운 프로그래밍 언어입니다."
        assert detect_language(text) == "ko"

    def test_detect_english(self):
        """Test English language detection."""
        text = "Python is an easy-to-learn programming language."
        assert detect_language(text) == "en"

    def test_detect_empty_text(self):
        """Test empty text returns default."""
        assert detect_language("") == "unknown"
        assert detect_language("   ") == "unknown"

    def test_is_korean(self):
        """Test is_korean helper."""
        assert is_korean("안녕하세요") is True
        assert is_korean("Hello") is False

    def test_is_english(self):
        """Test is_english helper."""
        # Use longer text for more reliable detection
        text = "Python is a high-level programming language with dynamic semantics."
        assert is_english(text) is True
        assert is_english("안녕하세요 반갑습니다") is False

    def test_get_language_name(self):
        """Test language name retrieval."""
        assert get_language_name("ko") == "Korean"
        assert get_language_name("en") == "English"
        assert get_language_name("ja") == "Japanese"
        assert get_language_name("unknown") == "Unknown"

    def test_detect_mixed_content(self):
        """Test detection with mixed content."""
        # Primarily Korean with some English
        text = "Python은 강력한 프로그래밍 언어입니다. 배우기 쉽고 사용하기 편리합니다."
        lang = detect_language(text)
        # langdetect is probabilistic, so we accept multiple results
        assert lang in ["ko", "en", "tl", "id"]  # Could vary

    def test_detect_technical_content(self):
        """Test detection with technical/code content."""
        # Longer Korean text for better detection
        text = "파이썬 프로그래밍 언어는 인터프리터 방식으로 동작합니다."
        lang = detect_language(text)
        # Should detect Korean
        assert lang == "ko"


class TestTranslation:
    """Test translation functions (integration tests - require API key)."""

    @pytest.mark.skip(reason="Requires OpenAI API key (integration test)")
    def test_translate_to_english(self):
        """Test Korean to English translation (integration test)."""
        from lecture_forge.utils import translate_to_english

        korean_text = "파이썬 데코레이터"
        english_text = translate_to_english(korean_text)

        # Should contain "decorator" or "python"
        assert english_text.lower() != korean_text
        assert len(english_text) > 0

    @pytest.mark.skip(reason="Requires OpenAI API key (integration test)")
    def test_translate_to_korean(self):
        """Test English to Korean translation (integration test)."""
        from lecture_forge.utils import translate_to_korean

        english_text = "Python decorator"
        korean_text = translate_to_korean(english_text)

        # Should be different from input
        assert korean_text != english_text
        assert len(korean_text) > 0
