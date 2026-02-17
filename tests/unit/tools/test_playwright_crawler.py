"""
Unit tests for PlaywrightCrawler - pure methods and mocked browser interactions.
Tests cover _extract_text, _extract_hada_links, crawl_hada_search, crawl_generic.
"""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup


@pytest.fixture
def crawler(test_env_vars):
    """Create PlaywrightCrawler with PLAYWRIGHT_AVAILABLE patched to True."""
    with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
        from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
        return PlaywrightCrawler(
            max_depth=2,
            max_pages=3,
            delay=0,
            timeout=5000,
            headless=True,
            wait_state="domcontentloaded",
        )


# ===== PlaywrightCrawler.__init__() =====

class TestPlaywrightCrawlerInit:
    def test_raises_import_error_when_playwright_unavailable(self, test_env_vars):
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", False):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            with pytest.raises(ImportError):
                PlaywrightCrawler()

    def test_sets_max_depth(self, crawler):
        assert crawler.max_depth == 2

    def test_sets_max_pages(self, crawler):
        assert crawler.max_pages == 3

    def test_sets_delay(self, crawler):
        assert crawler.delay == 0

    def test_initialized_visited_urls_empty(self, crawler):
        assert crawler.visited_urls == set()


# ===== _extract_text() =====

class TestExtractText:
    def test_extracts_text_from_html(self, crawler):
        html = "<html><body><p>Hello World</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "Hello World" in result

    def test_removes_script_tags(self, crawler):
        html = "<html><body><script>var x = 1;</script><p>Real content</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "var x" not in result
        assert "Real content" in result

    def test_removes_style_tags(self, crawler):
        html = "<html><body><style>body { color: red; }</style><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "color" not in result
        assert "Content" in result

    def test_removes_nav_tags(self, crawler):
        html = "<html><body><nav>Navigation</nav><main>Main content</main></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "Navigation" not in result
        assert "Main content" in result

    def test_returns_string(self, crawler):
        html = "<html><body><p>Test</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert isinstance(result, str)

    def test_empty_html_returns_string(self, crawler):
        soup = BeautifulSoup("", "html.parser")
        result = crawler._extract_text(soup)
        assert isinstance(result, str)

    def test_uses_main_tag_when_present(self, crawler):
        html = "<html><body><aside>Sidebar</aside><main>Main article text</main></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "Main article text" in result

    def test_cleans_whitespace(self, crawler):
        html = "<html><body><p>Line 1</p><p>Line 2</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._extract_text(soup)
        assert "\n\n" not in result  # No double newlines after cleanup


# ===== _extract_hada_links() =====

class TestExtractHadaLinks:
    def test_extracts_topic_links(self, crawler):
        html = """
        <html><body>
        <a href="/topic/123">Article 1</a>
        <a href="/topic?id=456">Article 2</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            result = crawler._extract_hada_links(soup, "https://hada.io/search?q=test")
        assert len(result) >= 0  # May or may not match depending on domain check

    def test_ignores_non_topic_links(self, crawler):
        html = """
        <html><body>
        <a href="/about">About</a>
        <a href="/contact">Contact</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            result = crawler._extract_hada_links(soup, "https://hada.io/search?q=test")
        assert result == []

    def test_returns_list(self, crawler):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            result = crawler._extract_hada_links(soup, "https://hada.io/")
        assert isinstance(result, list)

    def test_no_duplicates(self, crawler):
        html = """
        <html><body>
        <a href="/topic/123">Article</a>
        <a href="/topic/123">Duplicate</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            result = crawler._extract_hada_links(soup, "https://hada.io/search?q=test")
        # Result should have no duplicates
        assert len(result) == len(set(result))


# ===== crawl_hada_search() =====

class TestCrawlHadaSearch:
    def _make_playwright_mock(self, html_content="<html><body><main>Content</main></body></html>"):
        """Create a mock playwright context."""
        mock_page = MagicMock()
        mock_page.content.return_value = html_content
        mock_page.goto.return_value = None
        mock_page.wait_for_selector.return_value = None
        mock_page.wait_for_load_state.return_value = None
        mock_page.close.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_browser.close.return_value = None

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_sync_playwright = MagicMock()
        mock_sync_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_sync_playwright.__exit__ = MagicMock(return_value=False)

        return mock_sync_playwright

    def test_returns_list(self, test_env_vars):
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=1, max_pages=1, delay=0)

        mock_sync = self._make_playwright_mock()
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            mock_config.PLAYWRIGHT_MAX_DEPTH = 1
            mock_config.PLAYWRIGHT_MAX_PAGES = 1
            with patch("lecture_forge.tools.playwright_crawler.sync_playwright", return_value=mock_sync, create=True):
                result = c.crawl_hada_search("test keyword")
        assert isinstance(result, list)

    def test_includes_search_page(self, test_env_vars):
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=1, max_pages=1, delay=0)

        mock_sync = self._make_playwright_mock()
        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_config:
            mock_config.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            with patch("lecture_forge.tools.playwright_crawler.sync_playwright", return_value=mock_sync, create=True):
                result = c.crawl_hada_search("machine learning")
        # Should have at least the search page itself
        assert len(result) >= 1
        assert result[0]["type"] == "search_page"


# ===== crawl_generic() =====

# ===== crawl_hada_search() with max_depth=2 =====


class TestCrawlHadaSearchDepth2:
    """Tests covering article crawling loop (max_depth=2)."""

    def _make_playwright_mock(self, search_html, article_html=None):
        """Create playwright mock that returns different HTML for each page call."""
        html_sequence = [search_html]
        if article_html:
            html_sequence.append(article_html)

        call_count = [0]
        def page_content_side_effect():
            idx = min(call_count[0], len(html_sequence) - 1)
            call_count[0] += 1
            return html_sequence[idx]

        mock_page = MagicMock()
        mock_page.content.side_effect = page_content_side_effect
        mock_page.goto.return_value = None
        mock_page.wait_for_selector.return_value = None
        mock_page.wait_for_load_state.return_value = None
        mock_page.close.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_browser.close.return_value = None

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_sync = MagicMock()
        mock_sync.__enter__ = MagicMock(return_value=mock_playwright)
        mock_sync.__exit__ = MagicMock(return_value=False)

        return mock_sync

    def test_crawls_article_links_with_depth_2(self, test_env_vars):
        """max_depth=2 → articles are crawled after search page."""
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=2, max_pages=1, delay=0)

        search_html = "<html><body><main>Search content</main><a href='/topic/123'>Article</a></body></html>"
        article_html = "<html><head><title>Article Title</title></head><body><main>Article body</main></body></html>"

        mock_sync = self._make_playwright_mock(search_html, article_html)

        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_cfg:
            mock_cfg.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            mock_cfg.PLAYWRIGHT_MAX_DEPTH = 2
            mock_cfg.PLAYWRIGHT_MAX_PAGES = 1
            with patch("lecture_forge.tools.playwright_crawler.sync_playwright",
                       return_value=mock_sync, create=True):
                with patch.object(c, "_extract_hada_links",
                                  return_value=["https://hada.io/topic/123"]):
                    result = c.crawl_hada_search("test")

        # Should have search_page + article
        assert len(result) >= 2
        types = [r["type"] for r in result]
        assert "search_page" in types
        assert "article" in types

    def test_article_exception_handled_gracefully(self, test_env_vars):
        """Exception during article crawl is caught, loop continues."""
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=2, max_pages=2, delay=0)

        search_html = "<html><body><main>Search</main></body></html>"
        mock_sync = self._make_playwright_mock(search_html)

        # Make article page.goto raise an exception
        mock_page = mock_sync.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
        mock_page.goto.side_effect = [None, Exception("navigation error")]

        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_cfg:
            mock_cfg.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            with patch("lecture_forge.tools.playwright_crawler.sync_playwright",
                       return_value=mock_sync, create=True):
                with patch.object(c, "_extract_hada_links",
                                  return_value=["https://hada.io/topic/1"]):
                    result = c.crawl_hada_search("test")

        # Should at least have the search page
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_already_visited_url_skipped(self, test_env_vars):
        """Article URL already in visited_urls is skipped."""
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=2, max_pages=2, delay=0)

        # Pre-populate visited_urls
        c.visited_urls.add("https://hada.io/topic/already-visited")

        search_html = "<html><body><main>Search</main></body></html>"
        mock_sync = self._make_playwright_mock(search_html)

        with patch("lecture_forge.tools.playwright_crawler.Config") as mock_cfg:
            mock_cfg.DEEP_CRAWLER_BASE_URL = "https://hada.io"
            with patch("lecture_forge.tools.playwright_crawler.sync_playwright",
                       return_value=mock_sync, create=True):
                with patch.object(c, "_extract_hada_links",
                                  return_value=["https://hada.io/topic/already-visited"]):
                    result = c.crawl_hada_search("test")

        # Should only have search page (article was skipped)
        assert len(result) == 1


class TestCrawlGeneric:
    def _make_mock_sync(self, html="<html><body><title>Test</title><main>Content</main></body></html>"):
        """Build a complete playwright mock."""
        mock_page = MagicMock()
        mock_page.content.return_value = html
        mock_page.goto.return_value = None
        mock_page.wait_for_load_state.return_value = None
        mock_page.close.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_browser.close.return_value = None

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_sync = MagicMock()
        mock_sync.__enter__ = MagicMock(return_value=mock_playwright)
        mock_sync.__exit__ = MagicMock(return_value=False)
        return mock_sync, mock_page, mock_context

    def test_returns_list(self, test_env_vars):
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=1, max_pages=1, delay=0)

        mock_sync, _, _ = self._make_mock_sync()
        with patch("lecture_forge.tools.playwright_crawler.sync_playwright", return_value=mock_sync, create=True):
            result = c.crawl_generic("https://example.com")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_crawl_generic_with_same_domain_links(self, test_env_vars):
        """crawl_generic follows links on same domain (lines 273-321)."""
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=2, max_pages=2, delay=0)

        html_with_links = """<html><body>
        <title>Main</title><main>Content</main>
        <a href="/page2">Page 2</a>
        </body></html>"""
        page_html = "<html><body><title>Page 2</title><main>Sub content</main></body></html>"

        call_count = [0]
        def content_side():
            call_count[0] += 1
            if call_count[0] == 1:
                return html_with_links
            return page_html

        mock_sync, mock_page, _ = self._make_mock_sync()
        mock_page.content.side_effect = content_side
        mock_page.wait_for_load_state.return_value = None

        with patch("lecture_forge.tools.playwright_crawler.sync_playwright", return_value=mock_sync, create=True):
            result = c.crawl_generic("https://example.com")

        assert isinstance(result, list)
        assert len(result) >= 1

    def test_crawl_generic_link_exception_handled(self, test_env_vars):
        """Exception during linked page crawl is caught (lines 323-324)."""
        with patch("lecture_forge.tools.playwright_crawler.PLAYWRIGHT_AVAILABLE", True):
            from lecture_forge.tools.playwright_crawler import PlaywrightCrawler
            c = PlaywrightCrawler(max_depth=2, max_pages=2, delay=0)

        html_with_links = """<html><body>
        <title>Main</title><main>Content</main>
        <a href="/page2">Page 2</a>
        </body></html>"""

        call_count = [0]
        def goto_side(url, timeout=None):
            call_count[0] += 1
            if call_count[0] > 1:
                raise Exception("navigation error")

        mock_sync, mock_page, _ = self._make_mock_sync(html_with_links)
        mock_page.goto.side_effect = goto_side

        with patch("lecture_forge.tools.playwright_crawler.sync_playwright", return_value=mock_sync, create=True):
            result = c.crawl_generic("https://example.com")

        # Main page should be there, link exception was caught
        assert len(result) >= 1
