"""
Unit tests for cleanup CLI command.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_vector_db(tmp_path):
    """Create a fake vector DB directory with two KB subdirs."""
    vdb = tmp_path / "vector_db"
    vdb.mkdir()
    kb1 = vdb / "MyLecture_20260101_120000"
    kb1.mkdir()
    (kb1 / "chroma.sqlite3").write_bytes(b"x" * 1024)
    kb2 = vdb / "AnotherLecture_20260201_090000"
    kb2.mkdir()
    (kb2 / "chroma.sqlite3").write_bytes(b"x" * 512)
    return vdb


class TestCleanupNoKBDir:
    def test_no_vector_db_dir(self, runner, tmp_path):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg:
            mock_cfg.VECTOR_DB_PATH = str(tmp_path / "nonexistent")
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "No knowledge bases found" in result.output

    def test_empty_vector_db_dir(self, runner, tmp_path):
        from lecture_forge.cli.commands.cleanup import cleanup
        empty_dir = tmp_path / "vector_db"
        empty_dir.mkdir()
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg:
            mock_cfg.VECTOR_DB_PATH = str(empty_dir)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "No knowledge bases found" in result.output


class TestCleanupAllFlag:
    def test_all_flag_cancelled(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=1024), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=False):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, ["--all"])
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_all_flag_confirmed_deletes(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=1024), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=True), \
             patch("lecture_forge.cli.commands.cleanup.shutil.rmtree") as mock_rmtree:
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, ["--all"])
        assert result.exit_code == 0
        assert mock_rmtree.call_count == 2
        assert "Deleted" in result.output

    def test_all_flag_delete_error_handled(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=512), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=True), \
             patch("lecture_forge.cli.commands.cleanup.shutil.rmtree", side_effect=OSError("perm denied")):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, ["--all"])
        assert result.exit_code == 0
        assert "Failed to delete" in result.output


class TestCleanupInteractive:
    def test_interactive_empty_choice_cancels(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=1024), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value=""):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_interactive_valid_selection_then_cancel(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=1024), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="1"), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=False):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_interactive_valid_selection_confirmed(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=1024), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="1"), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=True), \
             patch("lecture_forge.cli.commands.cleanup.shutil.rmtree") as mock_rmtree:
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert mock_rmtree.call_count == 1

    def test_interactive_multi_selection(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=512), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="1,2"), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=True), \
             patch("lecture_forge.cli.commands.cleanup.shutil.rmtree") as mock_rmtree:
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert mock_rmtree.call_count == 2

    def test_interactive_out_of_range_selection(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=512), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="99"):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "No valid selections" in result.output

    def test_interactive_invalid_input(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=512), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="abc"):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "Invalid selection" in result.output

    def test_interactive_delete_error_handled(self, runner, mock_vector_db):
        from lecture_forge.cli.commands.cleanup import cleanup
        with patch("lecture_forge.cli.commands.cleanup.Config") as mock_cfg, \
             patch("lecture_forge.cli.commands.cleanup.get_dir_size", return_value=512), \
             patch("lecture_forge.cli.commands.cleanup.Prompt.ask", return_value="1"), \
             patch("lecture_forge.cli.commands.cleanup.Confirm.ask", return_value=True), \
             patch("lecture_forge.cli.commands.cleanup.shutil.rmtree", side_effect=OSError("busy")):
            mock_cfg.VECTOR_DB_PATH = str(mock_vector_db)
            result = runner.invoke(cleanup, [])
        assert result.exit_code == 0
        assert "Failed to delete" in result.output
