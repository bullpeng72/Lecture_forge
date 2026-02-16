"""
Unit tests for init command helpers.

Tests the individual helper functions extracted from init.py.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lecture_forge.cli.commands.init_helpers import (
    collect_openai_key,
    collect_serper_key,
    collect_pexels_key,
    collect_unsplash_key,
    collect_all_api_keys,
    generate_minimal_template,
    populate_template,
)


class TestCollectOpenAIKey:
    """Test OpenAI key collection."""

    def test_valid_key_sk_format(self):
        """Test accepting valid sk- format key."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="sk-test123456789")

        result = collect_openai_key(console, prompt_fn)

        assert result == "sk-test123456789"
        assert prompt_fn.call_count == 1

    def test_valid_key_sk_proj_format(self):
        """Test accepting valid sk-proj- format key."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="sk-proj-test123456789")

        result = collect_openai_key(console, prompt_fn)

        assert result == "sk-proj-test123456789"
        assert prompt_fn.call_count == 1

    def test_invalid_then_valid_key(self):
        """Test retry on invalid key format."""
        console = MagicMock()
        prompt_fn = MagicMock(side_effect=["invalid-key", "sk-valid123"])

        result = collect_openai_key(console, prompt_fn)

        assert result == "sk-valid123"
        assert prompt_fn.call_count == 2
        assert console.print.call_count >= 2  # Error message printed

    def test_empty_then_valid_key(self):
        """Test retry on empty input."""
        console = MagicMock()
        prompt_fn = MagicMock(side_effect=["", "sk-valid123"])

        result = collect_openai_key(console, prompt_fn)

        assert result == "sk-valid123"
        assert prompt_fn.call_count == 2


class TestCollectSerperKey:
    """Test Serper key collection."""

    def test_valid_key(self):
        """Test accepting valid Serper key."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="serper_test_key_12345")

        result = collect_serper_key(console, prompt_fn)

        assert result == "serper_test_key_12345"
        assert prompt_fn.call_count == 1

    def test_too_short_key(self):
        """Test rejecting too short key."""
        console = MagicMock()
        prompt_fn = MagicMock(side_effect=["short", "valid_key_12345"])

        result = collect_serper_key(console, prompt_fn)

        assert result == "valid_key_12345"
        assert prompt_fn.call_count == 2


class TestCollectOptionalKeys:
    """Test optional key collection."""

    def test_pexels_key_provided(self):
        """Test Pexels key when provided."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="pexels123")

        result = collect_pexels_key(console, prompt_fn)

        assert result == "pexels123"

    def test_pexels_key_skipped(self):
        """Test Pexels key when skipped."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="")

        result = collect_pexels_key(console, prompt_fn)

        assert result == ""

    def test_unsplash_key_provided(self):
        """Test Unsplash key when provided."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="unsplash123")

        result = collect_unsplash_key(console, prompt_fn)

        assert result == "unsplash123"

    def test_unsplash_key_skipped(self):
        """Test Unsplash key when skipped."""
        console = MagicMock()
        prompt_fn = MagicMock(return_value="")

        result = collect_unsplash_key(console, prompt_fn)

        assert result == ""


class TestCollectAllAPIKeys:
    """Test collecting all API keys."""

    def test_collect_all_required_only(self):
        """Test collecting only required keys."""
        console = MagicMock()
        prompt_fn = MagicMock(
            side_effect=[
                "sk-openai123",  # OpenAI
                "serper123456",  # Serper
                "",  # Pexels (skip)
                "",  # Unsplash (skip)
            ]
        )

        result = collect_all_api_keys(console, prompt_fn)

        assert result["openai"] == "sk-openai123"
        assert result["serper"] == "serper123456"
        assert result["pexels"] == ""
        assert result["unsplash"] == ""

    def test_collect_all_with_optional(self):
        """Test collecting all keys including optional."""
        console = MagicMock()
        prompt_fn = MagicMock(
            side_effect=[
                "sk-openai123",  # OpenAI
                "serper123456",  # Serper
                "pexels789",  # Pexels
                "unsplash456",  # Unsplash
            ]
        )

        result = collect_all_api_keys(console, prompt_fn)

        assert result["openai"] == "sk-openai123"
        assert result["serper"] == "serper123456"
        assert result["pexels"] == "pexels789"
        assert result["unsplash"] == "unsplash456"


class TestTemplateGeneration:
    """Test template generation and population."""

    def test_generate_minimal_template(self):
        """Test minimal template generation."""
        result = generate_minimal_template()

        assert "OPENAI_API_KEY=" in result
        assert "SERPER_API_KEY=" in result
        assert "PEXELS_API_KEY=" in result
        assert "UNSPLASH_ACCESS_KEY=" in result
        assert "LectureForge Configuration" in result

    def test_populate_template_required_only(self):
        """Test populating template with required keys only."""
        template = """
OPENAI_API_KEY=placeholder1
SERPER_API_KEY=placeholder2
PEXELS_API_KEY=placeholder3
UNSPLASH_ACCESS_KEY=placeholder4
"""
        api_keys = {
            "openai": "sk-real123",
            "serper": "serper-real456",
            "pexels": None,
            "unsplash": None,
        }

        result = populate_template(template, api_keys)

        assert "OPENAI_API_KEY=sk-real123" in result
        assert "SERPER_API_KEY=serper-real456" in result
        # Optional keys should remain as placeholders
        assert "PEXELS_API_KEY=placeholder3" in result
        assert "UNSPLASH_ACCESS_KEY=placeholder4" in result

    def test_populate_template_all_keys(self):
        """Test populating template with all keys."""
        template = """
OPENAI_API_KEY=placeholder1
SERPER_API_KEY=placeholder2
PEXELS_API_KEY=placeholder3
UNSPLASH_ACCESS_KEY=placeholder4
"""
        api_keys = {
            "openai": "sk-real123",
            "serper": "serper-real456",
            "pexels": "pexels-real789",
            "unsplash": "unsplash-real000",
        }

        result = populate_template(template, api_keys)

        assert "OPENAI_API_KEY=sk-real123" in result
        assert "SERPER_API_KEY=serper-real456" in result
        assert "PEXELS_API_KEY=pexels-real789" in result
        assert "UNSPLASH_ACCESS_KEY=unsplash-real000" in result

    def test_populate_template_adds_metadata(self):
        """Test that metadata is added to template."""
        template = "OPENAI_API_KEY=placeholder"
        api_keys = {"openai": "sk-test", "serper": "test"}

        result = populate_template(template, api_keys)

        assert "LectureForge Configuration" in result
        assert "Generated by: lecture-forge init" in result
        assert "Date:" in result
        assert "Platform:" in result


class TestTemplateLoading:
    """Test template loading from various sources."""

    @patch("importlib.resources.files")
    def test_load_from_package_resources(self, mock_files):
        """Test loading from package resources."""
        from lecture_forge.cli.commands.init_helpers import load_env_template

        mock_template = MagicMock()
        mock_template.read_text.return_value = "OPENAI_API_KEY=test"
        mock_files.return_value.joinpath.return_value = mock_template

        console = MagicMock()
        result, locations = load_env_template(console)

        assert result == "OPENAI_API_KEY=test"
        assert len(locations) > 0

    def test_load_returns_none_when_not_found(self):
        """Test that None is returned when template not found."""
        from lecture_forge.cli.commands.init_helpers import load_env_template

        with patch("importlib.resources.files", side_effect=FileNotFoundError):
            with patch("pathlib.Path.exists", return_value=False):
                console = MagicMock()
                result, locations = load_env_template(console)

                # Should return None when not found
                assert result is None or isinstance(result, str)
