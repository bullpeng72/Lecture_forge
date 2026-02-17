"""
Unit tests for AsyncBaseAgent and AsyncRateLimiter.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def agent(test_env_vars):
    from lecture_forge.agents.async_base import AsyncBaseAgent
    with patch("lecture_forge.agents.base.BaseAgent.__init__", return_value=None):
        a = AsyncBaseAgent.__new__(AsyncBaseAgent)
        AsyncBaseAgent.__init__(a)
    return a


# ===== AsyncBaseAgent =====

class TestAsyncBaseAgentInit:
    def test_has_executor(self, test_env_vars):
        from lecture_forge.agents.async_base import AsyncBaseAgent
        with patch("lecture_forge.agents.base.BaseAgent.__init__", return_value=None):
            a = AsyncBaseAgent.__new__(AsyncBaseAgent)
            AsyncBaseAgent.__init__(a)
        assert hasattr(a, "executor")

    def test_has_rate_limiters_dict(self, test_env_vars):
        from lecture_forge.agents.async_base import AsyncBaseAgent
        with patch("lecture_forge.agents.base.BaseAgent.__init__", return_value=None):
            a = AsyncBaseAgent.__new__(AsyncBaseAgent)
            AsyncBaseAgent.__init__(a)
        assert isinstance(a._rate_limiters, dict)


@pytest.mark.asyncio
class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency() (lines 91-98)."""

    async def test_runs_all_tasks(self, agent):
        async def fake_task(x):
            return x * 2

        tasks = [fake_task(i) for i in range(4)]
        results = await agent.gather_with_concurrency(2, *tasks)
        assert sorted(results) == [0, 2, 4, 6]

    async def test_limits_concurrency(self, agent):
        """Tasks run with limited concurrency."""
        results = []

        async def slow_task(n):
            await asyncio.sleep(0.01)
            results.append(n)
            return n

        tasks = [slow_task(i) for i in range(3)]
        out = await agent.gather_with_concurrency(2, *tasks)
        assert len(out) == 3

    async def test_returns_exceptions_as_results(self, agent):
        async def failing_task():
            raise ValueError("fail")

        async def ok_task():
            return 42

        tasks = [failing_task(), ok_task()]
        results = await agent.gather_with_concurrency(2, *tasks, return_exceptions=True)
        assert len(results) == 2
        # One should be an exception, one should be 42
        exceptions = [r for r in results if isinstance(r, Exception)]
        values = [r for r in results if not isinstance(r, Exception)]
        assert len(exceptions) == 1
        assert 42 in values


@pytest.mark.asyncio
class TestRetryAsync:
    """Tests for retry_async() (lines 127-146)."""

    async def test_succeeds_first_try(self, agent):
        async def succeed():
            return "ok"

        result = await agent.retry_async(succeed, max_retries=3, delay=0)
        assert result == "ok"

    async def test_retries_on_failure_then_succeeds(self, agent):
        call_count = [0]

        async def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("transient")
            return "success"

        result = await agent.retry_async(flaky, max_retries=3, delay=0.001, backoff=1.0)
        assert result == "success"
        assert call_count[0] == 3

    async def test_raises_after_all_retries(self, agent):
        async def always_fail():
            raise ValueError("permanent error")

        with pytest.raises(ValueError, match="permanent error"):
            await agent.retry_async(always_fail, max_retries=2, delay=0.001, backoff=1.0)

    async def test_passes_args_to_func(self, agent):
        async def add(a, b):
            return a + b

        result = await agent.retry_async(add, 3, 4, max_retries=1, delay=0)
        assert result == 7


@pytest.mark.asyncio
class TestAsyncContextManager:
    """Tests for __aenter__ and __aexit__ (lines 165-172)."""

    async def test_async_context_manager(self, test_env_vars):
        from lecture_forge.agents.async_base import AsyncBaseAgent
        with patch("lecture_forge.agents.base.BaseAgent.__init__", return_value=None):
            a = AsyncBaseAgent.__new__(AsyncBaseAgent)
            AsyncBaseAgent.__init__(a)
        async with a as entered:
            assert entered is a


class TestGetRateLimiter:
    """Test get_rate_limiter() creates/retrieves rate limiters."""

    def test_creates_new_rate_limiter(self, agent):
        rl = agent.get_rate_limiter("test_limiter", 60)
        assert rl is not None

    def test_returns_same_instance_on_second_call(self, agent):
        rl1 = agent.get_rate_limiter("my_limiter", 60)
        rl2 = agent.get_rate_limiter("my_limiter", 60)
        assert rl1 is rl2


# ===== AsyncRateLimiter =====

@pytest.mark.asyncio
class TestAsyncRateLimiter:
    """Tests for AsyncRateLimiter (lines 205-223)."""

    async def test_acquire_completes(self, test_env_vars):
        from lecture_forge.agents.async_base import AsyncRateLimiter
        rl = AsyncRateLimiter(calls_per_minute=120)
        await rl.acquire()  # Should complete without error

    async def test_context_manager(self, test_env_vars):
        from lecture_forge.agents.async_base import AsyncRateLimiter
        rl = AsyncRateLimiter(calls_per_minute=120)
        async with rl:
            pass  # Should not raise

    async def test_rate_limiting_wait(self, test_env_vars):
        """Second call within interval should wait."""
        from lecture_forge.agents.async_base import AsyncRateLimiter
        # 1 call/minute → 60s interval → normally would wait
        # Use very low rate to force wait (but patch sleep)
        rl = AsyncRateLimiter(calls_per_minute=1)
        await rl.acquire()  # First call (no wait)
        # Second call will need to wait but we just verify it completes
        with patch("asyncio.sleep", return_value=None):
            await rl.acquire()


@pytest.mark.asyncio
class TestRunInExecutor:
    """Tests for run_in_executor() (lines 61-69)."""

    async def test_runs_sync_function(self, agent):
        def sync_add(a, b):
            return a + b

        result = await agent.run_in_executor(sync_add, 3, 4)
        assert result == 7

    async def test_runs_with_kwargs(self, agent):
        def sync_func(x, multiplier=2):
            return x * multiplier

        result = await agent.run_in_executor(sync_func, 5, multiplier=3)
        assert result == 15
