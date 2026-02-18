"""
Base agent class for common functionality.
"""

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from lecture_forge.config import Config
from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry
from lecture_forge.utils.token_tracker import track_tokens


class BaseAgent:
    """Base class for all agents."""

    def __init__(self, model: str = None, temperature: float = None):
        """
        Initialize base agent.

        Args:
            model: LLM model name (default: Config.DEFAULT_MODEL)
            temperature: Temperature for LLM (default: Config.TEMPERATURE)
        """
        self.model = model if model is not None else Config.DEFAULT_MODEL
        self.temperature = temperature if temperature is not None else Config.TEMPERATURE
        self.llm = self._create_llm()
        self.agent_name = self.__class__.__name__

    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance."""
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            openai_api_key=Config.OPENAI_API_KEY,
        )

    @make_api_retry()
    def invoke_llm(self, prompt: str, phase: str = "unknown") -> AIMessage:
        """
        Invoke LLM and track token usage with automatic retry on failures.

        Args:
            prompt: Prompt to send to LLM
            phase: Current generation phase

        Returns:
            LLM response
        """
        response = self.llm.invoke(prompt)

        # Track token usage
        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if "token_usage" in metadata:
                usage = metadata["token_usage"]
                track_tokens(
                    model=self.model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    phase=phase,
                    agent=self.agent_name,
                )

        return response
