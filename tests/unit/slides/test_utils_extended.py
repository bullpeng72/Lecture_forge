"""
Extended unit tests for slides/utils.py covering previously uncovered lines.
Complements the existing test_utils.py (which covers convert_to_bullet_points).
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _truncate_bullet
# ---------------------------------------------------------------------------

class TestTruncateBullet:
    def test_short_text_unchanged(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet
        text = "Short text."
        assert _truncate_bullet(text) == text

    def test_text_at_limit_unchanged(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        text = "A" * _MAX_BULLET_CHARS
        assert _truncate_bullet(text) == text

    def test_complete_sentence_no_ellipsis(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        # Construct text > max_chars with a period near the start of the window
        prefix = "First sentence is complete. "
        suffix = "X" * (_MAX_BULLET_CHARS + 20)
        text = prefix + suffix
        result = _truncate_bullet(text)
        assert not result.endswith("…")
        assert result.endswith(".")

    def test_colon_boundary(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        # Place a colon at position 15 (> 10) so the colon branch triggers
        text = "A" * 15 + ": rest" + "B" * (_MAX_BULLET_CHARS + 10)
        result = _truncate_bullet(text)
        assert result.endswith("…")
        assert ":" in result

    def test_comma_boundary(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        # Comma past max_chars // 2 triggers comma branch
        half = _MAX_BULLET_CHARS // 2 + 5
        text = "A" * half + "," + "B" * (_MAX_BULLET_CHARS + 10)
        result = _truncate_bullet(text)
        assert result.endswith("…")

    def test_last_space_boundary(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        # Only a space as boundary, past half
        half = _MAX_BULLET_CHARS // 2 + 5
        text = "A" * half + " " + "B" * (_MAX_BULLET_CHARS + 10)
        result = _truncate_bullet(text)
        assert result.endswith("…")

    def test_no_boundary_truncates_hard(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet, _MAX_BULLET_CHARS
        # No period / colon / comma / space — hard truncate at max_chars
        text = "A" * (_MAX_BULLET_CHARS * 2)
        result = _truncate_bullet(text)
        assert result.endswith("…")
        assert len(result) == _MAX_BULLET_CHARS + 1  # window + "…"

    def test_custom_max_chars(self, test_env_vars):
        from lecture_forge.slides.utils import _truncate_bullet
        text = "Hello world this is a longer test string."
        result = _truncate_bullet(text, max_chars=10)
        assert len(result) <= 15  # truncated with possible "…"


# ---------------------------------------------------------------------------
# _parse_batch_response
# ---------------------------------------------------------------------------

class TestParseBatchResponse:
    def test_parses_single_paragraph(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n• Bullet one\n• Bullet two"
        result = _parse_batch_response(response, 1)
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_parses_multiple_paragraphs(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n• Alpha bullet point\n• Beta bullet point\n===PARA_1===\n• Gamma bullet point\n• Delta bullet point"
        result = _parse_batch_response(response, 2)
        assert len(result) == 2
        assert len(result[0]) == 2
        assert len(result[1]) == 2

    def test_missing_paragraph_returns_empty_list(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n• Only first."
        result = _parse_batch_response(response, 3)
        assert result[1] == []
        assert result[2] == []

    def test_out_of_range_paragraph_ignored(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_5===\n• Out of range."
        result = _parse_batch_response(response, 2)
        assert result == [[], []]

    def test_invalid_index_ignored(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_xyz===\n• Bad."
        result = _parse_batch_response(response, 1)
        assert result == [[]]

    def test_numbered_list_stripped(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n1. First item\n2) Second item"
        result = _parse_batch_response(response, 1)
        assert all(not b[0].isdigit() for b in result[0])

    def test_short_lines_filtered_out(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n• ok\n• This is a proper longer bullet point."
        result = _parse_batch_response(response, 1)
        # "ok" (2 chars) should be filtered (len <= 5)
        assert all(len(b) > 5 for b in result[0])

    def test_dash_bullet_stripped(self, test_env_vars):
        from lecture_forge.slides.utils import _parse_batch_response
        response = "===PARA_0===\n- A proper bullet line here"
        result = _parse_batch_response(response, 1)
        assert result[0][0][0] != "-"


# ---------------------------------------------------------------------------
# _process_batch
# ---------------------------------------------------------------------------

class TestProcessBatch:
    def test_calls_llm_and_parses(self, test_env_vars):
        from lecture_forge.slides.utils import _process_batch
        texts = ["Long narrative text that needs conversion to bullets for the slide deck."]
        mock_resp = MagicMock()
        mock_resp.content = "===PARA_0===\n• Key point one\n• Key point two"
        with patch("lecture_forge.slides.utils._invoke_llm", return_value=mock_resp):
            result = _process_batch(texts)
        assert len(result) == 1
        assert len(result[0]) >= 1

    def test_exception_falls_back(self, test_env_vars):
        from lecture_forge.slides.utils import _process_batch
        texts = ["Some text", "Other text"]
        with patch("lecture_forge.slides.utils._invoke_llm", side_effect=Exception("fail")):
            result = _process_batch(texts)
        assert result == [["Some text"], ["Other text"]]

    def test_multiple_texts_processed(self, test_env_vars):
        from lecture_forge.slides.utils import _process_batch
        texts = ["First text block.", "Second text block."]
        mock_resp = MagicMock()
        mock_resp.content = "===PARA_0===\n• Point A\n===PARA_1===\n• Point B"
        with patch("lecture_forge.slides.utils._invoke_llm", return_value=mock_resp):
            result = _process_batch(texts)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# batch_convert_to_bullet_points
# ---------------------------------------------------------------------------

class TestBatchConvertToBulletPoints:
    def test_empty_input_returns_empty(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        assert batch_convert_to_bullet_points([]) == []

    def test_short_texts_skipped_llm(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        texts = ["Short text.", "Also short."]
        # No LLM patch needed — short texts bypass the LLM
        result = batch_convert_to_bullet_points(texts)
        assert result == [["Short text."], ["Also short."]]

    def test_already_bulleted_skipped_llm(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        texts = ["• Bullet point here"]
        result = batch_convert_to_bullet_points(texts)
        assert result == [["• Bullet point here"]]

    def test_dash_bulleted_skipped_llm(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        texts = ["- Dash bullet point"]
        result = batch_convert_to_bullet_points(texts)
        assert result == [["- Dash bullet point"]]

    def test_long_texts_call_llm(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        long = "This is a very detailed narrative text that should be sent to the LLM. " * 3
        mock_resp = MagicMock()
        mock_resp.content = "===PARA_0===\n• Converted bullet point here"
        with patch("lecture_forge.slides.utils._invoke_llm", return_value=mock_resp):
            result = batch_convert_to_bullet_points([long])
        assert len(result) == 1
        assert isinstance(result[0], list)

    def test_mixed_short_and_long(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        short = "Short."
        long = "Long narrative text that needs LLM processing to convert to bullets. " * 3
        mock_resp = MagicMock()
        mock_resp.content = "===PARA_0===\n• Bullet for long text"
        with patch("lecture_forge.slides.utils._invoke_llm", return_value=mock_resp):
            result = batch_convert_to_bullet_points([short, long])
        assert len(result) == 2
        assert result[0] == ["Short."]

    def test_batches_over_batch_size(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points, _BATCH_SIZE
        # Create more texts than _BATCH_SIZE to trigger multiple batches
        long = "Long narrative text that needs LLM processing to convert. " * 3
        texts = [long] * (_BATCH_SIZE + 2)
        para_blocks = "\n".join(
            f"===PARA_{i}===\n• Bullet {i}" for i in range(_BATCH_SIZE)
        )
        extra_blocks = "\n".join(
            f"===PARA_{i}===\n• Bullet extra {i}" for i in range(2)
        )
        responses = [para_blocks, extra_blocks]
        call_count = [0]

        def fake_invoke(messages):
            resp = MagicMock()
            resp.content = responses[min(call_count[0], 1)]
            call_count[0] += 1
            return resp

        with patch("lecture_forge.slides.utils._invoke_llm", side_effect=fake_invoke):
            result = batch_convert_to_bullet_points(texts)
        assert len(result) == _BATCH_SIZE + 2
        assert call_count[0] == 2  # Two batches

    def test_star_bulleted_skipped_llm(self, test_env_vars):
        from lecture_forge.slides.utils import batch_convert_to_bullet_points
        texts = ["* Star bullet point"]
        result = batch_convert_to_bullet_points(texts)
        assert result == [["* Star bullet point"]]
