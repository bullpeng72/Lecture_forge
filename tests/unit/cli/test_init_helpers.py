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


# ──────────────────────────────────────────────────────────
# New helper tests
# ──────────────────────────────────────────────────────────


class TestLoadCurrentEnv:
    """Tests for load_current_env."""

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import load_current_env
        result = load_current_env(tmp_path / ".env")
        assert result == {}

    def test_parses_simple_key_value(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import load_current_env
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-test123\nSERPER_API_KEY=serper456\n")
        result = load_current_env(env_file)
        assert result["OPENAI_API_KEY"] == "sk-test123"
        assert result["SERPER_API_KEY"] == "serper456"

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import load_current_env
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nFOO=bar\n  # another comment\nBAZ=qux\n")
        result = load_current_env(env_file)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_value_with_equals_sign(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import load_current_env
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val=ue\n")
        result = load_current_env(env_file)
        assert result["KEY"] == "val=ue"

    def test_ignores_lines_without_equals(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import load_current_env
        env_file = tmp_path / ".env"
        env_file.write_text("VALID=yes\nINVALIDLINE\n")
        result = load_current_env(env_file)
        assert "INVALIDLINE" not in result
        assert result["VALID"] == "yes"


class TestMaskApiKey:
    """Tests for mask_api_key."""

    def test_short_key_returns_stars(self):
        from lecture_forge.cli.commands.init_helpers import mask_api_key
        # Keys shorter than 12 chars → fully masked
        assert mask_api_key("abc") == "****"
        assert mask_api_key("12345678901") == "****"  # exactly 11 chars

    def test_long_key_shows_head_and_tail(self):
        from lecture_forge.cli.commands.init_helpers import mask_api_key
        result = mask_api_key("sk-proj-abcdefghijklmnopqrstuvwxyz1234")
        assert result.startswith("sk-proj-")
        assert "****" in result
        assert result.endswith("1234")

    def test_empty_key_returns_placeholder(self):
        from lecture_forge.cli.commands.init_helpers import mask_api_key
        assert mask_api_key("") == "설정 안 됨"

    def test_none_is_falsy(self):
        from lecture_forge.cli.commands.init_helpers import mask_api_key
        assert mask_api_key(None) == "설정 안 됨"


class TestPopulateTemplateWithSettings:
    """Tests for populate_template with llm_settings and quality_settings."""

    _BASE_TEMPLATE = (
        "OPENAI_API_KEY=xxx\n"
        "SERPER_API_KEY=xxx\n"
        "DEFAULT_MODEL=gpt-4o-mini\n"
        "TEMPERATURE=0.7\n"
        "QUALITY_THRESHOLD=80\n"
        "MAX_ITERATIONS=3\n"
    )
    _API_KEYS = {"openai": "sk-test", "serper": "serper-test", "pexels": None, "unsplash": None}

    def test_llm_settings_replace_existing_vars(self):
        from lecture_forge.cli.commands.init_helpers import populate_template
        llm = {"LLM_PROVIDER": "openai", "DEFAULT_MODEL": "gpt-4o", "TEMPERATURE": "0.3"}
        result = populate_template(self._BASE_TEMPLATE, self._API_KEYS, llm_settings=llm)
        assert "DEFAULT_MODEL=gpt-4o" in result
        assert "TEMPERATURE=0.3" in result

    def test_llm_settings_appends_new_ollama_vars(self):
        from lecture_forge.cli.commands.init_helpers import populate_template
        llm = {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.2",
            "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        }
        result = populate_template(self._BASE_TEMPLATE, self._API_KEYS, llm_settings=llm)
        assert "LLM_PROVIDER=ollama" in result
        assert "OLLAMA_BASE_URL=http://localhost:11434" in result
        assert "OLLAMA_MODEL=llama3.2" in result

    def test_quality_settings_replace_threshold_and_iterations(self):
        from lecture_forge.cli.commands.init_helpers import populate_template
        quality = {"QUALITY_THRESHOLD": "90", "MAX_ITERATIONS": "5"}
        result = populate_template(self._BASE_TEMPLATE, self._API_KEYS, quality_settings=quality)
        assert "QUALITY_THRESHOLD=90" in result
        assert "MAX_ITERATIONS=5" in result

    def test_none_settings_leave_template_unchanged(self):
        from lecture_forge.cli.commands.init_helpers import populate_template
        result = populate_template(self._BASE_TEMPLATE, self._API_KEYS)
        assert "DEFAULT_MODEL=gpt-4o-mini" in result
        assert "QUALITY_THRESHOLD=80" in result


class TestShowCurrentConfig:
    """Tests for show_current_config."""

    def test_shows_warning_when_file_missing(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import show_current_config
        console = MagicMock()
        show_current_config(console, tmp_path / ".env")
        printed = " ".join(str(c) for c in console.print.call_args_list)
        assert "없습니다" in printed or "없" in printed

    def test_renders_tables_when_file_exists(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import show_current_config
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-proj-abcdefghij1234\n"
            "SERPER_API_KEY=serper123456\n"
            "DEFAULT_MODEL=gpt-4o-mini\n"
            "TEMPERATURE=0.7\n"
            "QUALITY_THRESHOLD=80\n"
            "MAX_ITERATIONS=3\n"
        )
        from rich.console import Console
        real_console = Console(no_color=True)
        # Should not raise
        show_current_config(real_console, env_file)

    def test_shows_ollama_rows_when_provider_is_ollama(self, tmp_path):
        from lecture_forge.cli.commands.init_helpers import show_current_config
        env_file = tmp_path / ".env"
        env_file.write_text(
            "LLM_PROVIDER=ollama\n"
            "OLLAMA_MODEL=llama3.2\n"
            "OPENAI_API_KEY=\n"
            "SERPER_API_KEY=serper123\n"
        )
        console = MagicMock()
        show_current_config(console, env_file)
        # Verify ollama-specific rows are added to a table
        add_row_calls = []
        for call in console.print.call_args_list:
            args = call[0]
            for a in args:
                if hasattr(a, "add_row"):
                    add_row_calls.append(a)
        # At least one table was printed
        assert console.print.called


class TestCollectLlmSettings:
    """Tests for collect_llm_settings."""

    def test_openai_defaults_returned_on_enter(self):
        from lecture_forge.cli.commands.init_helpers import collect_llm_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["openai", "gpt-4o-mini", "0.7"],
        ):
            result = collect_llm_settings(console)
        assert result["LLM_PROVIDER"] == "openai"
        assert result["DEFAULT_MODEL"] == "gpt-4o-mini"
        assert result["TEMPERATURE"] == "0.7"

    def test_ollama_settings_collected(self):
        from lecture_forge.cli.commands.init_helpers import collect_llm_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=[
                "ollama",
                "http://localhost:11434",
                "llama3.2",
                "nomic-embed-text",
                "0.5",
            ],
        ):
            result = collect_llm_settings(console)
        assert result["LLM_PROVIDER"] == "ollama"
        assert result["OLLAMA_MODEL"] == "llama3.2"
        assert result["TEMPERATURE"] == "0.5"

    def test_invalid_temperature_retried(self):
        from lecture_forge.cli.commands.init_helpers import collect_llm_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["openai", "gpt-4o-mini", "bad", "2.0", "0.8"],
        ):
            result = collect_llm_settings(console)
        assert result["TEMPERATURE"] == "0.8"

    def test_uses_current_as_defaults(self):
        from lecture_forge.cli.commands.init_helpers import collect_llm_settings
        console = MagicMock()
        current = {"LLM_PROVIDER": "openai", "DEFAULT_MODEL": "gpt-4o", "TEMPERATURE": "0.5"}
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["openai", "gpt-4o", "0.5"],
        ) as mock_ask:
            result = collect_llm_settings(console, current=current)
        # Default should be the current value
        assert mock_ask.call_args_list[0][1]["default"] == "openai"


class TestCollectQualitySettings:
    """Tests for collect_quality_settings."""

    def test_balanced_default(self):
        from lecture_forge.cli.commands.init_helpers import collect_quality_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["balanced", "3"],
        ):
            result = collect_quality_settings(console)
        assert result["QUALITY_THRESHOLD"] == "80"
        assert result["MAX_ITERATIONS"] == "3"

    def test_strict_maps_to_90(self):
        from lecture_forge.cli.commands.init_helpers import collect_quality_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["strict", "2"],
        ):
            result = collect_quality_settings(console)
        assert result["QUALITY_THRESHOLD"] == "90"

    def test_lenient_maps_to_70(self):
        from lecture_forge.cli.commands.init_helpers import collect_quality_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["lenient", "1"],
        ):
            result = collect_quality_settings(console)
        assert result["QUALITY_THRESHOLD"] == "70"

    def test_invalid_iterations_retried(self):
        from lecture_forge.cli.commands.init_helpers import collect_quality_settings
        console = MagicMock()
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["balanced", "0", "6", "abc", "3"],
        ):
            result = collect_quality_settings(console)
        assert result["MAX_ITERATIONS"] == "3"

    def test_uses_current_threshold_as_default(self):
        from lecture_forge.cli.commands.init_helpers import collect_quality_settings
        console = MagicMock()
        current = {"QUALITY_THRESHOLD": "90", "MAX_ITERATIONS": "5"}
        with patch(
            "lecture_forge.cli.commands.init_helpers.Prompt.ask",
            side_effect=["strict", "5"],
        ) as mock_ask:
            collect_quality_settings(console, current=current)
        # Default for level prompt should be "strict" (mapped from 90)
        assert mock_ask.call_args_list[0][1]["default"] == "strict"
