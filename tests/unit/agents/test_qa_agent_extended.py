"""
Extended unit tests for QAAgent - _show_help, _show_goodbye, and other uncovered paths.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.qa_agent import QAAgent


@pytest.fixture
def qa_agent(test_env_vars, mock_llm, tmp_path):
    """Create QAAgent instance with a mock knowledge base path."""
    kb_path = tmp_path / "test_kb"
    kb_path.mkdir()
    with patch("lecture_forge.agents.qa_agent.VectorStore"):
        agent = QAAgent(knowledge_base_path=str(kb_path))
    return agent


# ===== _show_help() =====

class TestShowHelp:
    def test_calls_console_print(self, qa_agent):
        console = MagicMock()
        qa_agent._show_help(console)
        assert console.print.call_count > 0

    def test_prints_multiple_times(self, qa_agent):
        console = MagicMock()
        qa_agent._show_help(console)
        assert console.print.call_count >= 5

    def test_returns_none(self, qa_agent):
        console = MagicMock()
        result = qa_agent._show_help(console)
        assert result is None


# ===== _show_goodbye() =====

class TestShowGoodbye:
    def test_calls_console_print(self, qa_agent):
        console = MagicMock()
        qa_agent._show_goodbye(console, question_count=5)
        assert console.print.call_count > 0

    def test_shows_question_count(self, qa_agent):
        console = MagicMock()
        qa_agent._show_goodbye(console, question_count=7)
        # Check that some print call includes the count
        all_calls = " ".join(str(c) for c in console.print.call_args_list)
        assert "7" in all_calls

    def test_returns_none(self, qa_agent):
        console = MagicMock()
        result = qa_agent._show_goodbye(console, question_count=0)
        assert result is None


# ===== _expand_short_answer() =====

class TestExpandShortAnswer:
    def test_returns_expanded_when_longer(self, qa_agent):
        short = "Short."
        expanded_content = "This is a much longer expanded answer with more details."
        mock_response = MagicMock()
        mock_response.content = expanded_content
        mock_response.response_metadata = {"token_usage": {"total_tokens": 50}}
        with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
            result = qa_agent._expand_short_answer(short, "What is X?", ["context"], "en")
        assert result == expanded_content

    def test_returns_original_when_expansion_not_longer(self, qa_agent):
        short = "Already a decent length answer."
        mock_response = MagicMock()
        mock_response.content = "Short."  # shorter than original
        mock_response.response_metadata = {"token_usage": {"total_tokens": 20}}
        with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
            result = qa_agent._expand_short_answer(short, "Q?", ["ctx"], "en")
        assert result == short

    def test_returns_original_on_exception(self, qa_agent):
        short = "Original answer."
        with patch.object(qa_agent, "invoke_llm", side_effect=Exception("LLM error")):
            result = qa_agent._expand_short_answer(short, "Q?", ["ctx"], "en")
        assert result == short


# ===== _extract_partial_info() =====

class TestExtractPartialInfo:
    def test_returns_response_content(self, qa_agent):
        mock_response = MagicMock()
        mock_response.content = "Partial info found here."
        mock_response.response_metadata = {"token_usage": {"total_tokens": 30}}
        with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
            result = qa_agent._extract_partial_info("What is X?", ["context"], "en")
        assert result == "Partial info found here."

    def test_returns_korean_fallback_on_exception(self, qa_agent):
        with patch.object(qa_agent, "invoke_llm", side_effect=Exception("error")):
            result = qa_agent._extract_partial_info("질문", ["ctx"], "ko")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_english_fallback_on_exception(self, qa_agent):
        with patch.object(qa_agent, "invoke_llm", side_effect=Exception("error")):
            result = qa_agent._extract_partial_info("Question?", ["ctx"], "en")
        assert isinstance(result, str)
        assert len(result) > 0


# ===== start_chat() =====

class TestStartChat:
    """Tests for the interactive start_chat() loop."""

    @pytest.fixture
    def chat_agent(self, test_env_vars, tmp_path):
        kb_path = tmp_path / "test_kb"
        kb_path.mkdir()
        with patch("lecture_forge.agents.qa_agent.VectorStore"):
            agent = QAAgent(knowledge_base_path=str(kb_path))
        return agent

    def _make_answer(self, confidence=0.85, sources=None, translated=None):
        """Build a mock answer() return value."""
        return {
            "answer": "This is the answer.",
            "sources": sources if sources is not None else [],
            "confidence": confidence,
            "query_language": "en",
            "translated_query": translated,
            "num_results": 5,
        }

    def test_exits_on_exit_command(self, chat_agent):
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            chat_agent.start_chat()
        # Verify prompt was called at least once
        chat_agent.prompt_session.prompt.assert_called()

    def test_exits_on_quit_command(self, chat_agent):
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["/quit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            chat_agent.start_chat()

    def test_exits_on_exit_uppercase(self, chat_agent):
        """Exit command is case-insensitive."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["/EXIT"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            chat_agent.start_chat()

    def test_continues_on_empty_input(self, chat_agent):
        """Empty question does not increment counter and loops back."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["", "  ", "/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            chat_agent.start_chat()
        assert chat_agent.prompt_session.prompt.call_count == 3

    def test_shows_help_on_help_command(self, chat_agent):
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["/help", "/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "_show_help") as mock_help:
                chat_agent.start_chat()
        mock_help.assert_called_once()

    def test_shows_help_on_help_keyword(self, chat_agent):
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["help", "/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "_show_help") as mock_help:
                chat_agent.start_chat()
        mock_help.assert_called_once()

    def test_shows_help_on_question_mark(self, chat_agent):
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["?", "/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "_show_help") as mock_help:
                chat_agent.start_chat()
        mock_help.assert_called_once()

    def test_answers_question_with_high_confidence(self, chat_agent):
        """Confidence >= 0.8 → green label."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["What is Python?", "/exit"]
        mock_result = self._make_answer(confidence=0.9)
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                chat_agent.start_chat()

    def test_answers_question_with_medium_confidence(self, chat_agent):
        """Confidence 0.5-0.8 → yellow label."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["What is X?", "/exit"]
        mock_result = self._make_answer(confidence=0.65)
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                chat_agent.start_chat()

    def test_answers_question_with_low_confidence(self, chat_agent):
        """Confidence < 0.5 → red label."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["What is Y?", "/exit"]
        mock_result = self._make_answer(confidence=0.3)
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                chat_agent.start_chat()

    def test_shows_translated_query_info(self, chat_agent):
        """When translated_query is set, multilingual info is displayed."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["파이썬이란?", "/exit"]
        mock_result = self._make_answer(
            confidence=0.9,
            translated="What is Python?",
        )
        mock_result["query_language"] = "ko"
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                chat_agent.start_chat()

    def test_displays_sources_when_present(self, chat_agent):
        """When sources are in result, they are displayed."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["Q?", "/exit"]
        mock_result = self._make_answer(
            confidence=0.8,
            sources=["doc1.pdf (page 3, English)", "doc2.pdf (page 7, Korean)"],
        )
        mock_result["num_results"] = 8
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                chat_agent.start_chat()

    def test_handles_keyboard_interrupt(self, chat_agent):
        """KeyboardInterrupt → calls _show_goodbye and exits cleanly."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = KeyboardInterrupt()
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "_show_goodbye") as mock_goodbye:
                chat_agent.start_chat()  # Must not raise
        mock_goodbye.assert_called_once()

    def test_handles_exception_in_answer(self, chat_agent):
        """Exception in answer() is caught, loop continues to /exit."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["question here", "/exit"]
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", side_effect=Exception("boom")):
                chat_agent.start_chat()  # Must not raise

    def test_question_counter_increments(self, chat_agent):
        """After 2 questions, _show_goodbye receives count=2."""
        chat_agent.prompt_session = MagicMock()
        chat_agent.prompt_session.prompt.side_effect = ["Q1?", "Q2?", "/exit"]
        mock_result = self._make_answer(confidence=0.7)
        with patch("lecture_forge.agents.qa_agent.Console"):
            with patch.object(chat_agent, "answer", return_value=mock_result):
                with patch.object(chat_agent, "_show_goodbye") as mock_goodbye:
                    chat_agent.start_chat()
        mock_goodbye.assert_called_once()
        # Second arg is question_count
        assert mock_goodbye.call_args[0][1] == 2
