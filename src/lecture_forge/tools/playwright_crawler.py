"""
Playwright-based Deep Crawler - Handles JavaScript-rendered content.
"""

import time
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from lecture_forge.config import Config
from lecture_forge.utils import logger

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install")


class PlaywrightCrawler:
    """Deep crawler using Playwright for JavaScript-rendered sites."""

    name: str = "Playwright Deep Crawler"
    description: str = "Crawls JavaScript-rendered websites like Hada.io"

    def __init__(
        self,
        max_depth: int = None,
        max_pages: int = None,
        delay: float = None,
        timeout: int = None,
        headless: bool = True,
    ):
        """
        Initialize Playwright crawler.

        Args:
            max_depth: Maximum crawl depth (default from Config)
            max_pages: Maximum pages per search (default from Config)
            delay: Delay between requests in seconds (default from Config)
            timeout: Page load timeout in milliseconds (default from Config)
            headless: Run browser in headless mode
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for this crawler. " "Install with: pip install playwright && playwright install"
            )

        # Use config defaults if not specified
        self.max_depth = max_depth if max_depth is not None else Config.PLAYWRIGHT_MAX_DEPTH
        self.max_pages = max_pages if max_pages is not None else Config.PLAYWRIGHT_MAX_PAGES
        self.delay = delay if delay is not None else Config.PLAYWRIGHT_DELAY
        self.timeout = timeout if timeout is not None else Config.PLAYWRIGHT_TIMEOUT
        self.headless = headless
        self.visited_urls: Set[str] = set()

    def crawl_hada_search(self, keyword: str) -> List[Dict]:
        """
        Crawl Hada.io search with Playwright.

        Args:
            keyword: Search keyword

        Returns:
            List of crawled content
        """
        logger.info(f"Starting Playwright crawl for: {keyword}")

        all_content = []
        search_url = f"https://news.hada.io/search?q={keyword}"

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            try:
                # Step 1: Crawl search page
                logger.info(f"Loading search page: {search_url}")
                page = context.new_page()

                page.goto(search_url, timeout=self.timeout)

                # Wait for content to load
                try:
                    # Wait for search results or "no results" message
                    page.wait_for_selector("main, .search-results, .topic-list, article", timeout=10000)
                except PlaywrightTimeout:
                    logger.warning("Timeout waiting for search results")

                # Additional wait for dynamic content
                time.sleep(2)

                # Get page content
                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                # Extract text
                search_text = self._extract_text(soup)

                # Add search page
                all_content.append(
                    {
                        "url": search_url,
                        "title": f"Search results for: {keyword}",
                        "text": search_text,
                        "type": "search_page",
                        "metadata": {
                            "url": search_url,
                            "content_length": len(search_text),
                            "word_count": len(search_text.split()),
                        },
                    }
                )

                # Extract article links
                article_links = self._extract_hada_links(soup, search_url)
                logger.info(f"Found {len(article_links)} article links")

                # Step 2: Crawl articles
                if self.max_depth >= 2 and article_links:
                    for i, link in enumerate(article_links[: self.max_pages], 1):
                        if link in self.visited_urls:
                            continue

                        time.sleep(self.delay)

                        logger.info(f"Crawling article {i}/{min(len(article_links), self.max_pages)}: {link}")

                        try:
                            article_page = context.new_page()
                            article_page.goto(link, timeout=self.timeout)

                            # Wait for article content
                            try:
                                article_page.wait_for_selector("article, .topic-content, main", timeout=10000)
                            except PlaywrightTimeout:
                                logger.warning(f"Timeout loading article: {link}")

                            time.sleep(1)

                            # Get content
                            article_html = article_page.content()
                            article_soup = BeautifulSoup(article_html, "html.parser")

                            title = article_soup.title.string if article_soup.title else "No title"
                            text = self._extract_text(article_soup)

                            all_content.append(
                                {
                                    "url": link,
                                    "title": title,
                                    "text": text,
                                    "type": "article",
                                    "metadata": {
                                        "url": link,
                                        "title": title,
                                        "content_length": len(text),
                                        "word_count": len(text.split()),
                                    },
                                }
                            )

                            self.visited_urls.add(link)
                            article_page.close()

                        except Exception as e:
                            logger.error(f"Error crawling article {link}: {e}")

                page.close()

            finally:
                browser.close()

        logger.info(f"Playwright crawl completed: {len(all_content)} pages")
        return all_content

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from HTML."""
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Find main content
        main = soup.find("main") or soup.find("article") or soup.find("body") or soup

        # Get text
        text = main.get_text(separator="\n", strip=True)

        # Clean up
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        cleaned_text = "\n".join(lines)

        return cleaned_text

    def _extract_hada_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract article links from Hada.io."""
        links = []

        # Hada.io link patterns: both /topic/ and /topic?id=
        for link in soup.find_all("a", href=True):
            href = link.get("href")

            # Check for topic links (both formats)
            if "/topic" in href and ("topic/" in href or "topic?" in href):
                full_url = urljoin(base_url, href)

                # Filter out duplicates and external links
                if "news.hada.io" in full_url and full_url not in links:
                    links.append(full_url)

        return links

    def crawl_generic(self, url: str, link_selector: str = "a[href]") -> List[Dict]:
        """
        Generic Playwright crawler for any site.

        Args:
            url: URL to crawl
            link_selector: CSS selector for links

        Returns:
            List of crawled content
        """
        logger.info(f"Crawling {url} with Playwright")

        all_content = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()

            try:
                page = context.new_page()
                page.goto(url, timeout=self.timeout)

                # Wait for content
                time.sleep(2)

                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                # Extract main page
                text = self._extract_text(soup)
                title = soup.title.string if soup.title else "No title"

                all_content.append(
                    {
                        "url": url,
                        "title": title,
                        "text": text,
                        "type": "main_page",
                        "metadata": {
                            "url": url,
                            "content_length": len(text),
                            "word_count": len(text.split()),
                        },
                    }
                )

                # Extract links
                links = []
                for element in soup.select(link_selector):
                    href = element.get("href")
                    if href:
                        full_url = urljoin(url, href)
                        if urlparse(full_url).netloc == urlparse(url).netloc:
                            links.append(full_url)

                links = list(set(links))[: self.max_pages]

                # Crawl linked pages
                for i, link in enumerate(links, 1):
                    if link in self.visited_urls:
                        continue

                    time.sleep(self.delay)

                    logger.info(f"Crawling page {i}/{len(links)}: {link}")

                    try:
                        link_page = context.new_page()
                        link_page.goto(link, timeout=self.timeout)
                        time.sleep(1)

                        link_html = link_page.content()
                        link_soup = BeautifulSoup(link_html, "html.parser")

                        link_text = self._extract_text(link_soup)
                        link_title = link_soup.title.string if link_soup.title else "No title"

                        all_content.append(
                            {
                                "url": link,
                                "title": link_title,
                                "text": link_text,
                                "type": "linked_page",
                                "metadata": {
                                    "url": link,
                                    "content_length": len(link_text),
                                    "word_count": len(link_text.split()),
                                },
                            }
                        )

                        self.visited_urls.add(link)
                        link_page.close()

                    except Exception as e:
                        logger.error(f"Error crawling {link}: {e}")

                page.close()

            finally:
                browser.close()

        logger.info(f"Crawl completed: {len(all_content)} pages")
        return all_content
