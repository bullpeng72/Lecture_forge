"""
Shared retry decorator factory for external API calls.

Usage:
    from lecture_forge.utils.retry import make_api_retry

    @make_api_retry("Unsplash")
    def run(self, ...):
        ...
"""

import logging

from tenacity import retry, stop_after_attempt, wait_exponential

_logger = logging.getLogger("lecture_forge")


def make_api_retry(service_name: str = ""):
    """
    Create a tenacity retry decorator for external API calls.

    Retries up to 3 times with exponential backoff (2s → 10s).

    Args:
        service_name: Human-readable service label used in warning messages
                      (e.g. "Unsplash", "Pexels", "Search").

    Returns:
        A tenacity ``retry`` decorator ready to be applied to a function.
    """
    prefix = f"{service_name} " if service_name else ""

    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda rs: _logger.warning(
            f"{prefix}API call failed (attempt {rs.attempt_number}/3), retrying..."
        ),
    )
