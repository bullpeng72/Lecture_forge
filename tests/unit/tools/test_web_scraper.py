"""
Unit tests for WebScraperTool.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests


@pytest.fixture
def scraper(test_env_vars):
    from lecture_forge.tools.web_scraper import WebScraperTool
    return WebScraperTool()


def test_initialization(scraper):
    from lecture_forge.tools.web_scraper import WebScraperTool
    assert scraper.timeout > 0
    assert "User-Agent" in scraper.headers


def test_initialization_custom_timeout(test_env_vars):
    from lecture_forge.tools.web_scraper import WebScraperTool
    tool = WebScraperTool(timeout=42)
    assert tool.timeout == 42


def test_run_invalid_url(scraper):
    """Returns error for invalid URL."""
    result = scraper.run("not-a-url")
    assert result["success"] is False
    assert "Invalid URL" in result["error"] or "error" in result


def test_run_success(scraper):
    """Returns parsed content for valid response."""
    html = b"""<html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Header</h1>
        <p>Hello world paragraph.</p>
    </body>
    </html>"""

    mock_response = MagicMock()
    mock_response.content = html
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.web_scraper.requests.get", return_value=mock_response):
        result = scraper.run("https://example.com/test")

    assert result["success"] is True
    assert result["title"] == "Test Page"
    assert "text" in result
    assert len(result["text"]) > 0


def test_run_request_exception(scraper):
    """Handles connection errors gracefully."""
    with patch(
        "lecture_forge.tools.web_scraper.requests.get",
        side_effect=requests.exceptions.RequestException("Connection failed"),
    ):
        result = scraper.run("https://unreachable.com")

    assert result["success"] is False
    assert "error" in result


def test_run_empty_body(scraper):
    """Handles page with empty body."""
    html = b"<html><head><title>Empty</title></head><body></body></html>"

    mock_response = MagicMock()
    mock_response.content = html
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.web_scraper.requests.get", return_value=mock_response):
        result = scraper.run("https://example.com")

    assert result["success"] is True


def test_run_no_title(scraper):
    """Handles page with no title tag."""
    html = b"<html><body><p>Content here.</p></body></html>"

    mock_response = MagicMock()
    mock_response.content = html
    mock_response.raise_for_status = MagicMock()

    with patch("lecture_forge.tools.web_scraper.requests.get", return_value=mock_response):
        result = scraper.run("https://example.com")

    assert result["success"] is True
    assert result["title"] == ""  # No title tag
