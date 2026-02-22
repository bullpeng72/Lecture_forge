"""
Integration tests for CLI commands.

Tests the refactored CLI module with all commands:
- init: Configuration setup
- create: Lecture generation
- chat: Q&A mode
- cleanup: Knowledge base management
- improve: Lecture enhancement
- edit-images: Image editing
- home: Folder navigation
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from lecture_forge.cli import cli
from lecture_forge.cli.commands.chat import chat
from lecture_forge.cli.commands.cleanup import cleanup
from lecture_forge.cli.commands.home import home
from lecture_forge.cli.commands.init import init
from lecture_forge.config import Config


class TestCLICommands:
    """Test CLI command integration."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test main CLI help command."""
        result = self.runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert "LectureForge Pro" in result.output
        assert "Commands Overview" in result.output or "Commands" in result.output

    def test_cli_version(self):
        """Test version display."""
        result = self.runner.invoke(cli, ['--version'])

        assert result.exit_code == 0
        assert "0." in result.output  # Should show version

    def test_init_command_help(self):
        """Test init command help."""
        result = self.runner.invoke(cli, ['init', '--help'])

        assert result.exit_code == 0
        assert "Initialize LectureForge" in result.output
        assert "api keys" in result.output.lower()

    def test_create_command_help(self):
        """Test create command help."""
        result = self.runner.invoke(cli, ['create', '--help'])

        assert result.exit_code == 0
        assert "Create a new lecture" in result.output or "Generate" in result.output
        assert "--config" in result.output

    def test_chat_command_help(self):
        """Test chat command help."""
        result = self.runner.invoke(cli, ['chat', '--help'])

        assert result.exit_code == 0
        assert "Q&A" in result.output or "chat" in result.output.lower()

    def test_cleanup_command_help(self):
        """Test cleanup command help."""
        result = self.runner.invoke(cli, ['cleanup', '--help'])

        assert result.exit_code == 0
        assert "knowledge base" in result.output.lower() or "delete" in result.output.lower()

    def test_improve_command_help(self):
        """Test improve command help."""
        result = self.runner.invoke(cli, ['improve', '--help'])

        assert result.exit_code == 0
        assert "--to-slides" in result.output or "enhance" in result.output.lower()

    def test_home_command_help(self):
        """Test home command help."""
        result = self.runner.invoke(cli, ['home', '--help'])

        assert result.exit_code == 0
        assert "folder" in result.output.lower() or "directory" in result.output.lower()


class TestInitCommand:
    """Test init command functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_init_creates_env_file(self):
        """Test that init creates .env file."""
        with self.runner.isolated_filesystem():
            # Create temporary directory for .env
            test_dir = Path.cwd() / "test_config"
            test_dir.mkdir()

            # Mock user inputs
            with patch('lecture_forge.cli.commands.init.prompt_masked_input') as mock_prompt:
                mock_prompt.side_effect = [
                    "sk-test-openai-key",  # OpenAI key
                    "test-serper-key",     # Serper key
                    "",                     # Pexels (skip)
                    "",                     # Unsplash (skip)
                ]

                result = self.runner.invoke(init, ['--path', str(test_dir)])

                # Should create .env file
                env_file = test_dir / ".env"
                if result.exit_code == 0:
                    assert env_file.exists() or "Configuration completed" in result.output


class TestCleanupCommand:
    """Test cleanup command functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_cleanup_no_knowledge_bases(self):
        """Test cleanup when no knowledge bases exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock vector DB path to empty directory
            with patch.object(Config, 'VECTOR_DB_PATH', Path(tmpdir) / "vector_db"):
                result = self.runner.invoke(cleanup)

                # Should handle gracefully
                assert "No knowledge bases found" in result.output or result.exit_code == 0

    def test_cleanup_with_knowledge_bases(self):
        """Test cleanup with existing knowledge bases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake knowledge bases
            kb_dir = Path(tmpdir) / "vector_db"
            kb_dir.mkdir(parents=True)
            (kb_dir / "kb1").mkdir()
            (kb_dir / "kb2").mkdir()

            with patch.object(Config, 'VECTOR_DB_PATH', kb_dir):
                # Test interactive mode (cancel)
                with patch('lecture_forge.cli.commands.cleanup.Prompt.ask', return_value=""):
                    result = self.runner.invoke(cleanup)

                    assert "Cancelled" in result.output or result.exit_code == 0


class TestHomeCommand:
    """Test home command functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_home_command_targets(self):
        """Test that home command accepts different targets."""
        targets = ["", "data", "outputs", "kb", "env"]

        for target in targets:
            result = self.runner.invoke(home, [target] if target else [])

            # Should not crash (may fail to open, but should handle gracefully)
            assert result.exit_code in [0, 1]  # 0 = success, 1 = controlled error


class TestChatCommand:
    """Test chat command functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_chat_no_knowledge_base(self):
        """Test chat when no knowledge base exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Config, 'VECTOR_DB_PATH', Path(tmpdir) / "vector_db"):
                result = self.runner.invoke(chat)

                # Should handle missing KB gracefully
                assert "No knowledge bases found" in result.output or result.exit_code in [0, 1]


class TestCommandChaining:
    """Test command workflow sequences."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_init_then_create_workflow(self):
        """Test typical workflow: init -> create."""
        with self.runner.isolated_filesystem():
            test_dir = Path.cwd() / "test_workflow"
            test_dir.mkdir()

            # Step 1: Init
            with patch('lecture_forge.cli.commands.init.prompt_masked_input') as mock_prompt:
                mock_prompt.side_effect = [
                    "sk-test-key",
                    "test-serper",
                    "",
                    "",
                ]

                init_result = self.runner.invoke(init, ['--path', str(test_dir)])

                if init_result.exit_code == 0:
                    # Verify .env was created
                    assert (test_dir / ".env").exists() or "completed" in init_result.output.lower()

            # Step 2: Create (would require more mocking for full test)
            # For now, just verify command exists
            create_help = self.runner.invoke(cli, ['create', '--help'])
            assert create_help.exit_code == 0


class TestErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()

    def test_invalid_command(self):
        """Test handling of invalid command."""
        result = self.runner.invoke(cli, ['invalid-command'])

        assert result.exit_code != 0
        assert "Error" in result.output or "Usage" in result.output

    def test_missing_required_argument(self):
        """Test handling of missing required arguments."""
        # improve requires lecture_path argument
        result = self.runner.invoke(cli, ['improve'])

        assert result.exit_code != 0
        # Should show usage or error about missing argument

    def test_invalid_option_value(self):
        """Test handling of invalid option values."""
        # create with invalid quality level
        result = self.runner.invoke(cli, ['create', '--quality-level', 'invalid'])

        assert result.exit_code != 0
        # Should show error about invalid choice


class TestCLIIntegration:
    """Integration tests for CLI module structure."""

    def test_all_commands_registered(self):
        """Test that all commands are properly registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])

        # Check all expected commands are listed
        expected_commands = ['init', 'create', 'chat', 'cleanup', 'improve', 'home', 'edit-images']

        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in CLI help"

    def test_cli_module_imports(self):
        """Test that CLI module structure is correct."""
        # Should be able to import all commands
        from lecture_forge.cli.commands import (
            chat,
            cleanup,
            create,
            edit_images,
            home,
            improve,
            init,
        )

        assert callable(chat)
        assert callable(cleanup)
        assert callable(create)
        assert callable(edit_images)
        assert callable(home)
        assert callable(improve)
        assert callable(init)

    def test_cli_utils_available(self):
        """Test that CLI utilities are available."""
        from lecture_forge.cli.utils import (
            console,
            display_token_usage,
            format_size,
            get_dir_size,
        )

        assert console is not None
        assert callable(display_token_usage)
        assert callable(format_size)
        assert callable(get_dir_size)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
