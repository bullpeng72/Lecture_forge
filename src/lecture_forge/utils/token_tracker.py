"""
Token Usage Tracker for LLM API calls.

Tracks token usage and calculates costs for OpenAI models.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TokenUsage:
    """Token usage for a single API call."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    phase: str = "unknown"
    agent: str = "unknown"


@dataclass
class CostEstimate:
    """Cost estimate for token usage."""

    total_cost: float
    input_cost: float
    output_cost: float
    by_model: Dict[str, float] = field(default_factory=dict)
    by_phase: Dict[str, float] = field(default_factory=dict)


class TokenTracker:
    """Track token usage and calculate costs across lecture generation."""

    # OpenAI Pricing (as of 2026-02-07)
    # https://openai.com/api/pricing/
    PRICING = {
        "gpt-4o-mini": {
            "input": 0.150 / 1_000_000,  # $0.150 per 1M tokens
            "output": 0.600 / 1_000_000,  # $0.600 per 1M tokens
        },
        "gpt-4o": {
            "input": 2.50 / 1_000_000,  # $2.50 per 1M tokens
            "output": 10.00 / 1_000_000,  # $10.00 per 1M tokens
        },
        "gpt-4o-2024-11-20": {  # Alias
            "input": 2.50 / 1_000_000,
            "output": 10.00 / 1_000_000,
        },
        "text-embedding-3-small": {
            "input": 0.020 / 1_000_000,  # $0.020 per 1M tokens
            "output": 0.0,  # Embeddings don't have output tokens
        },
    }

    def __init__(self):
        """Initialize token tracker."""
        self.usages: List[TokenUsage] = []
        self.enabled = True

    def add_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        phase: str = "unknown",
        agent: str = "unknown",
    ) -> None:
        """
        Add token usage record.

        Args:
            model: Model name (e.g., "gpt-4o-mini")
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            phase: Generation phase (e.g., "collection", "writing")
            agent: Agent name (e.g., "ContentWriter")
        """
        if not self.enabled:
            return

        usage = TokenUsage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            phase=phase,
            agent=agent,
        )
        self.usages.append(usage)

    def calculate_cost(self) -> CostEstimate:
        """
        Calculate total cost based on token usage.

        Returns:
            CostEstimate with breakdown by model and phase
        """
        total_input_cost = 0.0
        total_output_cost = 0.0
        by_model: Dict[str, float] = {}
        by_phase: Dict[str, float] = {}

        for usage in self.usages:
            # Normalize model name
            model_key = self._normalize_model_name(usage.model)

            # Get pricing — unknown models (e.g., Ollama local models) are free
            if model_key not in self.PRICING:
                pricing = {"input": 0.0, "output": 0.0}
            else:
                pricing = self.PRICING[model_key]

            # Calculate cost
            input_cost = usage.prompt_tokens * pricing["input"]
            output_cost = usage.completion_tokens * pricing["output"]
            total_cost = input_cost + output_cost

            total_input_cost += input_cost
            total_output_cost += output_cost

            # By model
            if model_key not in by_model:
                by_model[model_key] = 0.0
            by_model[model_key] += total_cost

            # By phase
            if usage.phase not in by_phase:
                by_phase[usage.phase] = 0.0
            by_phase[usage.phase] += total_cost

        return CostEstimate(
            total_cost=total_input_cost + total_output_cost,
            input_cost=total_input_cost,
            output_cost=total_output_cost,
            by_model=by_model,
            by_phase=by_phase,
        )

    def get_summary(self) -> Dict:
        """
        Get usage summary.

        Returns:
            Dictionary with token counts and costs
        """
        cost_estimate = self.calculate_cost()

        # Token counts by model
        tokens_by_model: Dict[str, Dict[str, int]] = {}
        for usage in self.usages:
            model_key = self._normalize_model_name(usage.model)
            if model_key not in tokens_by_model:
                tokens_by_model[model_key] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

            tokens_by_model[model_key]["prompt_tokens"] += usage.prompt_tokens
            tokens_by_model[model_key]["completion_tokens"] += usage.completion_tokens
            tokens_by_model[model_key]["total_tokens"] += usage.total_tokens

        # Total tokens
        total_prompt_tokens = sum(u.prompt_tokens for u in self.usages)
        total_completion_tokens = sum(u.completion_tokens for u in self.usages)
        total_tokens = sum(u.total_tokens for u in self.usages)

        return {
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "tokens_by_model": tokens_by_model,
            "cost_estimate": {
                "total": cost_estimate.total_cost,
                "input": cost_estimate.input_cost,
                "output": cost_estimate.output_cost,
                "by_model": cost_estimate.by_model,
                "by_phase": cost_estimate.by_phase,
            },
            "api_calls": len(self.usages),
        }

    def reset(self) -> None:
        """Reset tracker."""
        self.usages = []

    def _normalize_model_name(self, model: str) -> str:
        """Normalize model name for pricing lookup."""
        model_lower = model.lower()

        if "gpt-4o-mini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower:
            return "gpt-4o"
        elif "text-embedding-3-small" in model_lower:
            return "text-embedding-3-small"
        else:
            # Return original model name for unknown models (e.g., Ollama: qwen3.5:9b, llama3.2)
            return model


# Global tracker instance
_global_tracker = TokenTracker()


def get_tracker() -> TokenTracker:
    """Get global token tracker instance."""
    return _global_tracker


def track_tokens(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    phase: str = "unknown",
    agent: str = "unknown",
) -> None:
    """
    Convenience function to track tokens.

    Args:
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        phase: Generation phase
        agent: Agent name
    """
    _global_tracker.add_usage(model, prompt_tokens, completion_tokens, phase, agent)
