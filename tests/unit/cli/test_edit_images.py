"""
Unit tests for edit_images CLI command and its helpers.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def lecture_html(tmp_path):
    f = tmp_path / "lecture.html"
    f.write_text("<html><body><section>Content</section></body></html>")
    return str(f)


@pytest.fixture
def slides_html(tmp_path):
    f = tmp_path / "slides.html"
    f.write_text('<html><body class="reveal"><div class="slides"></div></body></html>')
    return str(f)


def _make_mock_editor(images=None, diagrams=None):
    editor = MagicMock()
    editor.images = images or [{"id": "img1", "url": "x"}]
    editor.diagrams = diagrams or []
    editor.list_elements.return_value = [
        {
            "display_index": 1,
            "kind": "image",
            "img_index": 0,
            "section": "Intro",
            "title": "Figure 1",
            "extra": "page 1",
            "status": "keep",
        }
    ]
    editor.get_summary.return_value = {
        "to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0
    }
    return editor


# ──────────────────────────────────────────────────────────────────────────────
# Slides rejection
# ──────────────────────────────────────────────────────────────────────────────

class TestEditImagesCommand:
    def test_slides_file_rejected(self, runner, slides_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        result = runner.invoke(edit_images, [slides_html])
        assert result.exit_code == 0
        assert "슬라이드 파일은 지원되지 않습니다" in result.output

    def test_quit_immediately_no_changes(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   return_value="q"):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_quit_with_changes_confirmed(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.get_summary.return_value = {
            "to_delete": 1, "to_replace": 0, "diagrams_to_delete": 0
        }
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   return_value="/quit"), \
             patch("lecture_forge.cli.commands.edit_images.Confirm.ask",
                   return_value=True):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_quit_with_changes_cancelled(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.get_summary.side_effect = [
            {"to_delete": 1, "to_replace": 0, "diagrams_to_delete": 0},
            {"to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0},
        ]
        prompts = iter(["/exit", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts), \
             patch("lecture_forge.cli.commands.edit_images.Confirm.ask",
                   return_value=False):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_empty_command_continues(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_help_command(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["h", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_unknown_command_shows_hint(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["xyz", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_delete_valid_image(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.mark_delete.return_value = True
        prompts = iter(["d 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.mark_delete.assert_called_once_with(0)

    def test_delete_fails(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.mark_delete.return_value = False
        prompts = iter(["d 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_delete_invalid_number(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["d 99", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_delete_non_numeric_arg(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["d abc", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_delete_no_arg(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["d", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_delete_diagram(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = MagicMock()
        mock_editor.images = []
        mock_editor.diagrams = [{"id": "dgm1"}]
        mock_editor.list_elements.return_value = [
            {
                "display_index": 1,
                "kind": "diagram",
                "dgm_index": 0,
                "section": "Intro",
                "title": "Flow",
                "extra": "",
                "status": "keep",
            }
        ]
        mock_editor.get_summary.return_value = {
            "to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0
        }
        mock_editor.mark_delete_diagram.return_value = True
        prompts = iter(["d 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.mark_delete_diagram.assert_called_once_with(0)

    def test_undo_image(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.unmark_delete.return_value = True
        prompts = iter(["u 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.unmark_delete.assert_called_once_with(0)

    def test_undo_image_not_marked(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.unmark_delete.return_value = False
        prompts = iter(["u 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_undo_no_arg(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["u", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_undo_non_numeric(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["u abc", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_undo_diagram(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = MagicMock()
        mock_editor.images = []
        mock_editor.diagrams = [{}]
        mock_editor.list_elements.return_value = [
            {"display_index": 1, "kind": "diagram", "dgm_index": 0,
             "section": "S", "title": "D", "extra": "", "status": "delete"}
        ]
        mock_editor.get_summary.return_value = {
            "to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0
        }
        mock_editor.unmark_delete_diagram.return_value = True
        prompts = iter(["u 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.unmark_delete_diagram.assert_called_once_with(0)

    def test_replace_no_arg(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["r", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_replace_invalid_number(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["r 99", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_replace_non_numeric(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["r abc", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_replace_diagram_shows_warning(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = MagicMock()
        mock_editor.images = []
        mock_editor.diagrams = [{}]
        mock_editor.list_elements.return_value = [
            {"display_index": 1, "kind": "diagram", "dgm_index": 0,
             "section": "S", "title": "D", "extra": "", "status": "keep"}
        ]
        mock_editor.get_summary.return_value = {
            "to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0
        }
        prompts = iter(["r 1", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_save_no_changes(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        prompts = iter(["s"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0

    def test_save_with_changes_confirmed(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.get_summary.return_value = {
            "to_delete": 1, "to_replace": 1, "diagrams_to_delete": 1
        }
        mock_editor.save_changes.return_value = "/tmp/out.html"
        prompts = iter(["s"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts), \
             patch("lecture_forge.cli.commands.edit_images.Confirm.ask",
                   return_value=True):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.save_changes.assert_called_once()

    def test_save_with_changes_cancelled(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        mock_editor = _make_mock_editor()
        mock_editor.get_summary.return_value = {
            "to_delete": 1, "to_replace": 0, "diagrams_to_delete": 0
        }
        prompts = iter(["s", "q"])
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   return_value=mock_editor), \
             patch("lecture_forge.cli.commands.edit_images.Prompt.ask",
                   side_effect=prompts), \
             patch("lecture_forge.cli.commands.edit_images.Confirm.ask",
                   return_value=False):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code == 0
        mock_editor.save_changes.assert_not_called()

    def test_image_editor_exception_aborts(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit_images import edit_images
        with patch("lecture_forge.tools.image_editor.ImageEditor",
                   side_effect=RuntimeError("failed")):
            result = runner.invoke(edit_images, [lecture_html])
        assert result.exit_code != 0


# ──────────────────────────────────────────────────────────────────────────────
# _handle_replace_image
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleReplaceImage:
    def test_no_alternatives(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = []
        _handle_replace_image(console, editor, 0)
        console.print.assert_called()

    def test_cancel_selection(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = [
            {"index": 1, "description": "a pic", "page": 1, "source": "pdf"}
        ]
        with patch("lecture_forge.cli.commands.edit_images.Prompt.ask", return_value="0"):
            _handle_replace_image(console, editor, 0)
        editor.replace_image.assert_not_called()

    def test_valid_selection_success(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = [
            {"index": 1, "description": "a nice pic", "page": 2,
             "source": "pdf", "path": "/tmp/a.jpg"}
        ]
        editor.replace_image.return_value = True
        with patch("lecture_forge.cli.commands.edit_images.Prompt.ask", return_value="1"):
            _handle_replace_image(console, editor, 0)
        editor.replace_image.assert_called_once_with(0, "/tmp/a.jpg")

    def test_valid_selection_fail(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = [
            {"index": 1, "description": "pic", "page": None,
             "source": "pdf", "path": "/tmp/a.jpg"}
        ]
        editor.replace_image.return_value = False
        with patch("lecture_forge.cli.commands.edit_images.Prompt.ask", return_value="1"):
            _handle_replace_image(console, editor, 0)
        editor.replace_image.assert_called_once()

    def test_out_of_range_selection(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = [
            {"index": 1, "description": "pic", "page": 1,
             "source": "pdf", "path": "/tmp/a.jpg"}
        ]
        with patch("lecture_forge.cli.commands.edit_images.Prompt.ask", return_value="99"):
            _handle_replace_image(console, editor, 0)
        editor.replace_image.assert_not_called()

    def test_non_numeric_selection(self):
        from lecture_forge.cli.commands.edit_images import _handle_replace_image
        console = MagicMock()
        editor = MagicMock()
        editor.find_alternative_images.return_value = [
            {"index": 1, "description": "pic", "page": 1,
             "source": "pdf", "path": "/tmp/a.jpg"}
        ]
        with patch("lecture_forge.cli.commands.edit_images.Prompt.ask", return_value="abc"):
            _handle_replace_image(console, editor, 0)
        editor.replace_image.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# _handle_save_changes
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleSaveChanges:
    def test_no_changes_returns_early(self):
        from lecture_forge.cli.commands.edit_images import _handle_save_changes
        console = MagicMock()
        editor = MagicMock()
        editor.get_summary.return_value = {
            "to_delete": 0, "to_replace": 0, "diagrams_to_delete": 0
        }
        _handle_save_changes(console, editor, None)
        editor.save_changes.assert_not_called()

    def test_save_success(self):
        from lecture_forge.cli.commands.edit_images import _handle_save_changes
        console = MagicMock()
        editor = MagicMock()
        editor.get_summary.return_value = {
            "to_delete": 2, "to_replace": 1, "diagrams_to_delete": 0
        }
        editor.save_changes.return_value = "/out/file.html"
        with patch("lecture_forge.cli.commands.edit_images.Confirm.ask", return_value=True):
            _handle_save_changes(console, editor, "/out/file.html")
        editor.save_changes.assert_called_once_with("/out/file.html")

    def test_save_exception_propagates(self):
        from lecture_forge.cli.commands.edit_images import _handle_save_changes
        console = MagicMock()
        editor = MagicMock()
        editor.get_summary.return_value = {
            "to_delete": 1, "to_replace": 0, "diagrams_to_delete": 0
        }
        editor.save_changes.side_effect = IOError("disk full")
        with patch("lecture_forge.cli.commands.edit_images.Confirm.ask", return_value=True):
            with pytest.raises(IOError):
                _handle_save_changes(console, editor, None)
