"""
Unit tests for utils/__init__.py utility functions.
"""

import pytest

from lecture_forge.utils import (
    count_words,
    format_duration,
    format_file_size,
    merge_dicts,
    sanitize_filename,
    timestamp,
)


class TestSanitizeFilename:
    def test_removes_angle_brackets(self):
        assert sanitize_filename("file<>name") == "file__name"

    def test_removes_colon(self):
        assert sanitize_filename("file:name") == "file_name"

    def test_removes_quotes(self):
        assert sanitize_filename('file"name') == "file_name"

    def test_removes_slashes(self):
        assert sanitize_filename("file/name\\other") == "file_name_other"

    def test_removes_pipe(self):
        assert sanitize_filename("file|name") == "file_name"

    def test_removes_question_mark(self):
        assert sanitize_filename("file?name") == "file_name"

    def test_removes_asterisk(self):
        assert sanitize_filename("file*name") == "file_name"

    def test_clean_filename_unchanged(self):
        assert sanitize_filename("normal_file_name.pdf") == "normal_file_name.pdf"

    def test_multiple_invalid_chars(self):
        result = sanitize_filename('file<>:"/\\|?*.pdf')
        assert result == "file_________.pdf"


class TestFormatDuration:
    def test_minutes_only(self):
        assert format_duration(30) == "30m"

    def test_exactly_one_hour(self):
        assert format_duration(60) == "1h"

    def test_one_hour_and_half(self):
        assert format_duration(90) == "1h 30m"

    def test_two_hours_no_minutes(self):
        assert format_duration(120) == "2h"

    def test_two_hours_and_minutes(self):
        assert format_duration(150) == "2h 30m"

    def test_zero_minutes(self):
        assert format_duration(0) == "0m"

    def test_one_minute(self):
        assert format_duration(1) == "1m"


class TestCountWords:
    def test_simple_sentence(self):
        assert count_words("hello world") == 2

    def test_empty_string(self):
        assert count_words("") == 0

    def test_single_word(self):
        assert count_words("Python") == 1

    def test_multiple_spaces(self):
        # split() handles multiple whitespace
        assert count_words("hello  world") == 2


class TestFormatFileSize:
    def test_bytes(self):
        result = format_file_size(500)
        assert "B" in result
        assert "500" in result

    def test_kilobytes(self):
        result = format_file_size(1024)
        assert "KB" in result

    def test_megabytes(self):
        result = format_file_size(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = format_file_size(1024 * 1024 * 1024)
        assert "GB" in result

    def test_zero_bytes(self):
        result = format_file_size(0)
        assert "B" in result

    def test_partial_megabyte(self):
        result = format_file_size(1536 * 1024)  # 1.5 MB
        assert "MB" in result
        assert "1.5" in result


class TestMergeDicts:
    def test_simple_merge(self):
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 3, "c": 4}
        result = merge_dicts(d1, d2)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        d1 = {"config": {"level": "basic", "timeout": 30}}
        d2 = {"config": {"level": "advanced"}}
        result = merge_dicts(d1, d2)
        assert result["config"]["level"] == "advanced"
        assert result["config"]["timeout"] == 30  # preserved from d1

    def test_d1_not_modified(self):
        d1 = {"a": 1}
        d2 = {"b": 2}
        merge_dicts(d1, d2)
        assert "b" not in d1

    def test_empty_dicts(self):
        assert merge_dicts({}, {}) == {}

    def test_second_overrides_first(self):
        d1 = {"key": "old"}
        d2 = {"key": "new"}
        result = merge_dicts(d1, d2)
        assert result["key"] == "new"

    def test_nested_list_not_merged(self):
        """Lists are NOT recursively merged, second dict wins."""
        d1 = {"items": [1, 2]}
        d2 = {"items": [3, 4]}
        result = merge_dicts(d1, d2)
        assert result["items"] == [3, 4]


class TestTimestamp:
    def test_returns_string(self):
        result = timestamp()
        assert isinstance(result, str)

    def test_format(self):
        result = timestamp()
        # Format: YYYYMMDD_HHMMSS (15 chars)
        assert len(result) == 15
        assert result[8] == "_"
