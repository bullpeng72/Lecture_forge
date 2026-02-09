"""
Search Tool - Performs web searches using Serper API.
"""

from typing import Dict, List

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from lecture_forge.config import Config
from lecture_forge.utils import logger


class SerperSearchTool:
    """Tool for web search using Serper API."""

    name: str = "Serper Search"
    description: str = "Searches the web for relevant information using Serper API"

    def __init__(self):
        """Initialize the search tool."""
        self.api_key = Config.SERPER_API_KEY
        self.api_url = "https://google.serper.dev/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"Search API call failed (attempt {retry_state.attempt_number}/3), retrying..."
        ),
    )
    def run(self, query: str, num_results: int = 10) -> Dict:
        """
        Search the web using Serper API with automatic retry on failures.

        Args:
            query: Search query
            num_results: Number of results to return (max 100)

        Returns:
            Search results with titles, snippets, and URLs
        """
        logger.info(f"Searching for: {query}")

        if not self.api_key:
            return {
                "success": False,
                "results": [],
                "query": query,
                "error": "SERPER_API_KEY not configured in .env",
            }

        try:
            # Prepare request
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "q": query,
                "num": min(num_results, 100),  # API max is 100
            }

            # Make request
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            # Parse results
            results = []

            # Organic results
            if "organic" in data:
                for item in data["organic"][:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "url": item.get("link", ""),
                        "position": item.get("position", 0),
                        "type": "organic",
                    })

            # Answer box (if present)
            if "answerBox" in data:
                answer_box = data["answerBox"]
                results.insert(0, {
                    "title": answer_box.get("title", "Answer"),
                    "snippet": answer_box.get("answer", ""),
                    "url": answer_box.get("link", ""),
                    "position": 0,
                    "type": "answer_box",
                })

            # Knowledge graph (if present)
            if "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                results.insert(0, {
                    "title": kg.get("title", ""),
                    "snippet": kg.get("description", ""),
                    "url": kg.get("website", ""),
                    "position": 0,
                    "type": "knowledge_graph",
                })

            logger.info(f"Search successful: found {len(results)} results")

            return {
                "success": True,
                "results": results,
                "query": query,
                "total_results": len(results),
                "error": None,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching with Serper API: {e}")
            return {
                "success": False,
                "results": [],
                "query": query,
                "error": f"API request failed: {str(e)}",
            }

        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            return {
                "success": False,
                "results": [],
                "query": query,
                "error": str(e),
            }

    def search_and_summarize(self, query: str, num_results: int = 5) -> str:
        """
        Search and return a formatted summary of results.

        Args:
            query: Search query
            num_results: Number of results to include

        Returns:
            Formatted string with search results
        """
        result = self.run(query, num_results)

        if not result["success"]:
            return f"Search failed: {result['error']}"

        if not result["results"]:
            return "No results found."

        summary = f"Search results for '{query}':\n\n"

        for i, item in enumerate(result["results"], 1):
            summary += f"{i}. {item['title']}\n"
            summary += f"   {item['snippet']}\n"
            summary += f"   URL: {item['url']}\n\n"

        return summary
