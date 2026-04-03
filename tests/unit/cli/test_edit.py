"""
Unit tests for edit CLI command.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def lecture_html(tmp_path):
    """A minimal lecture HTML file (not a Reveal.js slides file)."""
    f = tmp_path / "lecture.html"
    f.write_text("<html><body><section>Content</section></body></html>")
    return str(f)


@pytest.fixture
def slides_html(tmp_path):
    """A Reveal.js slides HTML file."""
    f = tmp_path / "slides.html"
    f.write_text('<html><body class="reveal"><div class="slides"></div></body></html>')
    return str(f)


class TestEditCommand:
    def test_slides_file_rejected(self, runner, slides_html):
        from lecture_forge.cli.commands.edit import edit
        result = runner.invoke(edit, [slides_html])
        assert result.exit_code == 0
        assert "슬라이드 파일은 지원되지 않습니다" in result.output

    def test_flask_not_installed(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (_ for _ in ()).throw(ImportError()) if n == "flask" else __import__(n, *a, **k)):
            result = runner.invoke(edit, [lecture_html])
        # Should abort or show error
        assert result.exit_code != 0 or "Flask" in result.output

    def test_successful_launch(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor") as mock_run:
            result = runner.invoke(edit, [lecture_html])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_custom_port(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor") as mock_run:
            result = runner.invoke(edit, [lecture_html, "--port", "8080"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs.get("port") == 8080 or mock_run.call_args[0][2] == 8080

    def test_no_browser_flag(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor") as mock_run:
            result = runner.invoke(edit, [lecture_html, "--no-browser"])
        assert result.exit_code == 0
        call_kwargs = mock_run.call_args
        # open_browser should be False
        args, kwargs = call_kwargs
        open_browser = kwargs.get("open_browser", args[3] if len(args) > 3 else True)
        assert open_browser is False

    def test_port_in_use_error(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor",
                   side_effect=OSError("Address already in use")):
            result = runner.invoke(edit, [lecture_html])
        assert result.exit_code != 0
        assert "이미 사용 중" in result.output

    def test_other_oserror(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor",
                   side_effect=OSError("some other error")):
            result = runner.invoke(edit, [lecture_html])
        assert result.exit_code != 0

    def test_keyboard_interrupt_graceful(self, runner, lecture_html):
        from lecture_forge.cli.commands.edit import edit
        with patch("lecture_forge.editor.server.run_editor",
                   side_effect=KeyboardInterrupt()):
            result = runner.invoke(edit, [lecture_html])
        assert result.exit_code == 0
        assert "종료" in result.output

    def test_output_option_passed(self, runner, lecture_html, tmp_path):
        from lecture_forge.cli.commands.edit import edit
        out = str(tmp_path / "output.html")
        with patch("lecture_forge.editor.server.run_editor") as mock_run:
            result = runner.invoke(edit, [lecture_html, "-o", out])
        assert result.exit_code == 0
        args, kwargs = mock_run.call_args
        output_path = kwargs.get("output_path", args[1] if len(args) > 1 else None)
        assert output_path == out
