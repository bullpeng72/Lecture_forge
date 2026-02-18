"""
Unit tests for AsyncWebScraperTool.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncWebScraperToolInit:
    """Tests for AsyncWebScraperTool initialization."""

    def test_init_default_timeout(self):
        """Initializes with default timeout of 30.0 seconds."""
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()
        assert tool.timeout == 30.0

    def test_init_custom_timeout(self):
        """Initializes with custom timeout."""
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool(timeout=10.0)
        assert tool.timeout == 10.0

    def test_headers_contain_user_agent(self):
        """Headers include a User-Agent string."""
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()
        assert "User-Agent" in tool.headers
        assert "LectureForge" in tool.headers["User-Agent"]


class TestAsyncWebScraperToolRun:
    """Tests for AsyncWebScraperTool.run()."""

    @pytest.fixture
    def tool(self):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        return AsyncWebScraperTool()

    def _make_mock_response(self, html: str, status_code: int = 200,
                            content_type: str = "text/html"):
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = status_code
        mock_response.headers = {"content-type": content_type}
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_run_returns_text_on_success(self, tool):
        """Returns parsed text content on a successful response."""
        html = "<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"
        mock_response = self._make_mock_response(html)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com")

        assert result["success"] is True
        assert "Hello world" in result["text"]

    @pytest.mark.asyncio
    async def test_run_includes_metadata(self, tool):
        """Result includes URL, title, status_code, and content_type metadata."""
        html = "<html><head><title>My Title</title></head><body><p>Content</p></body></html>"
        mock_response = self._make_mock_response(html, status_code=200,
                                                  content_type="text/html; charset=utf-8")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com/page")

        assert result["success"] is True
        assert result["metadata"]["url"] == "https://example.com/page"
        assert result["metadata"]["title"] == "My Title"
        assert result["metadata"]["status_code"] == 200
        assert "text/html" in result["metadata"]["content_type"]

    @pytest.mark.asyncio
    async def test_run_strips_script_and_style(self, tool):
        """Script, style, nav, and footer elements are removed from the text."""
        html = (
            "<html><body>"
            "<script>alert('xss')</script>"
            "<style>.foo { color: red }</style>"
            "<nav>Navigation</nav>"
            "<p>Main content here</p>"
            "<footer>Footer text</footer>"
            "</body></html>"
        )
        mock_response = self._make_mock_response(html)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com")

        assert result["success"] is True
        assert "alert" not in result["text"]
        assert "color: red" not in result["text"]
        assert "Main content here" in result["text"]

    @pytest.mark.asyncio
    async def test_run_handles_missing_title(self, tool):
        """Falls back to 'No title' when the page has no <title> tag."""
        html = "<html><body><p>No title page</p></body></html>"
        mock_response = self._make_mock_response(html)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com")

        assert result["success"] is True
        assert result["metadata"]["title"] == "No title"

    @pytest.mark.asyncio
    async def test_run_handles_timeout(self, tool):
        """Returns error dict on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com")

        assert result["success"] is False
        assert "Timeout" in result["error"] or "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_run_handles_http_error(self, tool):
        """Returns error dict on HTTP error status."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = httpx.HTTPStatusError(
            "not found", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=http_error)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com/missing")

        assert result["success"] is False
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_run_handles_generic_exception(self, tool):
        """Returns error dict on unexpected exceptions."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("https://example.com")

        assert result["success"] is False
        assert "error" in result


class TestAsyncWebScraperToolRunBatch:
    """Tests for AsyncWebScraperTool.run_batch()."""

    @pytest.fixture
    def tool(self):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        return AsyncWebScraperTool()

    @pytest.mark.asyncio
    async def test_run_batch_returns_one_result_per_url(self, tool):
        """Returns exactly one result dict per input URL."""
        html = "<html><head><title>T</title></head><body><p>Content</p></body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await tool.run_batch(urls)

        assert len(results) == 3
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_run_batch_handles_partial_failure(self, tool):
        """Converts exceptions to error dicts without failing the whole batch."""
        import httpx

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "fail" in url:
                raise httpx.TimeoutException("timeout")
            mock = MagicMock()
            mock.text = "<html><head><title>T</title></head><body><p>OK</p></body></html>"
            mock.status_code = 200
            mock.headers = {"content-type": "text/html"}
            mock.raise_for_status = MagicMock()
            return mock

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get

        urls = [
            "https://example.com/ok1",
            "https://example.com/fail",
            "https://example.com/ok2",
        ]

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await tool.run_batch(urls)

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_run_batch_empty_list(self, tool):
        """Returns empty list for empty input."""
        results = await tool.run_batch([])
        assert results == []
