"""
Async Search Tool - Asynchronous web search using Serper API.

Uses httpx for async API calls with improved performance.
"""

import httpx
from typing import Dict, List

from lecture_forge.config import Config
from lecture_forge.exceptions import SearchAPIError
from lecture_forge.utils import logger


class AsyncSerperSearchTool:
    """Async Serper search tool using httpx."""

    def __init__(self):
        """Initialize async Serper search tool."""
        self.api_key = Config.SERPER_API_KEY
        if not self.api_key:
            raise SearchAPIError("SERPER_API_KEY not found in configuration")

        self.base_url = "https://google.serper.dev/search"
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    async def run(self, query: str, num_results: int = 5) -> Dict:
        """
        Search web asynchronously using Serper API.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            Dictionary with:
                - success: bool
                - results: list of dicts
                - total_results: int
                - error: str (if failed)
        """
        try:
            logger.debug(f"Async searching: {query}")

            payload = {
                "q": query,
                "num": num_results,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()

                data = response.json()

                # Extract organic results
                organic_results = data.get("organic", [])
                results = []

                for item in organic_results[:num_results]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": item.get("link", ""),
                        }
                    )

                logger.debug(f"Found {len(results)} results for: {query}")

                return {
                    "success": True,
                    "results": results,
                    "total_results": len(results),
                }

        except httpx.TimeoutException as e:
            error_msg = f"Timeout searching for '{query}': {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "results": []}

        except httpx.HTTPStatusError as e:
            error_msg = (
                f"HTTP error searching for '{query}': {e.response.status_code}"
            )
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "results": []}

        except Exception as e:
            error_msg = f"Error searching for '{query}': {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "results": []}

    async def run_batch(self, queries: List[str], num_results: int = 5) -> List[Dict]:
        """
        Search multiple queries concurrently.

        Args:
            queries: List of search queries
            num_results: Number of results per query

        Returns:
            List of results (same format as run())
        """
        import asyncio

        tasks = [self.run(query, num_results) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dicts
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "success": False,
                        "error": f"Exception searching '{queries[i]}': {result}",
                        "results": [],
                    }
                )
            else:
                processed_results.append(result)

        return processed_results
