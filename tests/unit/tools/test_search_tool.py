"""
Unit tests for SerperSearchTool.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from lecture_forge.tools.search_tool import SerperSearchTool


@pytest.fixture
def search_tool(test_env_vars):
    return SerperSearchTool()


def test_initialization(search_tool):
    assert search_tool.name == "Serper Search"
    assert search_tool.api_key is not None


def test_run_no_api_key(test_env_vars):
    """Returns error when API key is not configured."""
    tool = SerperSearchTool()
    # Override the api_key
    tool.api_key = None
    result = tool.run("test query")
    assert result["success"] is False
    assert "SERPER_API_KEY" in result["error"]


def test_run_success(search_tool):
    """Returns parsed results on successful API response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {"title": "Python Docs", "snippet": "Python is great.", "link": "https://python.org", "position": 1},
            {"title": "Python Tutorial", "snippet": "Learn Python.", "link": "https://tutorial.org", "position": 2},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.search_tool.requests.post", return_value=mock_response):
        result = search_tool.run("Python tutorial")

    assert result["success"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Python Docs"
    assert result["query"] == "Python tutorial"


def test_run_answer_box(search_tool):
    """Answer box results are inserted at front."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [{"title": "Result", "snippet": "Text", "link": "url", "position": 1}],
        "answerBox": {"title": "Quick Answer", "answer": "42", "link": "https://example.com"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.search_tool.requests.post", return_value=mock_response):
        result = search_tool.run("question")

    assert result["success"] is True
    # Answer box is inserted at index 0
    assert any(r["type"] == "answer_box" for r in result["results"])


def test_run_knowledge_graph(search_tool):
    """Knowledge graph results are inserted at front."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [],
        "knowledgeGraph": {"title": "Python", "description": "A language.", "website": "https://python.org"},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.search_tool.requests.post", return_value=mock_response):
        result = search_tool.run("Python")

    assert any(r["type"] == "knowledge_graph" for r in result["results"])


def test_run_request_exception(search_tool):
    """Handles requests exceptions gracefully."""
    with patch(
        "lecture_forge.tools.search_tool.requests.post",
        side_effect=requests.exceptions.RequestException("Network error"),
    ):
        # tenacity retries 3 times but we can set stop_after_attempt(1) using a fresh instance
        # Since retry decorator is on the class method, use a short circuit
        result = search_tool.run.__wrapped__(search_tool, "query")

    assert result["success"] is False
    assert "error" in result


def test_run_generic_exception(search_tool):
    """Handles generic exceptions gracefully."""
    with patch("lecture_forge.tools.search_tool.requests.post", side_effect=ValueError("Unexpected")):
        result = search_tool.run.__wrapped__(search_tool, "query")

    assert result["success"] is False


def test_search_and_summarize_success(search_tool):
    """search_and_summarize returns formatted text."""
    mock_result = {
        "success": True,
        "results": [
            {"title": "T1", "snippet": "S1", "url": "http://u1.com"},
            {"title": "T2", "snippet": "S2", "url": "http://u2.com"},
        ],
        "query": "test",
    }
    with patch.object(search_tool, "run", return_value=mock_result):
        summary = search_tool.search_and_summarize("test")

    assert "T1" in summary
    assert "S1" in summary
    assert "http://u1.com" in summary


def test_search_and_summarize_failure(search_tool):
    """search_and_summarize returns error message on failure."""
    mock_result = {
        "success": False,
        "error": "API error",
        "results": [],
    }
    with patch.object(search_tool, "run", return_value=mock_result):
        summary = search_tool.search_and_summarize("test")

    assert "failed" in summary.lower() or "error" in summary.lower()


def test_search_and_summarize_no_results(search_tool):
    """search_and_summarize handles no results."""
    mock_result = {"success": True, "results": [], "query": "test"}
    with patch.object(search_tool, "run", return_value=mock_result):
        summary = search_tool.search_and_summarize("test")

    assert "No results" in summary
