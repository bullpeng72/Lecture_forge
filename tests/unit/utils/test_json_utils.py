"""
Unit tests for utils/json_utils.py — strip_json_fence and parse_json_response.
"""

import json
import pytest

from lecture_forge.utils.json_utils import strip_json_fence, parse_json_response


# ---------------------------------------------------------------------------
# strip_json_fence
# ---------------------------------------------------------------------------

class TestStripJsonFence:
    def test_plain_json_unchanged(self):
        text = '{"key": "value"}'
        assert strip_json_fence(text) == text

    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = strip_json_fence(text)
        assert result == '{"key": "value"}'

    def test_strips_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = strip_json_fence(text)
        assert result == '{"key": "value"}'

    def test_json_fence_preferred_over_plain(self):
        text = '```json\n{"a": 1}\n```'
        result = strip_json_fence(text)
        assert result == '{"a": 1}'

    def test_leading_trailing_whitespace_stripped(self):
        text = '  \n{"key": "value"}  \n'
        result = strip_json_fence(text)
        assert result == '{"key": "value"}'

    def test_whitespace_inside_fence_stripped(self):
        text = '```json\n  {"key": "value"}  \n```'
        result = strip_json_fence(text)
        assert result == '{"key": "value"}'

    def test_empty_string(self):
        result = strip_json_fence("")
        assert result == ""

    def test_json_array_in_fence(self):
        text = '```json\n[1, 2, 3]\n```'
        result = strip_json_fence(text)
        assert result == "[1, 2, 3]"

    def test_no_fence_multiline(self):
        text = '{"a": 1,\n "b": 2}'
        result = strip_json_fence(text)
        assert result == text.strip()


# ---------------------------------------------------------------------------
# parse_json_response
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_plain_json_dict(self):
        text = '{"name": "Alice", "age": 30}'
        result = parse_json_response(text)
        assert result == {"name": "Alice", "age": 30}

    def test_json_in_fence(self):
        text = '```json\n{"status": "ok"}\n```'
        result = parse_json_response(text)
        assert result == {"status": "ok"}

    def test_json_in_plain_fence(self):
        text = '```\n[1, 2, 3]\n```'
        result = parse_json_response(text)
        assert result == [1, 2, 3]

    def test_nested_json(self):
        data = {"level1": {"level2": [1, 2, 3]}}
        text = json.dumps(data)
        result = parse_json_response(text)
        assert result == data

    def test_invalid_json_raises(self):
        text = "not valid json"
        with pytest.raises(json.JSONDecodeError):
            parse_json_response(text)

    def test_json_boolean_values(self):
        text = '{"active": true, "deleted": false}'
        result = parse_json_response(text)
        assert result["active"] is True
        assert result["deleted"] is False

    def test_json_null_value(self):
        text = '{"value": null}'
        result = parse_json_response(text)
        assert result["value"] is None

    def test_json_list(self):
        text = '["a", "b", "c"]'
        result = parse_json_response(text)
        assert result == ["a", "b", "c"]
