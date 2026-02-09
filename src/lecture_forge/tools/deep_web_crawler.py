"""
Deep Web Crawler Tool - Crawls search results and linked content.
"""

import time
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from lecture_forge.utils import logger


class DeepWebCrawler:
    """Tool for deep crawling web content with link following."""

    name: str = "Deep Web Crawler"
    description: str = "Crawls search results and follows links to gather comprehensive content"

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 10,
        delay: float = 1.0,
        timeout: int = 30,
    ):
        """
        Initialize the deep web crawler.

        Args:
            max_depth: Maximum depth to crawl (1 = only search results, 2 = search + linked pages)
            max_pages: Maximum number of pages to crawl per search
            delay: Delay between requests in seconds (rate limiting)
            timeout: Request timeout in seconds
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.visited_urls: Set[str] = set()

    def crawl_hada_search(self, keyword: str) -> List[Dict]:
        """
        Crawl news.hada.io search results and linked articles.

        Args:
            keyword: Search keyword

        Returns:
            List of crawled content dictionaries
        """
        logger.info(f"Starting deep crawl for keyword: {keyword}")

        all_content = []
        search_url = f"https://news.hada.io/search?q={keyword}"

        # Step 1: Crawl search results page
        logger.info(f"Crawling search page: {search_url}")
        search_content = self._scrape_page(search_url)

        if not search_content["success"]:
            logger.error(f"Failed to crawl search page: {search_content['error']}")
            return all_content

        # Extract article links from search results
        article_links = self._extract_hada_article_links(
            search_content["html"], search_url
        )
        logger.info(f"Found {len(article_links)} article links")

        # Add search page content
        all_content.append(
            {
                "url": search_url,
                "title": f"Search results for: {keyword}",
                "text": search_content["text"],
                "type": "search_page",
                "metadata": search_content["metadata"],
            }
        )

        # Step 2: Crawl each article (depth 2)
        if self.max_depth >= 2:
            crawled_count = 0
            for link in article_links:
                if crawled_count >= self.max_pages:
                    logger.info(f"Reached max pages limit ({self.max_pages})")
                    break

                if link in self.visited_urls:
                    logger.debug(f"Skipping already visited: {link}")
                    continue

                # Rate limiting
                time.sleep(self.delay)

                # Crawl article
                logger.info(f"Crawling article ({crawled_count + 1}/{self.max_pages}): {link}")
                article_content = self._scrape_page(link)

                if article_content["success"]:
                    all_content.append(
                        {
                            "url": link,
                            "title": article_content["title"],
                            "text": article_content["text"],
                            "type": "article",
                            "metadata": article_content["metadata"],
                        }
                    )
                    crawled_count += 1
                else:
                    logger.warning(f"Failed to crawl article: {link}")

        logger.info(f"Deep crawl completed: {len(all_content)} pages collected")
        return all_content

    def _scrape_page(self, url: str) -> Dict:
        """
        Scrape a single page.

        Args:
            url: URL to scrape

        Returns:
            Scraped content dictionary
        """
        try:
            self.visited_urls.add(url)

            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else ""

            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # Extract main content
            main_content = self._find_main_content(soup)

            # Get text
            text = main_content.get_text(separator="\n", strip=True)

            # Clean up
            lines = [line.strip() for line in text.split("\n")]
            lines = [line for line in lines if line]
            cleaned_text = "\n".join(lines)

            # Metadata
            metadata = {
                "url": url,
                "title": title,
                "domain": urlparse(url).netloc,
                "content_length": len(cleaned_text),
                "word_count": len(cleaned_text.split()),
            }

            # Extract description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                metadata["description"] = meta_desc.get("content", "").strip()

            return {
                "success": True,
                "text": cleaned_text,
                "title": title,
                "html": soup,
                "metadata": metadata,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "success": False,
                "text": "",
                "title": "",
                "html": None,
                "metadata": {"url": url},
                "error": str(e),
            }

    def _find_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Find main content area in HTML."""
        # Try common content containers
        for selector in ["main", "article", "[role='main']", ".content", "#content"]:
            content = soup.select_one(selector)
            if content:
                return content

        # Fallback to body
        body = soup.find("body")
        return body if body else soup

    def _extract_hada_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract article links from Hada.io search results.

        Args:
            soup: BeautifulSoup object of search page
            base_url: Base URL for resolving relative links

        Returns:
            List of article URLs
        """
        links = []

        # Hada.io link patterns: both /topic/ and /topic?id=
        for link in soup.find_all("a", href=True):
            href = link.get("href")

            # Check for topic links (both /topic/ and /topic?id= formats)
            if "/topic" in href and ("topic/" in href or "topic?" in href):
                full_url = urljoin(base_url, href)

                # Filter only Hada.io article URLs
                if "news.hada.io" in full_url and full_url not in links:
                    links.append(full_url)

        return links

    def crawl_generic_search(
        self, search_url: str, link_selector: str = "a[href]"
    ) -> List[Dict]:
        """
        Generic crawler for any search page.

        Args:
            search_url: Search URL with keyword already included
            link_selector: CSS selector for extracting links

        Returns:
            List of crawled content
        """
        logger.info(f"Starting generic deep crawl: {search_url}")

        all_content = []

        # Crawl search page
        search_content = self._scrape_page(search_url)

        if not search_content["success"]:
            return all_content

        all_content.append(
            {
                "url": search_url,
                "title": search_content["title"],
                "text": search_content["text"],
                "type": "search_page",
                "metadata": search_content["metadata"],
            }
        )

        # Extract links
        if search_content["html"]:
            links = []
            for link in search_content["html"].select(link_selector):
                href = link.get("href")
                if href:
                    full_url = urljoin(search_url, href)
                    # Filter external links
                    if urlparse(full_url).netloc == urlparse(search_url).netloc:
                        links.append(full_url)

            links = list(set(links))[:self.max_pages]  # Deduplicate and limit

            # Crawl each link
            for i, link in enumerate(links, 1):
                if link in self.visited_urls:
                    continue

                time.sleep(self.delay)

                logger.info(f"Crawling page ({i}/{len(links)}): {link}")
                content = self._scrape_page(link)

                if content["success"]:
                    all_content.append(
                        {
                            "url": link,
                            "title": content["title"],
                            "text": content["text"],
                            "type": "linked_page",
                            "metadata": content["metadata"],
                        }
                    )

        logger.info(f"Generic crawl completed: {len(all_content)} pages")
        return all_content
