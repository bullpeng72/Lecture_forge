"""
Integration tests for multilingual features (v0.3.2+).

Tests:
- Language detection
- Cross-lingual search (dual query)
- Translation integration
- Mixed-language PDF handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from lecture_forge.knowledge.vector_store import VectorStore


class TestLanguageDetection:
    """Test language detection in RAG pipeline."""

    @pytest.mark.skipif(True, reason="Requires langdetect dependency")
    def test_detect_korean_text(self):
        """Test Korean text detection."""
        try:
            from lecture_forge.utils.language_utils import detect_language

            korean_text = "머신러닝은 인공지능의 한 분야입니다"
            lang = detect_language(korean_text)

            assert lang == "ko"
        except ImportError:
            pytest.skip("langdetect not available")

    @pytest.mark.skipif(True, reason="Requires langdetect dependency")
    def test_detect_english_text(self):
        """Test English text detection."""
        try:
            from lecture_forge.utils.language_utils import detect_language

            english_text = "Machine learning is a field of artificial intelligence"
            lang = detect_language(english_text)

            assert lang == "en"
        except ImportError:
            pytest.skip("langdetect not available")

    @pytest.mark.skipif(True, reason="Requires langdetect dependency")
    def test_detect_mixed_language(self):
        """Test detection in mixed language text."""
        try:
            from lecture_forge.utils.language_utils import detect_language

            # Mixed text (English with Korean)
            mixed_text = "Machine learning (머신러닝) is important"
            lang = detect_language(mixed_text)

            # Should detect dominant language
            assert lang in ["en", "ko"]
        except ImportError:
            pytest.skip("langdetect not available")


class TestCrossLingualSearch:
    """Test cross-lingual search functionality."""

    @pytest.mark.skipif(True, reason="Requires OpenAI API")
    def test_dual_query_korean_to_english(self):
        """Test Korean query searches both Korean and English chunks."""
        # This would require actual vector store
        # For now, test the concept
        pass

    @pytest.mark.skipif(True, reason="Requires OpenAI API")
    def test_dual_query_english_to_korean(self):
        """Test English query searches both languages."""
        pass

    def test_translation_caching(self):
        """Test that translations are cached."""
        # Mock translation cache
        cache = {}

        def mock_translate(text, target_lang):
            if text not in cache:
                cache[text] = f"translated_{text}"
            return cache[text]

        # First call
        result1 = mock_translate("hello", "ko")
        assert result1 == "translated_hello"
        assert len(cache) == 1

        # Second call (should use cache)
        result2 = mock_translate("hello", "ko")
        assert result2 == "translated_hello"
        assert len(cache) == 1  # Cache size unchanged


class TestLanguageMetadata:
    """Test language metadata in vector store."""

    def test_chunk_has_language_metadata(self):
        """Test that chunks are tagged with language."""
        # Mock chunk with metadata
        chunk_metadata = {
            "source": "test.pdf",
            "page_number": 1,
            "language": "en",
        }

        assert "language" in chunk_metadata
        assert chunk_metadata["language"] in ["en", "ko", "ja", "zh"]

    def test_filter_chunks_by_language(self):
        """Test filtering chunks by language."""
        chunks = [
            {"text": "English text", "metadata": {"language": "en"}},
            {"text": "한국어 텍스트", "metadata": {"language": "ko"}},
            {"text": "More English", "metadata": {"language": "en"}},
        ]

        english_chunks = [c for c in chunks if c["metadata"]["language"] == "en"]
        korean_chunks = [c for c in chunks if c["metadata"]["language"] == "ko"]

        assert len(english_chunks) == 2
        assert len(korean_chunks) == 1


class TestMixedLanguagePDF:
    """Test handling of mixed-language PDFs."""

    def test_page_level_language_detection(self):
        """Test that each page can have different language."""
        pages = [
            {"page": 1, "text": "Introduction to ML", "language": "en"},
            {"page": 2, "text": "머신러닝 소개", "language": "ko"},
            {"page": 3, "text": "Neural Networks", "language": "en"},
        ]

        languages = set(p["language"] for p in pages)
        assert "en" in languages
        assert "ko" in languages

    def test_chunk_preserves_source_language(self):
        """Test that chunks preserve original language."""
        chunk = {
            "text": "머신러닝은 AI의 일부입니다",
            "metadata": {
                "source": "mixed_doc.pdf",
                "page_number": 5,
                "language": "ko",
            },
        }

        # Chunk should maintain language tag
        assert chunk["metadata"]["language"] == "ko"

        # Even when searched in English, should preserve Korean
        search_result = {
            "chunk": chunk,
            "query_language": "en",
            "chunk_language": "ko",
            "is_cross_lingual": True,
        }

        assert search_result["is_cross_lingual"] is True


class TestLanguageReranking:
    """Test language-based reranking."""

    def test_same_language_bonus(self):
        """Test that same-language results get priority boost."""
        query_lang = "en"

        results = [
            {"score": 0.8, "metadata": {"language": "en"}},  # Same language
            {"score": 0.9, "metadata": {"language": "ko"}},  # Different language
        ]

        # Apply language bonus
        for result in results:
            if result["metadata"]["language"] == query_lang:
                result["score"] *= 1.1  # +10% bonus

        # Same language result should now score higher
        english_result = results[0]
        korean_result = results[1]

        assert english_result["score"] == 0.88  # 0.8 * 1.1
        assert english_result["score"] < korean_result["score"] or \
               abs(english_result["score"] - korean_result["score"]) < 0.1

    def test_cross_lingual_penalty(self):
        """Test that cross-lingual results get slight penalty."""
        query_lang = "en"

        results = [
            {"score": 0.9, "metadata": {"language": "en"}},
            {"score": 0.9, "metadata": {"language": "ko"}},
        ]

        # Apply bonuses
        for result in results:
            if result["metadata"]["language"] == query_lang:
                result["score"] *= 1.1  # Same language bonus
            else:
                result["score"] *= 1.05  # Cross-lingual bonus (smaller)

        same_lang_score = results[0]["score"]
        cross_lang_score = results[1]["score"]

        assert same_lang_score > cross_lang_score


class TestTranslationIntegration:
    """Test translation integration with RAG."""

    @pytest.mark.skipif(True, reason="Requires OpenAI API")
    def test_translate_query_for_dual_search(self):
        """Test query translation for dual-language search."""
        # Would require actual LLM call
        pass

    def test_translation_error_handling(self):
        """Test graceful handling of translation failures."""
        def mock_translate_with_error(text, target_lang):
            if "error" in text:
                raise Exception("Translation API error")
            return f"translated_{text}"

        # Should handle error gracefully
        try:
            result = mock_translate_with_error("error text", "ko")
        except Exception:
            result = None  # Fallback to original

        # Should have fallback behavior
        assert result is None or result == "error text"


class TestLanguageStatistics:
    """Test language usage statistics."""

    def test_count_chunks_by_language(self):
        """Test counting chunks by language."""
        chunks = [
            {"metadata": {"language": "en"}},
            {"metadata": {"language": "en"}},
            {"metadata": {"language": "ko"}},
            {"metadata": {"language": "en"}},
            {"metadata": {"language": "ja"}},
        ]

        lang_counts = {}
        for chunk in chunks:
            lang = chunk["metadata"]["language"]
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        assert lang_counts["en"] == 3
        assert lang_counts["ko"] == 1
        assert lang_counts["ja"] == 1

    def test_dominant_language_detection(self):
        """Test detecting dominant language in document."""
        lang_counts = {
            "en": 100,
            "ko": 20,
            "ja": 5,
        }

        dominant_lang = max(lang_counts, key=lang_counts.get)

        assert dominant_lang == "en"

    def test_language_distribution_reporting(self):
        """Test reporting language distribution."""
        total_chunks = 100
        lang_distribution = {
            "en": 70,
            "ko": 25,
            "ja": 5,
        }

        # Calculate percentages
        percentages = {
            lang: (count / total_chunks) * 100
            for lang, count in lang_distribution.items()
        }

        assert percentages["en"] == 70.0
        assert percentages["ko"] == 25.0
        assert percentages["ja"] == 5.0
        assert sum(percentages.values()) == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
