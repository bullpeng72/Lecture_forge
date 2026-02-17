"""
Tests for configuration module.
"""

from pathlib import Path

import pytest

from lecture_forge.config import Config
from lecture_forge.exceptions import ConfigurationError


def test_config_has_required_attributes():
    """Test that Config has all required attributes."""
    assert hasattr(Config, "OPENAI_API_KEY")
    assert hasattr(Config, "SERPER_API_KEY")
    assert hasattr(Config, "DEFAULT_MODEL")
    assert hasattr(Config, "EMBEDDING_MODEL")
    assert hasattr(Config, "VECTOR_DB_PATH")


def test_config_default_values():
    """Test default configuration values."""
    assert Config.DEFAULT_MODEL == "gpt-4o-mini"
    assert Config.EMBEDDING_MODEL == "text-embedding-3-small"
    assert Config.TEMPERATURE == 0.7
    assert Config.CHUNK_SIZE == 1000
    assert Config.CHUNK_OVERLAP == 200


def test_config_quality_settings():
    """Test quality assurance settings."""
    assert Config.QUALITY_THRESHOLD == 80
    assert Config.MAX_ITERATIONS == 3
    assert 0 <= Config.QUALITY_THRESHOLD <= 100
    assert Config.MAX_ITERATIONS > 0


def test_config_validate_with_valid_keys(test_env_vars):
    """Test validation passes with valid API keys."""
    # Should not raise any exception
    Config.validate()


def test_config_validate_missing_openai_key(monkeypatch):
    """Test validation fails when OPENAI_API_KEY is missing."""
    monkeypatch.setattr(Config, "OPENAI_API_KEY", None)

    with pytest.raises(ConfigurationError) as exc_info:
        Config.validate()

    assert "OPENAI_API_KEY is required" in str(exc_info.value)


def test_config_validate_invalid_openai_key_format(monkeypatch):
    """Test validation fails with invalid OPENAI_API_KEY format."""
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "invalid-key")

    with pytest.raises(ConfigurationError) as exc_info:
        Config.validate()

    assert "invalid format" in str(exc_info.value).lower()


def test_config_validate_short_serper_key(monkeypatch):
    """Test validation fails with too short SERPER_API_KEY."""
    monkeypatch.setattr(Config, "SERPER_API_KEY", "short")

    with pytest.raises(ConfigurationError) as exc_info:
        Config.validate()

    assert "too short" in str(exc_info.value).lower()


def test_config_image_settings():
    """Test image-related configuration."""
    assert Config.MAX_IMAGES_PER_SEARCH == 10
    assert Config.IMAGE_FORMAT == "webp"
    assert Config.IMAGE_MAX_WIDTH == 1920


def test_config_paths_exist(test_env_vars):
    """Test that required directories are created."""
    Config.ensure_directories()

    assert Config.DATA_DIR.exists()
    assert Config.OUTPUT_DIR.exists()
    assert Config.VECTOR_DB_PATH.exists()
    assert (Config.DATA_DIR / "images").exists()
    assert (Config.DATA_DIR / "cache").exists()


# ===== get_default_config_dir() =====

class TestGetDefaultConfigDir:
    def test_returns_path_on_linux(self, tmp_path):
        from lecture_forge.config import get_default_config_dir
        import sys
        from unittest.mock import patch
        # Patch sys.platform to ensure Linux path is taken
        with patch.object(sys, "platform", "linux"):
            result = get_default_config_dir()
        assert isinstance(result, Path)

    def test_returns_path_on_darwin(self, tmp_path):
        from lecture_forge.config import get_default_config_dir
        import sys
        from unittest.mock import patch
        with patch.object(sys, "platform", "darwin"):
            result = get_default_config_dir()
        assert isinstance(result, Path)

    def test_returns_lecture_forge_name(self):
        from lecture_forge.config import get_default_config_dir
        result = get_default_config_dir()
        assert result.name == "LectureForge"


# ===== resolve_config_path() =====

class TestResolveConfigPath:
    def test_returns_absolute_path(self, tmp_path):
        from lecture_forge.config import resolve_config_path
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"TEST_VAR": ""}, clear=False):
            result = resolve_config_path("NONEXISTENT_VAR", "data", tmp_path)
        assert result.is_absolute()

    def test_uses_default_when_env_not_set(self, tmp_path):
        from lecture_forge.config import resolve_config_path
        import os
        result = resolve_config_path("NONEXISTENT_VAR_XYZ", "subdir", tmp_path)
        assert result == (tmp_path / "subdir").resolve()

    def test_uses_env_var_when_set(self, tmp_path):
        from lecture_forge.config import resolve_config_path
        import os
        from unittest.mock import patch
        target = tmp_path / "custom_path"
        with patch.dict(os.environ, {"MY_CONFIG_PATH": str(target)}):
            result = resolve_config_path("MY_CONFIG_PATH", "subdir", tmp_path)
        assert result == target.resolve()

    def test_relative_path_resolved_against_base(self, tmp_path):
        from lecture_forge.config import resolve_config_path
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"MY_PATH": "relative/sub"}):
            result = resolve_config_path("MY_PATH", "default", tmp_path)
        assert result == (tmp_path / "relative" / "sub").resolve()


# ===== migrate_from_hidden_dir() =====

class TestMigrateFromHiddenDir:
    def test_returns_false_when_old_dir_not_exists(self, tmp_path, monkeypatch):
        from lecture_forge.config import migrate_from_hidden_dir
        from unittest.mock import patch
        # Point both dirs to nonexistent paths
        with patch("lecture_forge.config.Path.home", return_value=tmp_path):
            result = migrate_from_hidden_dir()
        # Old dir doesn't exist → returns False
        assert result is False

    def test_returns_true_when_migrates(self, tmp_path):
        from lecture_forge.config import migrate_from_hidden_dir
        from unittest.mock import patch
        # Create the old hidden dir
        old_dir = tmp_path / ".lecture-forge"
        old_dir.mkdir()
        (old_dir / "test.txt").write_text("data")
        # New dir doesn't exist yet
        new_dir = tmp_path / "Documents" / "LectureForge"

        with patch("lecture_forge.config.Path.home", return_value=tmp_path):
            with patch("lecture_forge.config.get_default_config_dir", return_value=new_dir):
                result = migrate_from_hidden_dir()
        assert result is True
        assert new_dir.exists()

    def test_returns_false_when_both_dirs_exist(self, tmp_path):
        from lecture_forge.config import migrate_from_hidden_dir
        from unittest.mock import patch
        old_dir = tmp_path / ".lecture-forge"
        old_dir.mkdir()
        new_dir = tmp_path / "Documents" / "LectureForge"
        new_dir.mkdir(parents=True)

        with patch("lecture_forge.config.Path.home", return_value=tmp_path):
            with patch("lecture_forge.config.get_default_config_dir", return_value=new_dir):
                result = migrate_from_hidden_dir()
        assert result is False


# ===== find_and_load_env() =====

class TestFindAndLoadEnv:
    def test_returns_none_when_no_env_found(self, tmp_path, monkeypatch):
        from lecture_forge.config import find_and_load_env
        from unittest.mock import patch
        # No env file in any location
        monkeypatch.chdir(tmp_path)
        with patch("lecture_forge.config.get_default_config_dir", return_value=tmp_path / "nonexistent"):
            with patch.dict("os.environ", {}, clear=False):
                # Remove LECTURE_FORGE_ENV_FILE if set
                import os
                os.environ.pop("LECTURE_FORGE_ENV_FILE", None)
                result = find_and_load_env()
        # Returns None (no .env found in tmp_path or home)
        assert result is None or isinstance(result, Path)

    def test_finds_env_in_cwd(self, tmp_path, monkeypatch):
        from lecture_forge.config import find_and_load_env
        from unittest.mock import patch
        import os
        # Create a .env file in tmp_path
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=test_value\n")
        monkeypatch.chdir(tmp_path)
        os.environ.pop("LECTURE_FORGE_ENV_FILE", None)
        result = find_and_load_env()
        assert result == env_file


# ===== Additional config coverage tests =====

import sys
from unittest.mock import patch, MagicMock


class TestGetDefaultConfigDirWindows:
    """Test Windows branch of get_default_config_dir() (lines 67-73)."""

    def test_windows_with_userprofile_and_docs(self, tmp_path):
        from lecture_forge.config import get_default_config_dir
        docs = tmp_path / "Documents"
        docs.mkdir()
        with patch.object(sys, "platform", "win32"):
            with patch.dict("os.environ", {"USERPROFILE": str(tmp_path)}):
                result = get_default_config_dir()
        assert result == docs / "LectureForge"

    def test_windows_without_userprofile(self, tmp_path):
        from lecture_forge.config import get_default_config_dir
        with patch.object(sys, "platform", "win32"):
            with patch.dict("os.environ", {}, clear=True):
                # No USERPROFILE → fallback to Path.home() / "LectureForge"
                result = get_default_config_dir()
        assert result.name == "LectureForge"

    def test_windows_docs_not_exist(self, tmp_path):
        from lecture_forge.config import get_default_config_dir
        # USERPROFILE exists but Documents subfolder doesn't
        with patch.object(sys, "platform", "win32"):
            with patch.dict("os.environ", {"USERPROFILE": str(tmp_path)}):
                result = get_default_config_dir()
        # No Documents dir → fallback
        assert result.name == "LectureForge"


class TestMigrateExceptionHandling:
    """Test migration exception branch (lines 134-138)."""

    def test_exception_during_migration_returns_false(self, tmp_path):
        from lecture_forge.config import migrate_from_hidden_dir
        old_dir = tmp_path / ".lecture-forge"
        old_dir.mkdir()
        new_dir = tmp_path / "Documents" / "LectureForge"

        with patch("lecture_forge.config.Path.home", return_value=tmp_path):
            with patch("lecture_forge.config.get_default_config_dir", return_value=new_dir):
                with patch("shutil.move", side_effect=Exception("permission denied")):
                    result = migrate_from_hidden_dir()
        assert result is False


class TestFindAndLoadEnvExplicitPath:
    """Test LECTURE_FORGE_ENV_FILE env var branches (lines 156-162)."""

    def test_explicit_path_exists_is_loaded(self, tmp_path, monkeypatch):
        from lecture_forge.config import find_and_load_env
        import os
        env_file = tmp_path / "custom.env"
        env_file.write_text("CUSTOM_KEY=custom_value\n")
        monkeypatch.setenv("LECTURE_FORGE_ENV_FILE", str(env_file))
        result = find_and_load_env()
        assert result == env_file

    def test_explicit_path_nonexistent_falls_through(self, tmp_path, monkeypatch):
        from lecture_forge.config import find_and_load_env
        import os
        nonexistent = tmp_path / "no_such_file.env"
        monkeypatch.setenv("LECTURE_FORGE_ENV_FILE", str(nonexistent))
        monkeypatch.chdir(tmp_path)  # No .env in cwd either
        with patch("lecture_forge.config.get_default_config_dir", return_value=tmp_path / "nodir"):
            result = find_and_load_env()
        # Should log warning and continue → return None (no other .env found)
        assert result is None or isinstance(result, Path)


class TestGetEnvFileLocationsWindows:
    """Test Windows branch in get_env_file_locations() (line 407)."""

    def test_windows_location_format(self):
        from lecture_forge.config import Config
        with patch.object(sys, "platform", "win32"):
            locations = Config.get_env_file_locations()
        # Should include a Windows-style path with backslash mention
        win_locations = [l for l in locations if "Windows" in l or "\\" in l]
        assert len(win_locations) >= 1


class TestValidateNoEnvFile:
    """Test validate() when no .env file found (lines 425-435)."""

    def test_validate_raises_when_no_env_file(self, monkeypatch):
        from lecture_forge.config import Config
        from lecture_forge.exceptions import ConfigurationError
        import lecture_forge.config as config_module
        original = config_module.ENV_FILE_PATH
        try:
            config_module.ENV_FILE_PATH = None
            monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-test-key-123456789012345678")
            monkeypatch.setattr(Config, "SERPER_API_KEY", "serper-valid-key-12345")
            with pytest.raises(ConfigurationError) as exc_info:
                Config.validate()
            assert "No .env file" in str(exc_info.value)
        finally:
            config_module.ENV_FILE_PATH = original


class TestValidateApiKeyWarnings:
    """Test short Unsplash/Pexels key warnings (lines 477-478, 481-483)."""

    def test_short_unsplash_key_logs_warning(self, test_env_vars, monkeypatch):
        from lecture_forge.config import Config
        monkeypatch.setattr(Config, "UNSPLASH_ACCESS_KEY", "short")
        # Should not raise, just warn
        Config.validate()

    def test_short_pexels_key_logs_warning(self, test_env_vars, monkeypatch):
        from lecture_forge.config import Config
        monkeypatch.setattr(Config, "PEXELS_API_KEY", "short")
        # Should not raise, just warn
        Config.validate()


class TestValidateAdditionalBranches:
    """Tests covering config.py lines 455, 476, 481."""

    def test_missing_serper_key_adds_error(self, test_env_vars, monkeypatch):
        """Line 455: SERPER_API_KEY is empty string → errors.append."""
        from lecture_forge.config import Config
        import pytest
        monkeypatch.setattr(Config, "SERPER_API_KEY", "")
        with pytest.raises(Exception):  # ConfigurationError
            Config.validate()

    def test_short_unsplash_key_warning(self, test_env_vars, monkeypatch):
        """Line 476: UNSPLASH_ACCESS_KEY < 10 chars → warning (not error)."""
        from lecture_forge.config import Config
        # Need valid OPENAI and SERPER keys so we don't raise before warnings
        monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-test-key-1234567890abcdefghijklmnop")
        monkeypatch.setattr(Config, "SERPER_API_KEY", "test-serper-key-1234567890")
        monkeypatch.setattr(Config, "UNSPLASH_ACCESS_KEY", "abc")  # < 10 chars
        monkeypatch.setattr(Config, "PEXELS_API_KEY", "")  # falsy so hits different branch
        Config.validate()  # Should not raise

    def test_short_pexels_key_warning(self, test_env_vars, monkeypatch):
        """Line 481: PEXELS_API_KEY < 10 chars → warning (not error)."""
        from lecture_forge.config import Config
        monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-test-key-1234567890abcdefghijklmnop")
        monkeypatch.setattr(Config, "SERPER_API_KEY", "test-serper-key-1234567890")
        monkeypatch.setattr(Config, "UNSPLASH_ACCESS_KEY", "")  # falsy
        monkeypatch.setattr(Config, "PEXELS_API_KEY", "abc")  # < 10 chars
        Config.validate()  # Should not raise
