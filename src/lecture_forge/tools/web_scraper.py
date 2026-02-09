"""
Web Scraper Tool - Scrapes content from URLs.
"""

from datetime import datetime
from typing import Dict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from lecture_forge.utils import logger


class WebScraperTool:
    """Tool for scraping web content."""

    name: str = "Web Scraper"
    description: str = "Scrapes and extracts clean text content from web pages"

    def __init__(self, timeout: int = None):
        """
        Initialize the web scraper.

        Args:
            timeout: Request timeout in seconds (default from Config)
        """
        from lecture_forge.config import Config

        self.timeout = timeout if timeout is not None else Config.WEB_SCRAPER_TIMEOUT
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def run(self, url: str) -> Dict:
        """
        Scrape a web page.

        Args:
            url: URL to scrape

        Returns:
            Scraped content with text and metadata
        """
        logger.info(f"Scraping URL: {url}")

        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {
                    "success": False,
                    "text": "",
                    "title": "",
                    "metadata": {},
                    "error": f"Invalid URL: {url}",
                }

            # Fetch the page
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else ""

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Extract main content
            # Try to find main content area
            main_content = None
            for tag in ["main", "article", "div[role='main']"]:
                main_content = soup.find(tag)
                if main_content:
                    break

            # If no main content found, use body
            if not main_content:
                main_content = soup.find("body")

            if not main_content:
                main_content = soup

            # Get text
            text = main_content.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split("\n")]
            lines = [line for line in lines if line]  # Remove empty lines
            cleaned_text = "\n".join(lines)

            # Extract metadata
            metadata = {
                "url": url,
                "title": title,
                "scrape_date": datetime.now().isoformat(),
                "domain": parsed.netloc,
                "content_length": len(cleaned_text),
                "word_count": len(cleaned_text.split()),
            }

            # Try to extract description/summary
            description = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                description = meta_desc.get("content", "").strip()
                metadata["description"] = description

            # Try to extract author
            author = ""
            meta_author = soup.find("meta", attrs={"name": "author"})
            if meta_author and meta_author.get("content"):
                author = meta_author.get("content", "").strip()
                metadata["author"] = author

            logger.info(f"Successfully scraped URL: {len(cleaned_text)} characters, {metadata['word_count']} words")

            return {
                "success": True,
                "text": cleaned_text,
                "title": title,
                "metadata": metadata,
                "error": None,
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout scraping URL {url}")
            return {
                "success": False,
                "text": "",
                "title": "",
                "metadata": {"url": url},
                "error": f"Timeout after {self.timeout} seconds",
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping URL {url}: {e}")
            return {
                "success": False,
                "text": "",
                "title": "",
                "metadata": {"url": url},
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"Unexpected error scraping URL {url}: {e}")
            return {
                "success": False,
                "text": "",
                "title": "",
                "metadata": {"url": url},
                "error": str(e),
            }
