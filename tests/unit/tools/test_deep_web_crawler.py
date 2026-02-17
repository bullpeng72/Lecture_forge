"""
Unit tests for DeepWebCrawler - _find_main_content, _extract_hada_article_links,
and _scrape_page with mocked requests.
"""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup


@pytest.fixture
def crawler(test_env_vars):
    """Create DeepWebCrawler instance."""
    from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
    return DeepWebCrawler(max_depth=1, max_pages=5, delay=0, timeout=5)


# ===== _find_main_content() =====

class TestFindMainContent:
    def test_finds_main_tag(self, crawler):
        html = "<html><body><main><p>content</p></main><aside>other</aside></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.name == "main"

    def test_finds_article_tag(self, crawler):
        html = "<html><body><article><p>article content</p></article></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.name == "article"

    def test_finds_role_main(self, crawler):
        html = "<html><body><div role='main'><p>role content</p></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.get("role") == "main"

    def test_finds_content_class(self, crawler):
        html = "<html><body><div class='content'><p>class content</p></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert "content" in result.get("class", [])

    def test_finds_content_id(self, crawler):
        html = "<html><body><div id='content'><p>id content</p></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.get("id") == "content"

    def test_falls_back_to_body(self, crawler):
        html = "<html><body><p>plain body</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.name == "body"

    def test_main_takes_priority_over_article(self, crawler):
        html = "<html><body><main><p>main content</p></main><article><p>article</p></article></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = crawler._find_main_content(soup)
        assert result.name == "main"


# ===== _extract_hada_article_links() =====

class TestExtractHadaArticleLinks:
    def test_extracts_topic_slash_links(self, crawler):
        base_url = "https://news.hada.io"
        html = '''
        <html><body>
            <a href="/topic/12345">Article 1</a>
            <a href="/other">Other link</a>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.deep_web_crawler.Config.DEEP_CRAWLER_BASE_URL", base_url):
            result = crawler._extract_hada_article_links(soup, base_url)
        # Should find link with /topic/
        topic_links = [u for u in result if "/topic/" in u]
        assert len(topic_links) >= 1

    def test_extracts_topic_query_links(self, crawler):
        base_url = "https://news.hada.io"
        html = '''
        <html><body>
            <a href="/topic?id=12345">Article Query</a>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.deep_web_crawler.Config.DEEP_CRAWLER_BASE_URL", base_url):
            result = crawler._extract_hada_article_links(soup, base_url)
        topic_links = [u for u in result if "topic" in u]
        assert len(topic_links) >= 1

    def test_deduplicates_links(self, crawler):
        base_url = "https://news.hada.io"
        html = '''
        <html><body>
            <a href="/topic/123">Article 1</a>
            <a href="/topic/123">Article 1 Duplicate</a>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.deep_web_crawler.Config.DEEP_CRAWLER_BASE_URL", base_url):
            result = crawler._extract_hada_article_links(soup, base_url)
        assert len(result) == len(set(result))

    def test_empty_soup_returns_empty(self, crawler):
        base_url = "https://news.hada.io"
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        with patch("lecture_forge.tools.deep_web_crawler.Config.DEEP_CRAWLER_BASE_URL", base_url):
            result = crawler._extract_hada_article_links(soup, base_url)
        assert result == []

    def test_returns_list(self, crawler):
        base_url = "https://news.hada.io"
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        with patch("lecture_forge.tools.deep_web_crawler.Config.DEEP_CRAWLER_BASE_URL", base_url):
            result = crawler._extract_hada_article_links(soup, base_url)
        assert isinstance(result, list)


# ===== _scrape_page() =====

class TestScrapePage:
    def _make_response(self, html_str, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = html_str
        resp.content = html_str.encode("utf-8")
        resp.raise_for_status = MagicMock()
        return resp

    def test_returns_title(self, crawler):
        html = "<html><head><title>Test Title</title></head><body><p>Body content here and more.</p></body></html>"
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com/page")
        assert result["title"] == "Test Title"

    def test_returns_text(self, crawler):
        html = "<html><head><title>T</title></head><body><p>Some body content text.</p></body></html>"
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com/page")
        assert "body content" in result["text"]

    def test_returns_url_in_metadata(self, crawler):
        html = "<html><head><title>T</title></head><body><p>content</p></body></html>"
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com/page")
        assert result["metadata"]["url"] == "http://example.com/page"

    def test_handles_request_exception(self, crawler):
        with patch("requests.get", side_effect=Exception("Connection error")):
            result = crawler._scrape_page("http://example.com/broken")
        assert result["text"] == ""
        assert result["title"] == ""
        assert "error" in result

    def test_returns_dict_structure(self, crawler):
        html = "<html><head><title>T</title></head><body><p>content</p></body></html>"
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com")
        assert "title" in result
        assert "text" in result
        assert "metadata" in result

    def test_removes_script_and_nav_tags(self, crawler):
        """script/style/nav tags are decomposed (line 145)."""
        html = """<html><head><title>T</title></head><body>
        <script>var x=1;</script>
        <nav>Nav content</nav>
        <p>Real content here.</p>
        </body></html>"""
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com")
        assert "var x" not in result.get("text", "")
        assert "Nav content" not in result.get("text", "")

    def test_extracts_meta_description(self, crawler):
        """Meta description tag is added to metadata (line 170)."""
        html = """<html><head>
        <title>T</title>
        <meta name="description" content="A great page about testing.">
        </head><body><p>content</p></body></html>"""
        mock_resp = self._make_response(html)
        with patch("requests.get", return_value=mock_resp):
            result = crawler._scrape_page("http://example.com")
        assert result["metadata"].get("description") == "A great page about testing."


# ===== crawl_generic() =====

class TestCrawlGeneric:
    """Tests for crawl_generic() method (lines 243-298)."""

    def _make_search_result(self, html=None, text="content", title="Page"):
        from bs4 import BeautifulSoup
        if html is None:
            html = "<html><body><p>text</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        return {
            "success": True,
            "text": text,
            "title": title,
            "html": soup,
            "metadata": {"url": "http://example.com/search"},
            "error": None,
        }

    def test_returns_empty_on_search_fail(self, test_env_vars):
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)
        with patch.object(c, "_scrape_page", return_value={"success": False, "text": "", "title": "", "html": None, "metadata": {}}):
            result = c.crawl_generic_search("http://example.com")
        assert result == []

    def test_returns_search_page(self, test_env_vars):
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=1, max_pages=3, delay=0, timeout=5)
        search_result = self._make_search_result(text="search content")
        with patch.object(c, "_scrape_page", return_value=search_result):
            result = c.crawl_generic_search("http://example.com")
        assert len(result) == 1
        assert result[0]["type"] == "search_page"

    def test_crawls_same_domain_links(self, test_env_vars):
        """Links on same domain are crawled (lines 264-295)."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)

        html_with_links = """<html><body>
        <p>Main content</p>
        <a href="/page2">Page 2</a>
        </body></html>"""
        search_result = self._make_search_result(html=html_with_links)
        linked_result = self._make_search_result(text="linked content", title="Page 2")

        with patch.object(c, "_scrape_page", side_effect=[search_result, linked_result]):
            result = c.crawl_generic_search("http://example.com")

        assert len(result) >= 1

    def test_skips_already_visited_links(self, test_env_vars):
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)

        html_with_links = """<html><body>
        <a href="/page2">Page 2</a>
        </body></html>"""
        search_result = self._make_search_result(html=html_with_links)
        # Pre-visit the link
        c.visited_urls.add("http://example.com/page2")

        with patch.object(c, "_scrape_page", return_value=search_result) as mock_scrape:
            result = c.crawl_generic_search("http://example.com")

        # Only search page scraped (linked page skipped)
        mock_scrape.assert_called_once()

    def test_no_html_in_result_skips_links(self, test_env_vars):
        """search_content['html'] is None → link extraction skipped."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)
        result_no_html = {
            "success": True, "text": "content", "title": "T",
            "html": None, "metadata": {}, "error": None
        }
        with patch.object(c, "_scrape_page", return_value=result_no_html) as mock_scrape:
            result = c.crawl_generic_search("http://example.com")
        mock_scrape.assert_called_once()
        assert len(result) == 1


# ===== crawl_hada_search() =====

class TestCrawlHadaSearch:
    """Tests covering the crawl_hada_search() method."""

    def _make_search_result(self, success=True, text="content", links=None):
        """Build a mock _scrape_page() return value."""
        from bs4 import BeautifulSoup
        html = "<html><body><p>text</p></body></html>"
        if links:
            link_tags = "".join(f'<a href="{l}">Link</a>' for l in links)
            html = f"<html><body>{link_tags}</body></html>"
        soup = BeautifulSoup(html, "html.parser") if success else None
        return {
            "success": success,
            "text": text,
            "title": "Search Page",
            "html": soup,
            "metadata": {"url": "http://example.com/search"},
            "error": None if success else "timeout",
        }

    def test_returns_empty_on_search_page_fail(self, test_env_vars):
        """When search page crawl fails, return empty list."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)
        with patch.object(c, "_scrape_page", return_value=self._make_search_result(success=False)):
            result = c.crawl_hada_search("test")
        assert result == []

    def test_returns_search_page_content(self, test_env_vars):
        """Successful search page is included in result."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=1, max_pages=3, delay=0, timeout=5)
        search_result = self._make_search_result(text="search content")
        with patch.object(c, "_scrape_page", return_value=search_result):
            with patch.object(c, "_extract_hada_article_links", return_value=[]):
                result = c.crawl_hada_search("test")
        assert len(result) == 1
        assert result[0]["type"] == "search_page"
        assert "search content" in result[0]["text"]

    def test_max_depth_1_skips_article_crawl(self, test_env_vars):
        """With max_depth=1, article links are not followed."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=1, max_pages=3, delay=0, timeout=5)
        search_result = self._make_search_result()
        with patch.object(c, "_scrape_page", return_value=search_result) as mock_scrape:
            with patch.object(c, "_extract_hada_article_links",
                              return_value=["http://example.com/topic/1"]):
                result = c.crawl_hada_search("test")
        # Only 1 call to _scrape_page (the search page), articles not crawled
        mock_scrape.assert_called_once()
        assert len(result) == 1

    def test_max_depth_2_crawls_articles(self, test_env_vars):
        """With max_depth=2, article links are crawled."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)

        search_result = self._make_search_result(text="search text")
        article_result = {
            "success": True,
            "text": "article text",
            "title": "Article Title",
            "html": None,
            "metadata": {"url": "http://example.com/topic/1"},
            "error": None,
        }

        with patch.object(c, "_scrape_page", side_effect=[search_result, article_result]):
            with patch.object(c, "_extract_hada_article_links",
                              return_value=["http://example.com/topic/1"]):
                result = c.crawl_hada_search("test")

        assert len(result) == 2
        assert result[0]["type"] == "search_page"
        assert result[1]["type"] == "article"
        assert result[1]["title"] == "Article Title"

    def test_max_pages_limits_articles(self, test_env_vars):
        """max_pages=1 stops after crawling 1 article."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=1, delay=0, timeout=5)

        search_result = self._make_search_result()
        article_result = {"success": True, "text": "a", "title": "A", "html": None,
                          "metadata": {}, "error": None}

        article_links = [
            "http://example.com/topic/1",
            "http://example.com/topic/2",
            "http://example.com/topic/3",
        ]

        with patch.object(c, "_scrape_page", side_effect=[search_result, article_result]):
            with patch.object(c, "_extract_hada_article_links", return_value=article_links):
                result = c.crawl_hada_search("test")

        # Should have search_page + 1 article (max_pages=1)
        assert len(result) == 2

    def test_visited_urls_skipped(self, test_env_vars):
        """Articles already in visited_urls are skipped."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=5, delay=0, timeout=5)

        search_result = self._make_search_result()
        article_link = "http://example.com/topic/already-visited"

        # Pre-populate visited_urls
        c.visited_urls.add(article_link)

        with patch.object(c, "_scrape_page", return_value=search_result) as mock_scrape:
            with patch.object(c, "_extract_hada_article_links", return_value=[article_link]):
                result = c.crawl_hada_search("test")

        # _scrape_page only called once (for search page); article is skipped
        mock_scrape.assert_called_once()
        assert len(result) == 1

    def test_article_failure_skipped_gracefully(self, test_env_vars):
        """When article scrape fails, it is skipped (not added to results)."""
        from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
        c = DeepWebCrawler(max_depth=2, max_pages=3, delay=0, timeout=5)

        search_result = self._make_search_result()
        failed_article = {"success": False, "text": "", "title": "", "html": None,
                          "metadata": {}, "error": "404"}

        with patch.object(c, "_scrape_page", side_effect=[search_result, failed_article]):
            with patch.object(c, "_extract_hada_article_links",
                              return_value=["http://example.com/topic/1"]):
                result = c.crawl_hada_search("test")

        # Failed article is not added; only search page in results
        assert len(result) == 1
