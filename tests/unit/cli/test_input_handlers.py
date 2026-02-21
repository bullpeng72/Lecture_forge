"""
Unit tests for CLI input_handlers module.
Tests cover _collect_comma_separated_input.
"""

from unittest.mock import MagicMock, patch

import pytest


# ===== _collect_comma_separated_input() =====

class TestCollectCommaSeparatedInput:
    def test_returns_list_from_comma_input(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value="a, b, c"):
            result = _collect_comma_separated_input(console, "Topics")
        assert result == ["a", "b", "c"]

    def test_empty_input_returns_empty_list(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value=""):
            result = _collect_comma_separated_input(console, "Topics")
        assert result == []

    def test_strips_quotes_from_items(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value='"item1", \'item2\''):
            result = _collect_comma_separated_input(console, "Topics")
        assert "item1" in result
        assert "item2" in result

    def test_hint_is_printed(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value=""):
            _collect_comma_separated_input(console, "Topics", hint="Enter topics separated by commas")
        assert console.print.called

    def test_no_hint_does_not_print(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value=""):
            _collect_comma_separated_input(console, "Topics", hint=None)
        console.print.assert_not_called()

    def test_single_item_returns_single_element_list(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value="machine learning"):
            result = _collect_comma_separated_input(console, "Topics")
        assert result == ["machine learning"]

    def test_strips_whitespace(self):
        from lecture_forge.cli.utils.input_handlers import _collect_comma_separated_input
        console = MagicMock()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", return_value="  topic1  ,  topic2  "):
            result = _collect_comma_separated_input(console, "Topics")
        assert result == ["topic1", "topic2"]


# ===== collect_inputs_interactive() =====

class TestCollectInputsInteractive:
    def _mock_prompts(self, topic="AI", duration="60", audience="intermediate", kb_choice="1",
                      pdf_choice="3", urls="", keywords="", hada="", img=""):
        """Return a side_effect list for Prompt.ask calls."""
        return [topic, duration, audience, kb_choice, pdf_choice, urls, keywords, hada, img]

    def test_returns_dict_with_required_keys(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        values = self._mock_prompts()
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.console"):
                result = collect_inputs_interactive()
        assert "topic" in result
        assert "duration" in result
        assert "audience_level" in result
        assert "pdfs" in result
        assert "urls" in result
        assert "keywords" in result

    def test_pdf_choice_3_returns_empty_pdfs(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        values = self._mock_prompts(pdf_choice="3")
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.console"):
                result = collect_inputs_interactive()
        assert result["pdfs"] == []

    def test_duration_converted_to_int(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        values = self._mock_prompts(duration="120")
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.console"):
                result = collect_inputs_interactive()
        assert result["duration"] == 120
        assert isinstance(result["duration"], int)

    def test_pdf_choice_2_manual_input(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        # pdf_choice="2" triggers manual input (one extra Prompt.ask call for PDFs)
        values = ["AI", "60", "intermediate", "1", "2", "doc1.pdf, doc2.pdf", "", "", "", ""]
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.console"):
                result = collect_inputs_interactive()
        assert len(result["pdfs"]) == 2
        assert "doc1.pdf" in result["pdfs"]

    def test_keywords_parsed_as_list(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        values = ["AI", "60", "beginner", "1", "3", "", "machine learning, deep learning", "", ""]
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.console"):
                result = collect_inputs_interactive()
        assert "machine learning" in result["keywords"]
        assert "deep learning" in result["keywords"]

    def test_pdf_choice_1_calls_select_pdf_files(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        # pdf_choice="1" calls select_pdf_files() then optionally asks to add more
        values = ["AI", "60", "intermediate", "1", "1", "", "", "", ""]
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=values):
            with patch("lecture_forge.cli.utils.input_handlers.select_pdf_files", return_value=[]) as mock_select:
                with patch("lecture_forge.cli.utils.input_handlers.console"):
                    result = collect_inputs_interactive()
        mock_select.assert_called_once()
        assert result["pdfs"] == []
