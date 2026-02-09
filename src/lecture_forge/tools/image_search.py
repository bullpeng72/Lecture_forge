"""
Image Search Tool - Searches for images using Unsplash and Pexels APIs.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import requests

from lecture_forge.config import Config
from lecture_forge.utils import logger


class UnsplashSearchTool:
    """Tool for searching images on Unsplash."""

    name: str = "Unsplash Search"
    description: str = "Searches for high-quality, free-to-use images on Unsplash"

    def __init__(self, output_dir: str = "./data/images"):
        """
        Initialize the Unsplash search tool.

        Args:
            output_dir: Directory to save downloaded images
        """
        self.access_key = Config.UNSPLASH_ACCESS_KEY
        self.api_url = "https://api.unsplash.com/search/photos"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        query: str,
        per_page: int = 10,
        orientation: str = "landscape",
        session_id: str = "default",
        download: bool = True,
    ) -> Dict:
        """
        Search for images on Unsplash.

        Args:
            query: Search query
            per_page: Number of results (max 30)
            orientation: Image orientation (landscape/portrait/squarish)
            session_id: Session identifier for organizing images
            download: Whether to download images

        Returns:
            Search results with image URLs and metadata
        """
        logger.info(f"Searching Unsplash for: {query}")

        if not self.access_key:
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": "UNSPLASH_ACCESS_KEY not configured in .env",
            }

        try:
            # Prepare request
            headers = {"Authorization": f"Client-ID {self.access_key}"}

            params = {
                "query": query,
                "per_page": min(per_page, 30),  # API max is 30
                "orientation": orientation,
            }

            # Make request
            response = requests.get(
                self.api_url,
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            images = []

            if "results" in data:
                # Create session directory if downloading
                if download:
                    session_dir = self.output_dir / session_id
                    session_dir.mkdir(parents=True, exist_ok=True)

                for idx, photo in enumerate(data["results"]):
                    try:
                        # Get image URL (regular quality)
                        image_url = photo["urls"]["regular"]
                        download_url = photo["links"]["download_location"]

                        # Get metadata
                        image_id = photo["id"]
                        description = photo.get("description") or photo.get("alt_description", "")
                        author = photo["user"]["name"]
                        author_username = photo["user"]["username"]
                        width = photo["width"]
                        height = photo["height"]
                        color = photo.get("color", "#000000")

                        image_metadata = {
                            "id": f"unsplash_{image_id}",
                            "url": image_url,
                            "download_url": download_url,
                            "description": description,
                            "width": width,
                            "height": height,
                            "color": color,
                            "author": author,
                            "author_username": author_username,
                            "attribution": f"Photo by {author} on Unsplash",
                            "license": "Unsplash License",
                            "source": "unsplash",
                            "query": query,
                        }

                        # Download image if requested
                        if download:
                            # Trigger download endpoint (required by Unsplash API)
                            try:
                                requests.get(
                                    download_url,
                                    headers=headers,
                                    timeout=10,
                                )
                            except (requests.RequestException, TimeoutError) as e:
                                logger.debug(f"Failed to trigger Unsplash download endpoint: {e}")

                            # Download actual image
                            img_response = requests.get(image_url, timeout=30)
                            img_response.raise_for_status()

                            image_bytes = img_response.content
                            image_hash = hashlib.md5(image_bytes).hexdigest()

                            filename = f"unsplash_{image_id}_{image_hash[:8]}.jpg"
                            image_path = session_dir / filename

                            with open(image_path, "wb") as f:
                                f.write(image_bytes)

                            image_metadata["path"] = str(image_path)
                            image_metadata["filename"] = filename
                            image_metadata["size_bytes"] = len(image_bytes)
                            image_metadata["hash"] = image_hash

                        images.append(image_metadata)

                    except Exception as e:
                        logger.warning(f"Error processing Unsplash image {idx}: {e}")
                        continue

            logger.info(f"Found {len(images)} images on Unsplash")

            return {
                "success": True,
                "images": images,
                "query": query,
                "total_results": len(images),
                "session_dir": str(session_dir) if download else None,
                "error": None,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Unsplash: {e}")
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": f"API request failed: {str(e)}",
            }

        except Exception as e:
            logger.error(f"Unexpected error during Unsplash search: {e}")
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": str(e),
            }


class PexelsSearchTool:
    """Tool for searching images on Pexels."""

    name: str = "Pexels Search"
    description: str = "Searches for high-quality, free-to-use images on Pexels"

    def __init__(self, output_dir: str = "./data/images"):
        """
        Initialize the Pexels search tool.

        Args:
            output_dir: Directory to save downloaded images
        """
        self.api_key = Config.PEXELS_API_KEY
        self.api_url = "https://api.pexels.com/v1/search"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        query: str,
        per_page: int = 10,
        orientation: str = "landscape",
        session_id: str = "default",
        download: bool = True,
    ) -> Dict:
        """
        Search for images on Pexels.

        Args:
            query: Search query
            per_page: Number of results (max 80)
            orientation: Image orientation (landscape/portrait/square)
            session_id: Session identifier for organizing images
            download: Whether to download images

        Returns:
            Search results with image URLs and metadata
        """
        logger.info(f"Searching Pexels for: {query}")

        if not self.api_key:
            logger.warning("PEXELS_API_KEY not configured, skipping Pexels search")
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": "PEXELS_API_KEY not configured in .env",
            }

        try:
            # Prepare request
            headers = {"Authorization": self.api_key}

            params = {
                "query": query,
                "per_page": min(per_page, 80),  # API max is 80
                "orientation": orientation,
            }

            # Make request
            response = requests.get(
                self.api_url,
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            images = []

            if "photos" in data:
                # Create session directory if downloading
                if download:
                    session_dir = self.output_dir / session_id
                    session_dir.mkdir(parents=True, exist_ok=True)

                for idx, photo in enumerate(data["photos"]):
                    try:
                        # Get image URL (large size)
                        image_url = photo["src"]["large"]

                        # Get metadata
                        image_id = photo["id"]
                        description = photo.get("alt", "")
                        photographer = photo["photographer"]
                        photographer_url = photo["photographer_url"]
                        width = photo["width"]
                        height = photo["height"]

                        image_metadata = {
                            "id": f"pexels_{image_id}",
                            "url": image_url,
                            "description": description,
                            "width": width,
                            "height": height,
                            "photographer": photographer,
                            "photographer_url": photographer_url,
                            "attribution": f"Photo by {photographer} on Pexels",
                            "license": "Pexels License",
                            "source": "pexels",
                            "query": query,
                        }

                        # Download image if requested
                        if download:
                            img_response = requests.get(image_url, timeout=30)
                            img_response.raise_for_status()

                            image_bytes = img_response.content
                            image_hash = hashlib.md5(image_bytes).hexdigest()

                            filename = f"pexels_{image_id}_{image_hash[:8]}.jpg"
                            image_path = session_dir / filename

                            with open(image_path, "wb") as f:
                                f.write(image_bytes)

                            image_metadata["path"] = str(image_path)
                            image_metadata["filename"] = filename
                            image_metadata["size_bytes"] = len(image_bytes)
                            image_metadata["hash"] = image_hash

                        images.append(image_metadata)

                    except Exception as e:
                        logger.warning(f"Error processing Pexels image {idx}: {e}")
                        continue

            logger.info(f"Found {len(images)} images on Pexels")

            return {
                "success": True,
                "images": images,
                "query": query,
                "total_results": len(images),
                "session_dir": str(session_dir) if download else None,
                "error": None,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Pexels: {e}")
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": f"API request failed: {str(e)}",
            }

        except Exception as e:
            logger.error(f"Unexpected error during Pexels search: {e}")
            return {
                "success": False,
                "images": [],
                "query": query,
                "error": str(e),
            }
