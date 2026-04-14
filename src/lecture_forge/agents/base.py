"""
Base agent class for common functionality.
"""

import re
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from lecture_forge.config import Config, create_llm
from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry
from lecture_forge.utils.token_tracker import track_tokens


def _strip_think_block(text: str) -> str:
    """Remove <think>...</think> blocks produced by reasoning models (Qwen3, DeepSeek-R1 etc.).

    The thinking content is discarded; only the final answer is returned.
    If no think block is present the original text is returned unchanged.
    """
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return cleaned.strip()


class BaseAgent:
    """Base class for all agents."""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking: Optional[bool] = None,
    ) -> None:
        """
        Initialize base agent.

        Args:
            model: LLM model name (default: Config.DEFAULT_MODEL or Config.OLLAMA_MODEL)
            temperature: Temperature for LLM (default: Config.TEMPERATURE)
            max_tokens: Maximum tokens per LLM response (default: Config.MAX_LLM_TOKENS)
            thinking: Enable/disable Ollama thinking mode.
                      None = use OLLAMA_THINKING config (auto-detect),
                      True = force on, False = force off.
        """
        # Resolve default model based on provider
        if model is None:
            model = Config.OLLAMA_MODEL if Config.LLM_PROVIDER == "ollama" else Config.DEFAULT_MODEL
        self.model = model
        self.temperature = temperature if temperature is not None else Config.TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else Config.MAX_LLM_TOKENS
        self.thinking = thinking
        self.llm = self._create_llm()
        self.agent_name = self.__class__.__name__

    def _create_llm(self) -> BaseChatModel:
        """Create LLM instance based on configured provider."""
        return create_llm(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            thinking=self.thinking,
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

        # Strip <think>...</think> blocks emitted by reasoning models.
        # The block is removed in-place so downstream code sees only the
        # final answer.  Works for Qwen3, DeepSeek-R1, etc.
        if isinstance(getattr(response, "content", None), str) and "<think>" in response.content:
            response.content = _strip_think_block(response.content)
            logger.debug(f"[{self.agent_name}] Stripped <think> block from response")

        # Track token usage — structure differs between OpenAI and Ollama.
        # Priority: LangChain standard usage_metadata (dict with int values)
        #           → OpenAI response_metadata["token_usage"]
        usage_metadata = getattr(response, "usage_metadata", None)
        if isinstance(usage_metadata, dict):
            track_tokens(
                model=self.model,
                prompt_tokens=usage_metadata.get("input_tokens", 0),
                completion_tokens=usage_metadata.get("output_tokens", 0),
                phase=phase,
                agent=self.agent_name,
            )
        elif hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict) and "token_usage" in metadata:
                usage = metadata["token_usage"]
                track_tokens(
                    model=self.model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    phase=phase,
                    agent=self.agent_name,
                )

        return response
