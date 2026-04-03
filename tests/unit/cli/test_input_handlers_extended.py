"""
Extended unit tests for CLI input_handlers module.
Covers collect_inputs_interactive and prompt_masked_input branches.
"""

from unittest.mock import MagicMock, patch, call

import pytest


class TestCollectInputsInteractive:
    """Tests for collect_inputs_interactive()."""

    def _base_prompts(self, topic="AI", duration="60", level="intermediate",
                      kb_choice="1", pdf_choice="3"):
        """Return a side_effect list for Prompt.ask covering the main flow."""
        return [topic, duration, level, kb_choice, pdf_choice, "", "", "", ""]

    def test_basic_new_kb_no_sources(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["AI Basics", "60", "intermediate", "1", "3", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts):
            result = collect_inputs_interactive()
        assert result["topic"] == "AI Basics"
        assert result["duration"] == 60
        assert result["audience_level"] == "intermediate"
        assert result["pdfs"] == []
        assert result["kb_mode"] == "new"

    def test_reuse_only_kb_skips_sources(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["ML", "90", "beginner", "2"])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts), \
             patch("lecture_forge.cli.utils.helpers.select_knowledge_base",
                   return_value="/some/kb"):
            result = collect_inputs_interactive()
        assert result["kb_mode"] == "reuse_only"
        assert result["pdfs"] == []
        assert result["urls"] == []

    def test_reuse_only_no_kb_selected_falls_back_to_new(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["ML", "90", "beginner", "2", "3", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts), \
             patch("lecture_forge.cli.utils.helpers.select_knowledge_base",
                   return_value=None):
            result = collect_inputs_interactive()
        assert result["kb_mode"] == "new"

    def test_extend_kb_mode(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["DL", "120", "advanced", "3", "3", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts), \
             patch("lecture_forge.cli.utils.helpers.select_knowledge_base",
                   return_value="/some/kb"):
            result = collect_inputs_interactive()
        assert result["kb_mode"] == "extend"

    def test_pdf_choice_2_manual_input(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        # topic, duration, level, kb_choice, pdf_choice, pdf_input, urls, keywords, hada, image
        prompts = iter(["Topic", "60", "intermediate", "1", "2",
                        "file1.pdf, file2.pdf", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts):
            result = collect_inputs_interactive()
        assert "file1.pdf" in result["pdfs"]
        assert "file2.pdf" in result["pdfs"]

    def test_pdf_choice_2_empty_input(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["Topic", "60", "intermediate", "1", "2", "", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts):
            result = collect_inputs_interactive()
        assert result["pdfs"] == []

    def test_pdf_choice_1_browse(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        # topic, duration, level, kb_choice, pdf_choice, urls, keywords, hada, image
        prompts = iter(["Topic", "60", "intermediate", "1", "1", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts), \
             patch("lecture_forge.cli.utils.input_handlers.select_pdf_files",
                   return_value=["a.pdf"]), \
             patch("lecture_forge.cli.utils.input_handlers.Confirm.ask", return_value=False):
            result = collect_inputs_interactive()
        assert result["pdfs"] == ["a.pdf"]

    def test_pdf_choice_1_browse_add_more(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        # topic, duration, level, kb_choice, pdf_choice, extra_pdf, urls, keywords, hada, image
        prompts = iter(["Topic", "60", "intermediate", "1", "1", "extra.pdf", "", "", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts), \
             patch("lecture_forge.cli.utils.input_handlers.select_pdf_files",
                   return_value=["a.pdf"]), \
             patch("lecture_forge.cli.utils.input_handlers.Confirm.ask", return_value=True):
            result = collect_inputs_interactive()
        assert "a.pdf" in result["pdfs"]
        assert "extra.pdf" in result["pdfs"]

    def test_keywords_collected(self):
        from lecture_forge.cli.utils.input_handlers import collect_inputs_interactive
        prompts = iter(["NLP", "60", "intermediate", "1", "3",
                        "https://example.com", "nlp, bert", "", ""])
        with patch("lecture_forge.cli.utils.input_handlers.Prompt.ask", side_effect=prompts):
            result = collect_inputs_interactive()
        assert "https://example.com" in result["urls"]
        assert "nlp" in result["keywords"]
        assert "bert" in result["keywords"]


class TestPromptMaskedInputUnix:
    """Tests for prompt_masked_input on Unix (termios path)."""

    def test_normal_input(self):
        from lecture_forge.cli.utils.input_handlers import prompt_masked_input
        console = MagicMock()
        chars = list("hello") + ["\r"]
        with patch("sys.platform", "linux"), \
             patch("tty.setraw"), \
             patch("termios.tcgetattr", return_value=[]), \
             patch("termios.tcsetattr"), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout") as mock_stdout:
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = chars
            result = prompt_masked_input(console, "Password:")
        assert result == "hello"

    def test_backspace_removes_last_char(self):
        from lecture_forge.cli.utils.input_handlers import prompt_masked_input
        console = MagicMock()
        # type "ab", backspace, enter
        chars = ["a", "b", "\x7f", "\r"]
        with patch("sys.platform", "linux"), \
             patch("tty.setraw"), \
             patch("termios.tcgetattr", return_value=[]), \
             patch("termios.tcsetattr"), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout"):
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = chars
            result = prompt_masked_input(console, "Password:")
        assert result == "a"

    def test_ctrl_c_raises(self):
        from lecture_forge.cli.utils.input_handlers import prompt_masked_input
        console = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("tty.setraw"), \
             patch("termios.tcgetattr", return_value=[]), \
             patch("termios.tcsetattr"), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout"):
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\x03"]
            with pytest.raises(KeyboardInterrupt):
                prompt_masked_input(console, "Password:")

    def test_empty_input_not_allowed(self):
        from lecture_forge.cli.utils.input_handlers import prompt_masked_input
        console = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("tty.setraw"), \
             patch("termios.tcgetattr", return_value=[]), \
             patch("termios.tcsetattr"), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout"):
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\r"]
            result = prompt_masked_input(console, "Password:", allow_empty=False)
        assert result == ""
        console.print.assert_called()  # shows "(Empty input - skipped)"

    def test_allow_empty_no_message(self):
        from lecture_forge.cli.utils.input_handlers import prompt_masked_input
        console = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("tty.setraw"), \
             patch("termios.tcgetattr", return_value=[]), \
             patch("termios.tcsetattr"), \
             patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout"):
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\r"]
            result = prompt_masked_input(console, "Password:", allow_empty=True)
        assert result == ""
        # should NOT print the "(Empty input - skipped)" message
        for c in console.print.call_args_list:
            assert "skipped" not in str(c)
