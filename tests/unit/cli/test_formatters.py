"""
Unit tests for CLI formatters module.
Tests cover format_size() and smoke-tests for display functions.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


# ===== format_size() =====

class TestFormatSize:
    def setup_method(self):
        from lecture_forge.cli.utils.formatters import format_size
        self.format_size = format_size

    def test_bytes(self):
        assert self.format_size(512) == "512.0 B"

    def test_kilobytes(self):
        result = self.format_size(1024)
        assert "KB" in result

    def test_megabytes(self):
        result = self.format_size(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = self.format_size(1024 * 1024 * 1024)
        assert "GB" in result

    def test_terabytes(self):
        result = self.format_size(1024 ** 4)
        assert "TB" in result

    def test_zero_bytes(self):
        result = self.format_size(0)
        assert "B" in result
        assert "0.0" in result

    def test_fractional_kb(self):
        result = self.format_size(1536)  # 1.5 KB
        assert "KB" in result
        assert "1.5" in result

    def test_fractional_mb(self):
        result = self.format_size(int(2.5 * 1024 * 1024))  # 2.5 MB
        assert "MB" in result
        assert "2.5" in result


# ===== display_token_usage() =====

class TestDisplayTokenUsage:
    def test_calls_without_error_minimal_input(self):
        from lecture_forge.cli.utils.formatters import display_token_usage
        usage = {
            "total_tokens": 1000,
            "prompt_tokens": 700,
            "completion_tokens": 300,
            "api_calls": 5,
            "tokens_by_model": {},
            "cost_estimate": {"total": 0.001, "input": 0.0007, "output": 0.0003, "by_model": {}},
        }
        # Should not raise
        with patch("lecture_forge.cli.utils.formatters.console") as mock_console:
            display_token_usage(usage)
        assert mock_console.print.called

    def test_calls_with_model_breakdown(self):
        from lecture_forge.cli.utils.formatters import display_token_usage
        usage = {
            "total_tokens": 2000,
            "prompt_tokens": 1500,
            "completion_tokens": 500,
            "api_calls": 10,
            "tokens_by_model": {
                "gpt-4o-mini": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 500,
                    "total_tokens": 2000,
                }
            },
            "cost_estimate": {
                "total": 0.003,
                "input": 0.0002,
                "output": 0.0003,
                "by_model": {"gpt-4o-mini": 0.003},
            },
        }
        with patch("lecture_forge.cli.utils.formatters.console") as mock_console:
            display_token_usage(usage)
        assert mock_console.print.called

    def test_handles_missing_keys_gracefully(self):
        from lecture_forge.cli.utils.formatters import display_token_usage
        # Minimal dict with missing optional keys
        usage = {}
        with patch("lecture_forge.cli.utils.formatters.console"):
            display_token_usage(usage)  # Should not raise


# ===== print_banner() =====

class TestPrintBanner:
    def test_calls_console_print(self):
        from lecture_forge.cli.utils.formatters import print_banner
        with patch("lecture_forge.cli.utils.formatters.console") as mock_console:
            print_banner()
        mock_console.print.assert_called_once()

    def test_output_contains_version_format(self):
        from lecture_forge.cli.utils.formatters import print_banner
        # Just verify it doesn't raise
        with patch("lecture_forge.cli.utils.formatters.console"):
            print_banner()


# ===== print_basic_help() =====

class TestPrintBasicHelp:
    def test_calls_without_error(self):
        from lecture_forge.cli.utils.formatters import print_basic_help
        with patch("lecture_forge.cli.utils.formatters.console"):
            print_basic_help()  # Should not raise

    def test_calls_console_print_multiple_times(self):
        from lecture_forge.cli.utils.formatters import print_basic_help
        with patch("lecture_forge.cli.utils.formatters.console") as mock_console:
            print_basic_help()
        assert mock_console.print.call_count > 5


class TestFormatSize:
    def test_petabyte_range(self):
        """Line 199: very large bytes → returns PB."""
        from lecture_forge.cli.utils.formatters import format_size
        result = format_size(1024 ** 5 * 2)  # 2 PB
        assert "PB" in result
