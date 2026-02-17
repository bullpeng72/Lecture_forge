"""
Unit tests for AsyncWebScraperTool and AsyncSerperSearchTool.
Uses pytest-asyncio with mocked httpx client responses.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx


# ===== AsyncWebScraperTool =====

class TestAsyncWebScraperToolInit:
    def test_default_timeout(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()
        assert tool.timeout == 30.0

    def test_custom_timeout(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool(timeout=10.0)
        assert tool.timeout == 10.0

    def test_headers_set(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()
        assert "User-Agent" in tool.headers


@pytest.mark.asyncio
class TestAsyncWebScraperToolRun:
    """Tests for AsyncWebScraperTool.run()"""

    def _make_response(self, status=200, html="<html><head><title>T</title></head><body><p>Hello</p></body></html>"):
        resp = MagicMock()
        resp.status_code = status
        resp.text = html
        resp.headers = {"content-type": "text/html"}
        resp.raise_for_status = MagicMock()
        return resp

    async def test_run_success(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_resp = self._make_response()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert result["success"] is True
        assert "Hello" in result["text"]
        assert result["metadata"]["url"] == "http://example.com"

    async def test_run_returns_title_in_metadata(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_resp = self._make_response(html="<html><head><title>My Page</title></head><body><p>Content</p></body></html>")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert result["metadata"]["title"] == "My Page"

    async def test_run_timeout_returns_error(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert result["success"] is False
        assert "error" in result

    async def test_run_http_error_returns_error(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = httpx.HTTPStatusError("404", request=mock_request, response=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=http_error)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert result["success"] is False
        assert "error" in result

    async def test_run_generic_exception(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert result["success"] is False
        assert "error" in result

    async def test_run_no_title_tag(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_resp = self._make_response(html="<html><body><p>Content only</p></body></html>")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com/notitle")

        assert result["success"] is True
        assert result["metadata"]["title"] == "No title"

    async def test_run_removes_script_tags(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        mock_resp = self._make_response(
            html="<html><body><script>var x=1;</script><p>Real text</p></body></html>"
        )
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("http://example.com")

        assert "var x" not in result.get("text", "")
        assert "Real text" in result.get("text", "")


@pytest.mark.asyncio
class TestAsyncWebScraperToolRunBatch:
    """Tests for AsyncWebScraperTool.run_batch()"""

    async def test_run_batch_returns_list(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        async def fake_run(url):
            return {"success": True, "text": f"content from {url}", "metadata": {"url": url}}

        with patch.object(tool, "run", side_effect=fake_run):
            results = await tool.run_batch(["http://a.com", "http://b.com"])

        assert isinstance(results, list)
        assert len(results) == 2

    async def test_run_batch_exception_handled(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        call_count = [0]

        async def fake_run(url):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("network error")
            return {"success": True, "text": "ok", "metadata": {}}

        with patch.object(tool, "run", side_effect=fake_run):
            results = await tool.run_batch(["http://fail.com", "http://ok.com"])

        assert len(results) == 2
        # First result should be error dict (from exception handling)
        assert results[0].get("success") is False

    async def test_run_batch_empty_list(self, test_env_vars):
        from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
        tool = AsyncWebScraperTool()

        results = await tool.run_batch([])
        assert results == []


# ===== AsyncSerperSearchTool =====

class TestAsyncSerperSearchToolInit:
    def test_raises_without_api_key(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        from lecture_forge.exceptions import SearchAPIError
        from lecture_forge.config import Config
        original = Config.SERPER_API_KEY
        try:
            Config.SERPER_API_KEY = None
            with pytest.raises(SearchAPIError):
                AsyncSerperSearchTool()
        finally:
            Config.SERPER_API_KEY = original

    def test_initializes_with_api_key(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()
        assert tool.api_key is not None
        assert tool.base_url is not None


@pytest.mark.asyncio
class TestAsyncSerperSearchToolRun:
    """Tests for AsyncSerperSearchTool.run()"""

    def _make_response(self, status=200, data=None):
        if data is None:
            data = {
                "organic": [
                    {"title": "Result 1", "snippet": "Snippet 1", "link": "http://r1.com"},
                    {"title": "Result 2", "snippet": "Snippet 2", "link": "http://r2.com"},
                ]
            }
        resp = MagicMock()
        resp.status_code = status
        resp.json = MagicMock(return_value=data)
        resp.raise_for_status = MagicMock()
        return resp

    async def test_run_success(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_resp = self._make_response()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is True
        assert "results" in result
        assert result["total_results"] >= 1

    async def test_run_extracts_result_fields(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_resp = self._make_response()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        r = result["results"][0]
        assert "title" in r
        assert "snippet" in r
        assert "url" in r

    async def test_run_timeout_returns_error(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is False
        assert result["results"] == []
        assert "error" in result

    async def test_run_http_error_returns_error(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        http_error = httpx.HTTPStatusError("401", request=mock_request, response=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=http_error)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is False
        assert result["results"] == []

    async def test_run_generic_exception(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("unexpected"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is False

    async def test_run_empty_organic_results(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        mock_resp = self._make_response(data={"organic": []})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("obscure query")

        assert result["success"] is True
        assert result["results"] == []
        assert result["total_results"] == 0


@pytest.mark.asyncio
class TestAsyncSerperSearchToolRunBatch:
    """Tests for AsyncSerperSearchTool.run_batch()"""

    async def test_run_batch_returns_list(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        async def fake_run(query, num_results=5):
            return {"success": True, "results": [], "total_results": 0}

        with patch.object(tool, "run", side_effect=fake_run):
            results = await tool.run_batch(["q1", "q2", "q3"])

        assert isinstance(results, list)
        assert len(results) == 3

    async def test_run_batch_exception_handled(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        call_count = [0]

        async def fake_run(query, num_results=5):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API failure")
            return {"success": True, "results": [], "total_results": 0}

        with patch.object(tool, "run", side_effect=fake_run):
            results = await tool.run_batch(["fail", "ok"])

        assert len(results) == 2
        # First result: exception converted to error dict
        assert results[0].get("success") is False
        assert results[0]["results"] == []

    async def test_run_batch_empty_list(self, test_env_vars):
        from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
        tool = AsyncSerperSearchTool()

        results = await tool.run_batch([])
        assert results == []
