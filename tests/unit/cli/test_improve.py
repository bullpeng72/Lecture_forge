"""
Unit tests for improve CLI command.
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
    f = tmp_path / "lecture.html"
    f.write_text("<html><body>content</body></html>")
    return str(f)


class TestImproveCommand:
    def test_no_options_shows_hint(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        result = runner.invoke(improve, [lecture_html])
        assert result.exit_code == 0
        assert "No improvement options" in result.output

    def test_with_notes_without_to_slides_warns(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        result = runner.invoke(improve, [lecture_html, "--with-notes"])
        assert result.exit_code == 0
        assert "--with-notes requires --to-slides" in result.output

    def test_to_slides_success(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_converter = MagicMock()
        mock_converter.convert.return_value = True
        with patch("lecture_forge.cli.commands.improve.SlideConverter",
                   return_value=mock_converter):
            result = runner.invoke(improve, [lecture_html, "--to-slides"])
        assert result.exit_code == 0
        assert "Slides created" in result.output

    def test_to_slides_failure(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_converter = MagicMock()
        mock_converter.convert.return_value = False
        with patch("lecture_forge.cli.commands.improve.SlideConverter",
                   return_value=mock_converter):
            result = runner.invoke(improve, [lecture_html, "--to-slides"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()

    def test_to_slides_with_notes(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_converter = MagicMock()
        mock_converter.convert.return_value = True
        with patch("lecture_forge.cli.commands.improve.SlideConverter",
                   return_value=mock_converter):
            result = runner.invoke(improve, [lecture_html, "--to-slides", "--with-notes"])
        assert result.exit_code == 0
        mock_converter.convert.assert_called_once_with(
            Path(lecture_html), Path(lecture_html).parent / f"{Path(lecture_html).stem}_slides.html",
            with_notes=True
        )
        assert "발표자 노트" in result.output

    def test_re_evaluate_success(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_enhancer = MagicMock()
        mock_enhancer.enhance.return_value = "/tmp/lecture_enhanced.html"
        with patch("lecture_forge.agents.content_enhancer.ContentEnhancer",
                   return_value=mock_enhancer):
            result = runner.invoke(improve, [lecture_html, "--re-evaluate"])
        assert result.exit_code == 0

    def test_re_evaluate_failure_returns_none(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_enhancer = MagicMock()
        mock_enhancer.enhance.return_value = None
        with patch("lecture_forge.agents.content_enhancer.ContentEnhancer",
                   return_value=mock_enhancer):
            result = runner.invoke(improve, [lecture_html, "--re-evaluate"])
        assert result.exit_code == 0
        assert "실패" in result.output

    def test_re_evaluate_with_kb_path(self, runner, lecture_html, tmp_path):
        from lecture_forge.cli.commands.improve import improve
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        mock_enhancer = MagicMock()
        mock_enhancer.enhance.return_value = str(tmp_path / "out_enhanced.html")
        with patch("lecture_forge.agents.content_enhancer.ContentEnhancer",
                   return_value=mock_enhancer):
            result = runner.invoke(improve, [lecture_html, "--re-evaluate", "--kb", str(kb_dir)])
        assert result.exit_code == 0
        _, kwargs = mock_enhancer.enhance.call_args
        assert kwargs.get("kb_path") == str(kb_dir)

    def test_quality_level_strict(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_enhancer = MagicMock()
        mock_enhancer.enhance.return_value = "enhanced.html"
        with patch("lecture_forge.agents.content_enhancer.ContentEnhancer",
                   return_value=mock_enhancer):
            result = runner.invoke(improve, [lecture_html, "--re-evaluate", "--quality-level", "strict"])
        assert result.exit_code == 0
        _, kwargs = mock_enhancer.enhance.call_args
        assert kwargs.get("quality_level") == "strict"

    def test_re_evaluate_and_to_slides_together(self, runner, lecture_html):
        from lecture_forge.cli.commands.improve import improve
        mock_enhancer = MagicMock()
        mock_enhancer.enhance.return_value = "enhanced.html"
        mock_converter = MagicMock()
        mock_converter.convert.return_value = True
        with patch("lecture_forge.agents.content_enhancer.ContentEnhancer",
                   return_value=mock_enhancer), \
             patch("lecture_forge.cli.commands.improve.SlideConverter",
                   return_value=mock_converter):
            result = runner.invoke(improve, [lecture_html, "--re-evaluate", "--to-slides"])
        assert result.exit_code == 0
        mock_enhancer.enhance.assert_called_once()
        mock_converter.convert.assert_called_once()
