"""
Unit tests for AsyncSerperSearchTool.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncSerperSearchToolInit:
    """Tests for AsyncSerperSearchTool initialization."""

    def test_init_with_api_key(self):
        """Initializes successfully when SERPER_API_KEY is set."""
        with patch("lecture_forge.config.Config.SERPER_API_KEY", "test-key-12345"):
            from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
            tool = AsyncSerperSearchTool()
            assert tool.api_key == "test-key-12345"
            assert "google.serper.dev" in tool.base_url

    def test_init_missing_api_key_raises(self):
        """Raises SearchAPIError when SERPER_API_KEY is not set."""
        with patch("lecture_forge.config.Config.SERPER_API_KEY", ""):
            from lecture_forge.exceptions import SearchAPIError
            from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
            with pytest.raises(SearchAPIError):
                AsyncSerperSearchTool()

    def test_headers_contain_api_key(self):
        """Headers include X-API-KEY."""
        with patch("lecture_forge.config.Config.SERPER_API_KEY", "my-secret-key"):
            from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
            tool = AsyncSerperSearchTool()
            assert tool.headers["X-API-KEY"] == "my-secret-key"
            assert tool.headers["Content-Type"] == "application/json"


class TestAsyncSerperSearchToolRun:
    """Tests for AsyncSerperSearchTool.run()."""

    @pytest.fixture
    def tool(self):
        with patch("lecture_forge.config.Config.SERPER_API_KEY", "test-key"):
            from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
            return AsyncSerperSearchTool()

    @pytest.mark.asyncio
    async def test_run_returns_results_on_success(self, tool):
        """Returns parsed results on a successful API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic": [
                {"title": "Result 1", "snippet": "Snippet 1", "link": "https://example.com/1"},
                {"title": "Result 2", "snippet": "Snippet 2", "link": "https://example.com/2"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("Python basics", num_results=2)

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Result 1"
        assert result["results"][0]["url"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_run_handles_timeout(self, tool):
        """Returns error dict on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is False
        assert "Timeout" in result["error"]
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_run_handles_http_error(self, tool):
        """Returns error dict on HTTP error status."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 429
        http_error = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=http_error)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query")

        assert result["success"] is False
        assert "429" in result["error"]

    @pytest.mark.asyncio
    async def test_run_respects_num_results_limit(self, tool):
        """Returns at most num_results items."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic": [
                {"title": f"Result {i}", "snippet": f"Snippet {i}", "link": f"https://example.com/{i}"}
                for i in range(10)
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("test query", num_results=3)

        assert result["success"] is True
        assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_run_empty_organic_returns_empty_list(self, tool):
        """Returns empty results list when API returns no organic results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.run("obscure query")

        assert result["success"] is True
        assert result["results"] == []
        assert result["total_results"] == 0


class TestAsyncSerperSearchToolRunBatch:
    """Tests for AsyncSerperSearchTool.run_batch()."""

    @pytest.fixture
    def tool(self):
        with patch("lecture_forge.config.Config.SERPER_API_KEY", "test-key"):
            from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
            return AsyncSerperSearchTool()

    @pytest.mark.asyncio
    async def test_run_batch_processes_all_queries(self, tool):
        """Processes each query and returns one result per query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"organic": [{"title": "R", "snippet": "S", "link": "https://x.com"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await tool.run_batch(["query1", "query2", "query3"])

        assert len(results) == 3
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_run_batch_handles_partial_failure(self, tool):
        """Converts exceptions to error dicts without failing the whole batch."""
        import httpx

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise httpx.TimeoutException("timeout on second query")
            mock = MagicMock()
            mock.json.return_value = {"organic": [{"title": "R", "snippet": "S", "link": "https://x.com"}]}
            mock.raise_for_status = MagicMock()
            return mock

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = side_effect

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await tool.run_batch(["ok-query", "fail-query", "ok-query2"])

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True
