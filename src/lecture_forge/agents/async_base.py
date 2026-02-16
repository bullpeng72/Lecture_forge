"""
Async Base Agent - Base class for async agents.

Provides common async functionality and utilities for all async agents.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from lecture_forge.agents.base import BaseAgent
from lecture_forge.utils import logger


class AsyncBaseAgent(BaseAgent):
    """
    Base class for async agents.

    Extends BaseAgent with async-specific functionality including:
    - Thread pool executor for CPU-bound tasks
    - Async context management
    - Rate limiting support
    - Error handling for async operations
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize async base agent.

        Args:
            max_workers: Max threads for CPU-bound tasks (default: CPU count)
        """
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._rate_limiters = {}
        logger.debug(f"Initialized {self.__class__.__name__} with async support")

    async def run_in_executor(
        self, func: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        """
        Run a synchronous function in a thread pool.

        Use this for CPU-bound operations (PDF parsing, image processing, etc.)
        that would block the event loop.

        Args:
            func: Synchronous function to run
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Example:
            result = await self.run_in_executor(
                self._parse_pdf_sync,
                pdf_path
            )
        """
        loop = asyncio.get_event_loop()

        # If kwargs provided, create a partial function
        if kwargs:
            from functools import partial

            func = partial(func, **kwargs)

        return await loop.run_in_executor(self.executor, func, *args)

    async def gather_with_concurrency(
        self, n: int, *tasks, return_exceptions: bool = True
    ) -> list:
        """
        Run tasks with limited concurrency.

        Args:
            n: Maximum number of concurrent tasks
            *tasks: Coroutines to run
            return_exceptions: Whether to return exceptions as results

        Returns:
            List of results

        Example:
            results = await self.gather_with_concurrency(
                3,  # Max 3 concurrent
                *[fetch_url(url) for url in urls]
            )
        """
        semaphore = asyncio.Semaphore(n)

        async def sem_task(task):
            async with semaphore:
                return await task

        return await asyncio.gather(
            *[sem_task(task) for task in tasks], return_exceptions=return_exceptions
        )

    async def retry_async(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        **kwargs,
    ) -> Any:
        """
        Retry an async function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Positional arguments
            max_retries: Maximum number of retries
            delay: Initial delay in seconds
            backoff: Backoff multiplier
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (backoff**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"All {max_retries} attempts failed for {func.__name__}"
                    )

        raise last_exception

    def get_rate_limiter(
        self, name: str, calls_per_minute: int
    ) -> "AsyncRateLimiter":
        """
        Get or create a rate limiter.

        Args:
            name: Unique name for this rate limiter
            calls_per_minute: Maximum calls per minute

        Returns:
            AsyncRateLimiter instance
        """
        if name not in self._rate_limiters:
            self._rate_limiters[name] = AsyncRateLimiter(calls_per_minute)
        return self._rate_limiters[name]

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.executor.shutdown(wait=False)
        return False

    def __del__(self):
        """Cleanup executor on deletion."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


class AsyncRateLimiter:
    """
    Async rate limiter using token bucket algorithm.

    Limits the rate of API calls to prevent hitting rate limits.
    """

    def __init__(self, calls_per_minute: int):
        """
        Initialize rate limiter.

        Args:
            calls_per_minute: Maximum number of calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute  # Seconds between calls
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Acquire permission to make a call.

        Waits if necessary to respect rate limit.
        """
        async with self._lock:
            now = asyncio.get_event_loop().time()
            time_since_last = now - self.last_call

            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self.last_call = asyncio.get_event_loop().time()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        return False
