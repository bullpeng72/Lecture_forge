"""
Unit tests for utils/retry.py — make_api_retry decorator.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMakeApiRetry:
    """Tests for make_api_retry decorator."""

    def test_decorator_created_without_error(self):
        from lecture_forge.utils.retry import make_api_retry
        decorator = make_api_retry()
        assert callable(decorator)

    def test_decorator_created_with_service_name(self):
        from lecture_forge.utils.retry import make_api_retry
        decorator = make_api_retry("TestService")
        assert callable(decorator)

    def test_retryable_error_is_retried(self):
        """RuntimeError (retryable) should be retried up to 3 times."""
        from lecture_forge.utils.retry import make_api_retry

        call_count = 0

        @make_api_retry("Test")
        def flaky():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("transient error")

        with pytest.raises(RuntimeError, match="transient error"):
            flaky()

        assert call_count == 3

    def test_authentication_error_not_retried(self):
        """AuthenticationError (401) must NOT be retried."""
        from lecture_forge.utils.retry import make_api_retry

        try:
            from openai import AuthenticationError
        except ImportError:
            pytest.skip("openai package not installed")

        call_count = 0

        @make_api_retry("OpenAI")
        def bad_key():
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 401
            raise AuthenticationError("Invalid API key", response=mock_response, body={})

        with pytest.raises(AuthenticationError):
            bad_key()

        assert call_count == 1, f"AuthenticationError should not be retried, but was called {call_count} times"

    def test_permission_denied_not_retried(self):
        """PermissionDeniedError (403) must NOT be retried."""
        from lecture_forge.utils.retry import make_api_retry

        try:
            from openai import PermissionDeniedError
        except ImportError:
            pytest.skip("openai package not installed")

        call_count = 0

        @make_api_retry("OpenAI")
        def no_permission():
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 403
            raise PermissionDeniedError("Permission denied", response=mock_response, body={})

        with pytest.raises(PermissionDeniedError):
            no_permission()

        assert call_count == 1

    def test_success_on_first_try(self):
        """Successful call returns result without retry."""
        from lecture_forge.utils.retry import make_api_retry

        call_count = 0

        @make_api_retry()
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_success_after_one_retry(self):
        """Retryable error on first attempt succeeds on second."""
        from lecture_forge.utils.retry import make_api_retry

        call_count = 0

        @make_api_retry()
        def succeed_second_time():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temporary network error")
            return "recovered"

        result = succeed_second_time()
        assert result == "recovered"
        assert call_count == 2

    def test_reraise_on_exhausted_retries(self):
        """After 3 failed retries, original exception is re-raised (not RetryError)."""
        from lecture_forge.utils.retry import make_api_retry
        from tenacity import RetryError

        @make_api_retry()
        def always_fails():
            raise ValueError("always bad")

        # With reraise=True, original ValueError should be raised, not RetryError
        with pytest.raises(ValueError, match="always bad"):
            always_fails()
