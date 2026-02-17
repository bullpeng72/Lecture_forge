"""
Unit tests for CLI cleanup_helpers module.
Tests cover get_knowledge_bases, create_kb_table, parse_user_selection,
delete_knowledge_bases, confirm_deletion_all, interactive_selection,
and display_cleanup_results.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===== get_knowledge_bases() =====

class TestGetKnowledgeBases:
    def test_returns_empty_when_dir_not_exists(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import get_knowledge_bases
        result = get_knowledge_bases(tmp_path / "nonexistent")
        assert result == []

    def test_returns_sorted_dirs(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import get_knowledge_bases
        import time
        d1 = tmp_path / "KB_001"
        d1.mkdir()
        time.sleep(0.01)
        d2 = tmp_path / "KB_002"
        d2.mkdir()
        result = get_knowledge_bases(tmp_path)
        # Newest first
        assert result[0].name == "KB_002"
        assert result[1].name == "KB_001"

    def test_ignores_files(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import get_knowledge_bases
        (tmp_path / "file.txt").write_text("not a dir")
        (tmp_path / "KB_001").mkdir()
        result = get_knowledge_bases(tmp_path)
        assert len(result) == 1
        assert result[0].name == "KB_001"

    def test_empty_dir_returns_empty_list(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import get_knowledge_bases
        result = get_knowledge_bases(tmp_path)
        assert result == []

    def test_returns_list_of_path_objects(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import get_knowledge_bases
        (tmp_path / "KB_001").mkdir()
        result = get_knowledge_bases(tmp_path)
        assert all(isinstance(p, Path) for p in result)


# ===== create_kb_table() =====

class TestCreateKbTable:
    def test_returns_table_and_total_size(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import create_kb_table
        d = tmp_path / "KB_001"
        d.mkdir()
        get_size = MagicMock(return_value=1024)
        fmt_size = MagicMock(return_value="1.0 KB")
        table, total = create_kb_table([d], get_size, fmt_size)
        assert total == 1024
        assert table is not None

    def test_total_size_sums_multiple(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import create_kb_table
        d1 = tmp_path / "KB_001"
        d1.mkdir()
        d2 = tmp_path / "KB_002"
        d2.mkdir()
        get_size = MagicMock(side_effect=[500, 300])
        fmt_size = MagicMock(return_value="ok")
        _, total = create_kb_table([d1, d2], get_size, fmt_size)
        assert total == 800

    def test_show_numbers_adds_column(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import create_kb_table
        d = tmp_path / "KB_001"
        d.mkdir()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        table, _ = create_kb_table([d], get_size, fmt_size, show_numbers=True)
        # Should have 4 columns (No., Name, Size, Modified)
        assert len(table.columns) == 4

    def test_no_numbers_has_3_columns(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import create_kb_table
        d = tmp_path / "KB_001"
        d.mkdir()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        table, _ = create_kb_table([d], get_size, fmt_size, show_numbers=False)
        assert len(table.columns) == 3

    def test_empty_list_returns_zero_total(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import create_kb_table
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        _, total = create_kb_table([], get_size, fmt_size)
        assert total == 0


# ===== parse_user_selection() =====

class TestParseUserSelection:
    def test_empty_string_returns_empty(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        assert parse_user_selection("", 5) == []

    def test_single_number(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("1", 5)
        assert result == [0]  # zero-based

    def test_comma_separated(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("1,3,5", 5)
        assert result == [0, 2, 4]

    def test_range_selection(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("1-3", 5)
        assert result == [0, 1, 2]

    def test_range_and_single(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("1-2,4", 5)
        assert result == [0, 1, 3]

    def test_deduplicates(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("1,1,2", 5)
        assert result == [0, 1]

    def test_out_of_bounds_raises(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        with pytest.raises(ValueError):
            parse_user_selection("6", 5)

    def test_range_out_of_bounds_raises(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        with pytest.raises(ValueError):
            parse_user_selection("1-10", 5)

    def test_whitespace_ignored(self):
        from lecture_forge.cli.commands.cleanup_helpers import parse_user_selection
        result = parse_user_selection("  1 , 2 ", 5)
        assert result == [0, 1]


# ===== delete_knowledge_bases() =====

class TestDeleteKnowledgeBases:
    def test_deletes_dirs_and_returns_counts(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import delete_knowledge_bases
        d1 = tmp_path / "KB_001"
        d1.mkdir()
        d2 = tmp_path / "KB_002"
        d2.mkdir()
        console = MagicMock()
        deleted, failed = delete_knowledge_bases([d1, d2], console)
        assert deleted == 2
        assert failed == 0
        assert not d1.exists()
        assert not d2.exists()

    def test_handles_deletion_error(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import delete_knowledge_bases
        d1 = tmp_path / "KB_001"
        d1.mkdir()
        console = MagicMock()
        with patch("shutil.rmtree", side_effect=PermissionError("denied")):
            deleted, failed = delete_knowledge_bases([d1], console)
        assert deleted == 0
        assert failed == 1

    def test_empty_list_returns_zero(self):
        from lecture_forge.cli.commands.cleanup_helpers import delete_knowledge_bases
        console = MagicMock()
        deleted, failed = delete_knowledge_bases([], console)
        assert deleted == 0
        assert failed == 0


# ===== confirm_deletion_all() =====

class TestConfirmDeletionAll:
    def test_returns_true_when_confirmed(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import confirm_deletion_all
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Confirm.ask", return_value=True):
            result = confirm_deletion_all([d], console, get_size, fmt_size)
        assert result is True

    def test_returns_false_when_declined(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import confirm_deletion_all
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Confirm.ask", return_value=False):
            result = confirm_deletion_all([d], console, get_size, fmt_size)
        assert result is False


# ===== interactive_selection() =====

class TestInteractiveSelection:
    def test_empty_input_returns_empty_list(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import interactive_selection
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Prompt.ask", return_value=""):
            result = interactive_selection([d], console, get_size, fmt_size)
        assert result == []

    def test_valid_selection_returns_kbs(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import interactive_selection
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=100)
        fmt_size = MagicMock(return_value="100 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Prompt.ask", return_value="1"):
            with patch("lecture_forge.cli.commands.cleanup_helpers.Confirm.ask", return_value=True):
                result = interactive_selection([d], console, get_size, fmt_size)
        assert result == [d]

    def test_cancel_at_confirm_returns_empty(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import interactive_selection
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=100)
        fmt_size = MagicMock(return_value="100 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Prompt.ask", return_value="1"):
            with patch("lecture_forge.cli.commands.cleanup_helpers.Confirm.ask", return_value=False):
                result = interactive_selection([d], console, get_size, fmt_size)
        assert result == []

    def test_invalid_input_returns_empty(self, tmp_path):
        from lecture_forge.cli.commands.cleanup_helpers import interactive_selection
        d = tmp_path / "KB_001"
        d.mkdir()
        console = MagicMock()
        get_size = MagicMock(return_value=0)
        fmt_size = MagicMock(return_value="0 B")
        with patch("lecture_forge.cli.commands.cleanup_helpers.Prompt.ask", return_value="abc"):
            result = interactive_selection([d], console, get_size, fmt_size)
        assert result == []


# ===== display_cleanup_results() =====

class TestDisplayCleanupResults:
    def test_calls_console_print(self):
        from lecture_forge.cli.commands.cleanup_helpers import display_cleanup_results
        console = MagicMock()
        fmt_size = MagicMock(return_value="1 KB")
        display_cleanup_results(3, 1024, console, fmt_size)
        assert console.print.call_count >= 2

    def test_calls_format_size(self):
        from lecture_forge.cli.commands.cleanup_helpers import display_cleanup_results
        console = MagicMock()
        fmt_size = MagicMock(return_value="1 KB")
        display_cleanup_results(1, 1024, console, fmt_size)
        fmt_size.assert_called_once_with(1024)
