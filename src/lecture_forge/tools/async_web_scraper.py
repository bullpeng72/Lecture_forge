"""
Async Web Scraper Tool - Asynchronous web page scraping.

Uses httpx for async HTTP requests with improved performance.
"""

import httpx
from typing import Dict
from bs4 import BeautifulSoup

from lecture_forge.config import Config
from lecture_forge.exceptions import WebScrapingError
from lecture_forge.utils import logger


class AsyncWebScraperTool:
    """Async web scraper using httpx."""

    def __init__(self, timeout: float = 30.0):
        """
        Initialize async web scraper.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LectureForge/1.0; +https://github.com/bullpeng72/Lecture_forge)"
        }

    async def run(self, url: str) -> Dict:
        """
        Scrape web page asynchronously.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with:
                - success: bool
                - text: str (page content)
                - metadata: dict
                - error: str (if failed)
        """
        try:
            logger.debug(f"Async scraping: {url}")

            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer"]):
                    element.decompose()

                # Extract text
                text = soup.get_text(separator="\n", strip=True)

                # Clean up whitespace
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                clean_text = "\n".join(lines)

                metadata = {
                    "url": url,
                    "title": soup.title.string if soup.title else "No title",
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", "unknown"),
                }

                logger.debug(
                    f"Successfully scraped {url}: {len(clean_text)} characters"
                )

                return {
                    "success": True,
                    "text": clean_text,
                    "metadata": metadata,
                }

        except httpx.TimeoutException as e:
            error_msg = f"Timeout scraping {url}: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error scraping {url}: {e.response.status_code}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Error scraping {url}: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def run_batch(self, urls: list[str]) -> list[Dict]:
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of results (same format as run())
        """
        import asyncio

        tasks = [self.run(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dicts
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "success": False,
                        "error": f"Exception scraping {urls[i]}: {result}",
                    }
                )
            else:
                processed_results.append(result)

        return processed_results
