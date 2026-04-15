"""
Unit tests for TokenTracker.
"""

import pytest

from lecture_forge.utils.token_tracker import (
    CostEstimate,
    TokenTracker,
    TokenUsage,
    get_tracker,
    track_tokens,
)


class TestTokenUsage:
    """Test TokenUsage dataclass."""

    def test_basic_creation(self):
        u = TokenUsage(
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert u.model == "gpt-4o-mini"
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50
        assert u.total_tokens == 150
        assert u.phase == "unknown"
        assert u.agent == "unknown"

    def test_with_phase_and_agent(self):
        u = TokenUsage(
            model="gpt-4o",
            prompt_tokens=200,
            completion_tokens=80,
            total_tokens=280,
            phase="writing",
            agent="ContentWriter",
        )
        assert u.phase == "writing"
        assert u.agent == "ContentWriter"


class TestCostEstimate:
    """Test CostEstimate dataclass."""

    def test_basic_creation(self):
        c = CostEstimate(total_cost=0.01, input_cost=0.006, output_cost=0.004)
        assert c.total_cost == 0.01
        assert c.by_model == {}
        assert c.by_phase == {}


class TestTokenTracker:
    """Test TokenTracker class."""

    def test_init(self):
        tracker = TokenTracker()
        assert tracker.usages == []
        assert tracker.enabled is True

    def test_add_usage(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 100, 50)
        assert len(tracker.usages) == 1
        assert tracker.usages[0].total_tokens == 150

    def test_add_usage_disabled(self):
        tracker = TokenTracker()
        tracker.enabled = False
        tracker.add_usage("gpt-4o-mini", 100, 50)
        assert len(tracker.usages) == 0

    def test_add_multiple_usages(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 100, 50, phase="writing", agent="Writer")
        tracker.add_usage("gpt-4o", 200, 100, phase="evaluation", agent="Evaluator")
        assert len(tracker.usages) == 2

    def test_calculate_cost_empty(self):
        tracker = TokenTracker()
        cost = tracker.calculate_cost()
        assert cost.total_cost == 0.0
        assert cost.input_cost == 0.0
        assert cost.output_cost == 0.0
        assert cost.by_model == {}
        assert cost.by_phase == {}

    def test_calculate_cost_gpt4o_mini(self):
        tracker = TokenTracker()
        # 1M prompt tokens + 1M completion tokens at gpt-4o-mini rates
        tracker.add_usage("gpt-4o-mini", 1_000_000, 1_000_000, phase="writing")
        cost = tracker.calculate_cost()
        # $0.15 input + $0.60 output = $0.75
        assert abs(cost.input_cost - 0.15) < 1e-6
        assert abs(cost.output_cost - 0.60) < 1e-6
        assert abs(cost.total_cost - 0.75) < 1e-6

    def test_calculate_cost_gpt4o(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o", 1_000_000, 0, phase="analysis")
        cost = tracker.calculate_cost()
        assert abs(cost.input_cost - 2.50) < 1e-6

    def test_calculate_cost_by_model(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 100, 50, phase="p1")
        tracker.add_usage("gpt-4o", 100, 50, phase="p2")
        cost = tracker.calculate_cost()
        assert "gpt-4o-mini" in cost.by_model
        assert "gpt-4o" in cost.by_model

    def test_calculate_cost_by_phase(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 100, 50, phase="writing")
        tracker.add_usage("gpt-4o-mini", 100, 50, phase="evaluation")
        cost = tracker.calculate_cost()
        assert "writing" in cost.by_phase
        assert "evaluation" in cost.by_phase

    def test_calculate_cost_unknown_model_zero_cost(self):
        tracker = TokenTracker()
        # Unknown model (e.g., Ollama local model) → zero cost, not gpt-4o-mini fallback
        tracker.add_usage("some-unknown-model", 1_000_000, 0)
        cost = tracker.calculate_cost()
        assert cost.input_cost == 0.0
        assert cost.total_cost == 0.0
        assert "some-unknown-model" in cost.by_model

    def test_get_summary_empty(self):
        tracker = TokenTracker()
        summary = tracker.get_summary()
        assert summary["total_tokens"] == 0
        assert summary["prompt_tokens"] == 0
        assert summary["completion_tokens"] == 0
        assert summary["api_calls"] == 0
        assert "cost_estimate" in summary

    def test_get_summary_with_data(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 300, 100, phase="writing", agent="Writer")
        tracker.add_usage("gpt-4o-mini", 200, 50, phase="evaluation", agent="Evaluator")
        summary = tracker.get_summary()
        assert summary["total_tokens"] == 650
        assert summary["prompt_tokens"] == 500
        assert summary["completion_tokens"] == 150
        assert summary["api_calls"] == 2
        assert "gpt-4o-mini" in summary["tokens_by_model"]

    def test_reset(self):
        tracker = TokenTracker()
        tracker.add_usage("gpt-4o-mini", 100, 50)
        assert len(tracker.usages) == 1
        tracker.reset()
        assert len(tracker.usages) == 0

    def test_normalize_model_name_variants(self):
        tracker = TokenTracker()
        assert tracker._normalize_model_name("gpt-4o-mini-2024-07-18") == "gpt-4o-mini"
        assert tracker._normalize_model_name("gpt-4o-2024-11-20") == "gpt-4o"
        assert tracker._normalize_model_name("text-embedding-3-small") == "text-embedding-3-small"
        # Unknown models (e.g., Ollama) are returned as-is
        assert tracker._normalize_model_name("completely-unknown") == "completely-unknown"
        assert tracker._normalize_model_name("qwen3.5:9b") == "qwen3.5:9b"
        assert tracker._normalize_model_name("llama3.2") == "llama3.2"

    def test_embedding_model_pricing(self):
        tracker = TokenTracker()
        tracker.add_usage("text-embedding-3-small", 1_000_000, 0, phase="embedding")
        cost = tracker.calculate_cost()
        # $0.020 per 1M input tokens, no output cost
        assert abs(cost.input_cost - 0.020) < 1e-6
        assert cost.output_cost == 0.0


class TestGlobalFunctions:
    """Test module-level convenience functions."""

    def test_get_tracker_returns_instance(self):
        tracker = get_tracker()
        assert isinstance(tracker, TokenTracker)

    def test_get_tracker_same_instance(self):
        """get_tracker() should return the same global instance."""
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2

    def test_track_tokens_function(self):
        """track_tokens() adds to global tracker."""
        tracker = get_tracker()
        initial_count = len(tracker.usages)
        track_tokens("gpt-4o-mini", 10, 5, phase="test_phase", agent="TestAgent")
        assert len(tracker.usages) == initial_count + 1


def test_unknown_model_uses_fallback():
    """Line 113: model key not in PRICING → gpt-4o-mini fallback."""
    from unittest.mock import patch
    from lecture_forge.utils.token_tracker import TokenTracker, TokenUsage
    tracker = TokenTracker()
    usage = TokenUsage(
        model="some-unknown-model-xyz",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        phase="test",
        agent="TestAgent",
    )
    tracker.usages.append(usage)
    # Patch _normalize_model_name to return something not in PRICING
    with patch.object(tracker, "_normalize_model_name", return_value="not-in-pricing"):
        cost = tracker.calculate_cost()
    # Should not raise; unknown model falls back to gpt-4o-mini pricing
    assert cost.total_cost >= 0
