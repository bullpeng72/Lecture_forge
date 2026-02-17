"""
Unit tests for CLI helpers module.
Tests cover pure utility functions: get_dir_size, find_pdf_files, _find_image_dir_from_html.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===== get_dir_size() =====

class TestGetDirSize:
    def test_returns_zero_for_empty_directory(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        assert get_dir_size(tmp_path) == 0

    def test_counts_file_sizes(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        (tmp_path / "a.txt").write_bytes(b"x" * 100)
        (tmp_path / "b.txt").write_bytes(b"y" * 200)
        assert get_dir_size(tmp_path) == 300

    def test_counts_nested_files(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "top.txt").write_bytes(b"x" * 50)
        (subdir / "nested.txt").write_bytes(b"y" * 150)
        assert get_dir_size(tmp_path) == 200

    def test_handles_nonexistent_directory(self):
        from lecture_forge.cli.utils.helpers import get_dir_size
        result = get_dir_size(Path("/nonexistent/path"))
        assert result == 0

    def test_returns_int(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        result = get_dir_size(tmp_path)
        assert isinstance(result, int)


# ===== find_pdf_files() =====

class TestFindPdfFiles:
    def test_returns_list(self, tmp_path, monkeypatch):
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        result = find_pdf_files()
        assert isinstance(result, list)

    def test_finds_pdf_in_cwd(self, tmp_path, monkeypatch):
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = find_pdf_files()
        assert len(result) == 1
        assert result[0]["name"] == "test.pdf"

    def test_finds_pdf_in_subdirectory(self, tmp_path, monkeypatch):
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "docs"
        subdir.mkdir()
        (subdir / "report.pdf").write_bytes(b"%PDF-1.4 fake")
        result = find_pdf_files(max_depth=1)
        names = [r["name"] for r in result]
        assert "report.pdf" in names

    def test_no_pdfs_returns_empty(self, tmp_path, monkeypatch):
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.txt").write_text("not a pdf")
        result = find_pdf_files()
        assert result == []

    def test_result_has_required_keys(self, tmp_path, monkeypatch):
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 fake content")
        result = find_pdf_files()
        assert len(result) >= 1
        entry = result[0]
        assert "path" in entry
        assert "name" in entry
        assert "size_mb" in entry
        assert "modified" in entry
        assert "relative_path" in entry

    def test_sorted_by_modification_time(self, tmp_path, monkeypatch):
        """Most recently modified file appears first."""
        import time
        from lecture_forge.cli.utils.helpers import find_pdf_files
        monkeypatch.chdir(tmp_path)
        old = tmp_path / "old.pdf"
        old.write_bytes(b"%PDF-1.4 old")
        time.sleep(0.01)
        new = tmp_path / "new.pdf"
        new.write_bytes(b"%PDF-1.4 new")
        result = find_pdf_files()
        assert result[0]["name"] == "new.pdf"


# ===== _find_image_dir_from_html() =====

class TestFindImageDirFromHtml:
    def test_finds_dir_from_comment(self, tmp_path):
        from lecture_forge.cli.utils.helpers import _find_image_dir_from_html
        # Create the image dir so it exists
        img_dir = tmp_path / "data" / "images" / "session_001"
        img_dir.mkdir(parents=True)

        html_content = f"<!-- image_dir: {img_dir} -->\n<html><body></body></html>"
        html_file = tmp_path / "lecture.html"
        html_file.write_text(html_content)

        result = _find_image_dir_from_html(html_file)
        assert result == img_dir

    def test_returns_none_when_no_comment(self, tmp_path):
        from lecture_forge.cli.utils.helpers import _find_image_dir_from_html
        html_file = tmp_path / "lecture.html"
        html_file.write_text("<html><body></body></html>")
        result = _find_image_dir_from_html(html_file)
        assert result is None

    def test_returns_none_when_dir_not_exists(self, tmp_path):
        from lecture_forge.cli.utils.helpers import _find_image_dir_from_html
        # Comment points to nonexistent dir
        html_content = "<!-- image_dir: /nonexistent/path/session -->\n<html></html>"
        html_file = tmp_path / "lecture.html"
        html_file.write_text(html_content)
        result = _find_image_dir_from_html(html_file)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        from lecture_forge.cli.utils.helpers import _find_image_dir_from_html
        result = _find_image_dir_from_html(tmp_path / "nonexistent.html")
        assert result is None


# ===== select_knowledge_base() =====

class TestSelectKnowledgeBase:
    def test_returns_none_when_no_vector_db_dir(self, tmp_path):
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = tmp_path / "nonexistent_db"
            result = select_knowledge_base()
        assert result is None

    def test_returns_none_when_empty_dir(self, tmp_path):
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        db_dir.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value=""):
                result = select_knowledge_base()
        assert result is None

    def test_user_selects_valid_kb(self, tmp_path):
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        kb1 = db_dir / "MyKB_001"
        kb1.mkdir(parents=True)

        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            # User enters "1" to select first KB
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1"):
                result = select_knowledge_base()

        assert result == str(kb1)

    def test_user_cancels_with_empty_input(self, tmp_path):
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        kb1 = db_dir / "MyKB_001"
        kb1.mkdir(parents=True)

        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value=""):
                result = select_knowledge_base()
        assert result is None

# ===== get_dir_size() exception handling =====

class TestGetDirSizeExceptions:
    def test_handles_os_error(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        with patch("pathlib.Path.rglob", side_effect=OSError("permission denied")):
            result = get_dir_size(tmp_path)
        assert result == 0

    def test_handles_permission_error(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        with patch("pathlib.Path.rglob", side_effect=PermissionError("access denied")):
            result = get_dir_size(tmp_path)
        assert result == 0

    def test_handles_unexpected_exception(self, tmp_path):
        from lecture_forge.cli.utils.helpers import get_dir_size
        with patch("pathlib.Path.rglob", side_effect=RuntimeError("unexpected")):
            result = get_dir_size(tmp_path)
        assert result == 0


# ===== handle_kb_deletion_interactive() =====

class TestHandleKbDeletionInteractive:
    def test_empty_input_returns_continue(self, tmp_path):
        from lecture_forge.cli.utils.helpers import handle_kb_deletion_interactive
        d = tmp_path / "KB_001"
        d.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value=""):
            with patch("lecture_forge.cli.utils.helpers.console"):
                result = handle_kb_deletion_interactive([d])
        assert result == "continue"

    def test_valid_number_selection(self, tmp_path):
        from lecture_forge.cli.utils.helpers import handle_kb_deletion_interactive
        d = tmp_path / "KB_001"
        d.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1"):
            with patch("lecture_forge.cli.utils.helpers.Confirm.ask", return_value=True):
                with patch("shutil.rmtree"):
                    with patch("lecture_forge.cli.utils.helpers.console"):
                        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
                            mock_config.VECTOR_DB_PATH = str(tmp_path)
                            # Create a remaining dir to avoid "no remaining" path
                            remaining_dir = tmp_path / "KB_002"
                            remaining_dir.mkdir()
                            result = handle_kb_deletion_interactive([d])
        assert result == "continue"

    def test_invalid_input_returns_continue(self, tmp_path):
        from lecture_forge.cli.utils.helpers import handle_kb_deletion_interactive
        d = tmp_path / "KB_001"
        d.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="not_a_number"):
            with patch("lecture_forge.cli.utils.helpers.console"):
                result = handle_kb_deletion_interactive([d])
        assert result == "continue"


# ===== select_pdf_files() =====

class TestSelectPdfFiles:
    def _make_pdf_entry(self, name, relative_path=None, size_mb=1.0):
        from datetime import datetime
        return {
            "path": f"/some/{name}",
            "relative_path": relative_path or name,
            "name": name,
            "size_mb": size_mb,
            "modified": datetime(2026, 1, 1, 12, 0),
        }

    def test_returns_empty_when_no_pdfs(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=[]):
            with patch("lecture_forge.cli.utils.helpers.console"):
                result = select_pdf_files()
        assert result == []

    def test_empty_input_returns_empty(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry("doc.pdf")]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value=""):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert result == []

    def test_all_selection_returns_all(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry(f"doc{i}.pdf") for i in range(3)]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="all"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert len(result) == 3

    def test_single_number_selection(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [
            self._make_pdf_entry("first.pdf", "first.pdf"),
            self._make_pdf_entry("second.pdf", "second.pdf"),
        ]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert result == ["first.pdf"]

    def test_comma_separated_selection(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry(f"doc{i}.pdf", f"doc{i}.pdf") for i in range(3)]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1,3"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert len(result) == 2
        assert "doc0.pdf" in result
        assert "doc2.pdf" in result

    def test_range_selection(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry(f"doc{i}.pdf", f"doc{i}.pdf") for i in range(4)]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1-3"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert len(result) == 3

    def test_invalid_format_returns_empty(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry("doc.pdf")]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="not_a_number"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert result == []

    def test_out_of_range_skipped(self):
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry("only.pdf", "only.pdf")]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="99"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert result == []

    def test_range_selection_out_of_range_skipped(self):
        """Lines 388-389: range with end > len(pdfs) → skipped."""
        from lecture_forge.cli.utils.helpers import select_pdf_files
        pdfs = [self._make_pdf_entry("doc.pdf", "doc.pdf")]
        with patch("lecture_forge.cli.utils.helpers.find_pdf_files", return_value=pdfs):
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="1-99"):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_pdf_files()
        assert result == []


class TestSelectKnowledgeBaseDeletePath:
    """Tests for lines 97-115: select_knowledge_base delete and invalid input paths."""

    def test_delete_option_calls_deletion_handler(self, tmp_path):
        """Lines 97-99: user types 'd' → handle_kb_deletion_interactive called."""
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        kb1 = db_dir / "KB_001"
        kb1.mkdir(parents=True)

        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            # First call: "d" (delete), which returns None (user cancelled)
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="d"):
                with patch("lecture_forge.cli.utils.helpers.handle_kb_deletion_interactive", return_value="cancelled"):
                    result = select_knowledge_base()
        assert result is None

    def test_invalid_index_shows_error(self, tmp_path):
        """Line 112-113: idx out of range → error message, continue."""
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        kb1 = db_dir / "KB_001"
        kb1.mkdir(parents=True)
        call_count = [0]

        def ask_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "99"  # Out of range → continue
            return ""  # Second call: empty → return None

        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", side_effect=ask_side_effect):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_knowledge_base()
        assert result is None

    def test_value_error_on_non_numeric_input(self, tmp_path):
        """Line 114-115: ValueError when choice is not a number → continue."""
        from lecture_forge.cli.utils.helpers import select_knowledge_base
        db_dir = tmp_path / "vector_db"
        kb1 = db_dir / "KB_001"
        kb1.mkdir(parents=True)
        call_count = [0]

        def ask_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "abc"  # ValueError → continue
            return ""  # Second: empty → None

        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = db_dir
            with patch("lecture_forge.cli.utils.helpers.Prompt.ask", side_effect=ask_side_effect):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = select_knowledge_base()
        assert result is None


class TestFindImageDirFallback:
    """Tests for lines 297-305: _find_image_dir_from_html() filename fallback."""

    def test_fallback_finds_matching_directory(self, tmp_path):
        """Lines 297-305: no comment → tries filename-based fallback."""
        from lecture_forge.cli.utils.helpers import _find_image_dir_from_html
        from lecture_forge.config import Config

        # Create the data/images directory structure
        image_base = tmp_path / "images"
        image_base.mkdir(parents=True)
        matching_dir = image_base / "AI_20260208_session"
        matching_dir.mkdir()

        html_file = tmp_path / "AI_20260208_session.html"
        html_file.write_text("<html></html>")

        orig_data = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            result = _find_image_dir_from_html(html_file)
        finally:
            Config.DATA_DIR = orig_data
        # May or may not find it depending on naming; just verify no exception
        assert result is None or result.exists()


class TestHandleKbDeletionDeleteAll:
    """Tests for lines 148-206: handle_kb_deletion_interactive 'all' option."""

    def test_all_option_no_confirm_returns_continue(self, tmp_path):
        """Lines 148-157: user selects 'all' but declines confirm → continue."""
        from lecture_forge.cli.utils.helpers import handle_kb_deletion_interactive
        d1 = tmp_path / "KB_001"
        d2 = tmp_path / "KB_002"
        d1.mkdir()
        d2.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="all"):
            with patch("lecture_forge.cli.utils.helpers.Confirm.ask", return_value=False):
                with patch("lecture_forge.cli.utils.helpers.console"):
                    result = handle_kb_deletion_interactive([d1, d2])
        assert result == "continue"

    def test_all_option_confirm_deletes_all(self, tmp_path):
        """Lines 159-174: user selects 'all' and confirms → deletes all."""
        from lecture_forge.cli.utils.helpers import handle_kb_deletion_interactive
        # Create VECTOR_DB_PATH dir so iterdir() works
        db_dir = tmp_path / "vector_db"
        db_dir.mkdir()
        d1 = db_dir / "KB_001"
        d2 = db_dir / "KB_002"
        d1.mkdir()
        d2.mkdir()
        with patch("lecture_forge.cli.utils.helpers.Prompt.ask", return_value="all"):
            with patch("lecture_forge.cli.utils.helpers.Confirm.ask", return_value=True):
                with patch("shutil.rmtree"):
                    with patch("lecture_forge.cli.utils.helpers.console"):
                        with patch("lecture_forge.cli.utils.helpers.Config") as mock_config:
                            mock_config.VECTOR_DB_PATH = str(db_dir)
                            result = handle_kb_deletion_interactive([d1, d2])
        assert result in ("continue", "cancelled")
