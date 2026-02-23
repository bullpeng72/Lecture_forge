"""
Unit tests for BaseCommand class.

Tests common CLI utilities and functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

from lecture_forge.cli.utils.base_command import BaseCommand
from lecture_forge.exceptions import (
    MissingAPIKeyError,
    ConfigurationError,
    LectureForgeError,
)


class TestBaseCommand:
    """Test BaseCommand class."""

    def test_initialization(self):
        """Test BaseCommand initialization."""
        cmd = BaseCommand()

        assert cmd.console is not None
        assert cmd.config is None  # Lazy-loaded

    def test_initialization_with_console(self):
        """Test initialization with custom console."""
        custom_console = MagicMock()
        cmd = BaseCommand(console=custom_console)

        assert cmd.console == custom_console


class TestValidateRequiredEnvVars:
    """Test environment variable validation."""

    def test_all_required_keys_present(self):
        """Test when all required keys are present."""
        cmd = BaseCommand()

        with patch("lecture_forge.cli.utils.base_command.Config") as mock_config:
            mock_config.return_value.OPENAI_API_KEY = "test-key"
            mock_config.return_value.SERPER_API_KEY = "test-key"

            # Should not raise
            cmd.validate_required_env_vars(["OPENAI_API_KEY", "SERPER_API_KEY"])

    def test_missing_required_keys(self):
        """Test when required keys are missing."""
        cmd = BaseCommand(console=MagicMock())

        with patch("lecture_forge.cli.utils.base_command.Config") as mock_config:
            mock_config.return_value.OPENAI_API_KEY = None
            mock_config.return_value.SERPER_API_KEY = "test-key"

            with pytest.raises(MissingAPIKeyError) as exc_info:
                cmd.validate_required_env_vars(["OPENAI_API_KEY", "SERPER_API_KEY"])

            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_multiple_missing_keys(self):
        """Test when multiple keys are missing."""
        cmd = BaseCommand(console=MagicMock())

        with patch("lecture_forge.cli.utils.base_command.Config") as mock_config:
            mock_config.return_value.OPENAI_API_KEY = None
            mock_config.return_value.SERPER_API_KEY = None

            with pytest.raises(MissingAPIKeyError):
                cmd.validate_required_env_vars(["OPENAI_API_KEY", "SERPER_API_KEY"])


class TestResolvePath:
    """Test path resolution."""

    def test_resolve_absolute_path(self):
        """Test resolving absolute path."""
        cmd = BaseCommand()

        result = cmd.resolve_path("/tmp/test")

        assert result == Path("/tmp/test").resolve()  # resolve() dereferences symlinks (e.g. /tmp → /private/tmp on macOS)
        assert result.is_absolute()

    def test_resolve_relative_path(self):
        """Test resolving relative path."""
        cmd = BaseCommand()

        result = cmd.resolve_path("./test")

        assert result.is_absolute()

    def test_resolve_home_path(self):
        """Test resolving home path with ~."""
        cmd = BaseCommand()

        result = cmd.resolve_path("~/test")

        assert result.is_absolute()
        assert "~" not in str(result)

    def test_resolve_default_dir(self):
        """Test using default directory when path is None."""
        cmd = BaseCommand()
        default = Path("/tmp/default")

        result = cmd.resolve_path(None, default_dir=default)

        assert result == default

    def test_resolve_no_path_no_default(self):
        """Test error when no path and no default."""
        cmd = BaseCommand()

        with pytest.raises(ConfigurationError):
            cmd.resolve_path(None)


class TestEnsureDirectory:
    """Test directory creation."""

    def test_create_new_directory(self, tmp_path):
        """Test creating new directory."""
        cmd = BaseCommand()
        new_dir = tmp_path / "new_dir"

        cmd.ensure_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_ensure_existing_directory(self, tmp_path):
        """Test ensuring existing directory."""
        cmd = BaseCommand()

        cmd.ensure_directory(tmp_path)

        assert tmp_path.exists()

    def test_create_nested_directories(self, tmp_path):
        """Test creating nested directories."""
        cmd = BaseCommand()
        nested_dir = tmp_path / "a" / "b" / "c"

        cmd.ensure_directory(nested_dir)

        assert nested_dir.exists()

    def test_permission_error(self, tmp_path):
        """Test handling permission error."""
        cmd = BaseCommand(console=MagicMock())

        with patch("pathlib.Path.mkdir", side_effect=PermissionError("No permission")):
            with pytest.raises(ConfigurationError):
                cmd.ensure_directory(tmp_path / "test")


class TestConfirmOverwrite:
    """Test file overwrite confirmation."""

    def test_confirm_yes(self):
        """Test user confirms overwrite."""
        cmd = BaseCommand(console=MagicMock())

        with patch("rich.prompt.Confirm.ask", return_value=True):
            result = cmd.confirm_overwrite(Path("/tmp/test.txt"))

            assert result is True

    def test_confirm_no(self):
        """Test user declines overwrite."""
        cmd = BaseCommand(console=MagicMock())

        with patch("rich.prompt.Confirm.ask", return_value=False):
            result = cmd.confirm_overwrite(Path("/tmp/test.txt"))

            assert result is False


class TestHandleError:
    """Test error handling."""

    def test_handle_lectureforge_error(self):
        """Test handling LectureForge-specific error."""
        cmd = BaseCommand(console=MagicMock())
        error = MissingAPIKeyError("TEST_KEY")

        with pytest.raises(SystemExit) as exc_info:
            cmd.handle_error(error)

        assert exc_info.value.code == 1

    def test_handle_generic_error(self):
        """Test handling generic error."""
        cmd = BaseCommand(console=MagicMock())
        error = ValueError("Something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            cmd.handle_error(error)

        assert exc_info.value.code == 1

    def test_handle_error_custom_exit_code(self):
        """Test handling error with custom exit code."""
        cmd = BaseCommand(console=MagicMock())
        error = RuntimeError("Test error")

        with pytest.raises(SystemExit) as exc_info:
            cmd.handle_error(error, exit_code=42)

        assert exc_info.value.code == 42


class TestSetFilePermissions:
    """Test file permissions setting."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only test")
    def test_set_permissions_unix(self, tmp_path):
        """Test setting file permissions on Unix."""
        cmd = BaseCommand(console=MagicMock())
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        cmd.set_file_permissions(test_file, mode=0o600)

        # Verify permissions
        import os
        stat_info = os.stat(test_file)
        assert stat_info.st_mode & 0o777 == 0o600

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_set_permissions_windows_skip(self, tmp_path):
        """Test that permissions are skipped on Windows."""
        cmd = BaseCommand(console=MagicMock())
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Should not raise on Windows
        cmd.set_file_permissions(test_file)


class TestShowBanner:
    """Test banner display."""

    def test_show_default_banner(self):
        """Test showing banner with default style."""
        console = MagicMock()
        cmd = BaseCommand(console=console)

        cmd.show_banner("Test Title")

        # Should call console.print at least twice (empty line + panel + empty line)
        assert console.print.call_count >= 2

    def test_show_banner_custom_style(self):
        """Test showing banner with custom style."""
        console = MagicMock()
        cmd = BaseCommand(console=console)

        cmd.show_banner("Test Title", border_style="red")

        assert console.print.call_count >= 2


class TestCreateProgress:
    """Test progress indicator creation."""

    def test_create_progress(self):
        """Test creating progress indicator."""
        cmd = BaseCommand()

        progress = cmd.create_progress("Processing")

        assert progress is not None
        # Rich Progress object has these attributes
        assert hasattr(progress, "add_task")
        assert hasattr(progress, "update")
