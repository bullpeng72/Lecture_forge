"""
Base agent class for common functionality.
"""

from langchain_openai import ChatOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from lecture_forge.config import Config
from lecture_forge.utils import logger
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
        self.model = model or Config.DEFAULT_MODEL
        self.temperature = temperature or Config.TEMPERATURE
        self.llm = self._create_llm()
        self.agent_name = self.__class__.__name__

    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance."""
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            openai_api_key=Config.OPENAI_API_KEY,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"API call failed (attempt {retry_state.attempt_number}/3), retrying..."
        ),
    )
    def invoke_llm(self, prompt: str, phase: str = "unknown"):
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
