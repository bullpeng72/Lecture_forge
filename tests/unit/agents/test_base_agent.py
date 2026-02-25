"""
Unit tests for BaseAgent.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


@pytest.fixture(autouse=True)
def set_env(test_env_vars):
    """Ensure env vars are set for all tests in this module."""
    pass


# ===== BaseAgent.__init__ =====

class TestBaseAgentInit:
    def test_default_model_from_config(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        from lecture_forge.config import Config
        agent = BaseAgent()
        assert agent.model == Config.DEFAULT_MODEL

    def test_default_temperature_from_config(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        from lecture_forge.config import Config
        agent = BaseAgent()
        assert agent.temperature == Config.TEMPERATURE

    def test_custom_model_override(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        agent = BaseAgent(model="gpt-4o")
        assert agent.model == "gpt-4o"

    def test_custom_temperature_override(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        agent = BaseAgent(temperature=0.0)
        assert agent.temperature == 0.0

    def test_agent_name_is_class_name(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        agent = BaseAgent()
        assert agent.agent_name == "BaseAgent"

    def test_subclass_agent_name(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent

        class MySpecialAgent(BaseAgent):
            pass

        agent = MySpecialAgent()
        assert agent.agent_name == "MySpecialAgent"

    def test_llm_is_created(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        agent = BaseAgent()
        assert agent.llm is not None


# ===== BaseAgent.invoke_llm =====

class TestBaseAgentInvokeLlm:
    def _make_ai_message(self, content: str = "test response") -> AIMessage:
        msg = AIMessage(content=content)
        msg.response_metadata = {
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }
        }
        return msg

    def test_returns_ai_message(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        mock_llm.invoke.return_value = self._make_ai_message("hello")
        agent = BaseAgent()
        result = agent.invoke_llm("What is AI?", phase="test")
        assert isinstance(result, AIMessage)

    def test_calls_llm_invoke_with_prompt(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        mock_llm.invoke.return_value = self._make_ai_message()
        agent = BaseAgent()
        agent.invoke_llm("my prompt", phase="test")
        mock_llm.invoke.assert_called_once_with("my prompt")

    def test_tracks_tokens_when_metadata_present(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        mock_llm.invoke.return_value = self._make_ai_message()
        with patch("lecture_forge.agents.base.track_tokens") as mock_track:
            agent = BaseAgent()
            agent.invoke_llm("prompt", phase="writing")
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args
            assert call_kwargs.kwargs.get("phase") == "writing" or call_kwargs.args[3] == "writing"

    def test_no_track_when_no_metadata(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        msg = AIMessage(content="no metadata")
        mock_llm.invoke.return_value = msg
        with patch("lecture_forge.agents.base.track_tokens") as mock_track:
            agent = BaseAgent()
            agent.invoke_llm("prompt", phase="test")
            mock_track.assert_not_called()

    def test_default_phase_is_unknown(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        mock_llm.invoke.return_value = self._make_ai_message()
        with patch("lecture_forge.agents.base.track_tokens") as mock_track:
            agent = BaseAgent()
            agent.invoke_llm("prompt")
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args
            # phase should be "unknown" (default)
            assert "unknown" in str(call_kwargs)

    def test_returns_content_string(self, mock_llm):
        from lecture_forge.agents.base import BaseAgent
        mock_llm.invoke.return_value = self._make_ai_message("response text")
        agent = BaseAgent()
        result = agent.invoke_llm("prompt")
        assert result.content == "response text"
