"""
Image Search Tool - Searches for images using Unsplash and Pexels APIs.
"""

import hashlib
from pathlib import Path
from typing import Dict

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"Unsplash API call failed (attempt {retry_state.attempt_number}/3), retrying..."
        ),
    )
    def run(
        self,
        query: str,
        per_page: int = None,
        orientation: str = "landscape",
        session_id: str = "default",
        download: bool = True,
    ) -> Dict:
        """
        Search for images on Unsplash with automatic retry on failures.

        Args:
            query: Search query
            per_page: Number of results (max 30, default from Config)
            orientation: Image orientation (landscape/portrait/squarish)
            session_id: Session identifier for organizing images
            download: Whether to download images

        Returns:
            Search results with image URLs and metadata
        """
        # Use config default if not specified
        if per_page is None:
            per_page = Config.IMAGE_SEARCH_PER_PAGE
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
                timeout=Config.IMAGE_SEARCH_TIMEOUT,
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
                                    timeout=Config.IMAGE_SEARCH_TIMEOUT,
                                )
                            except (requests.RequestException, TimeoutError) as e:
                                logger.debug(f"Failed to trigger Unsplash download endpoint: {e}")

                            # Download actual image
                            img_response = requests.get(image_url, timeout=Config.IMAGE_SEARCH_TIMEOUT)
                            img_response.raise_for_status()

                            image_bytes = img_response.content
                            image_hash = hashlib.md5(image_bytes).hexdigest()

                            # Process image with PIL to apply format and max width
                            from PIL import Image
                            import io
                            pil_image = Image.open(io.BytesIO(image_bytes))
                            width, height = pil_image.size

                            # Apply IMAGE_MAX_WIDTH if configured
                            if width > Config.IMAGE_MAX_WIDTH:
                                aspect_ratio = height / width
                                new_width = Config.IMAGE_MAX_WIDTH
                                new_height = int(new_width * aspect_ratio)
                                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                width, height = pil_image.size

                            # Use configured image format
                            image_format = Config.IMAGE_FORMAT
                            filename = f"unsplash_{image_id}_{image_hash[:8]}.{image_format}"
                            image_path = session_dir / filename

                            # Save with configured format
                            output_buffer = io.BytesIO()
                            pil_image.save(output_buffer, format=image_format.upper())
                            image_bytes = output_buffer.getvalue()

                            with open(image_path, "wb") as f:
                                f.write(image_bytes)

                            image_metadata["path"] = str(image_path)
                            image_metadata["filename"] = filename
                            image_metadata["size_bytes"] = len(image_bytes)
                            image_metadata["hash"] = image_hash
                            image_metadata["width"] = width  # Update with actual saved dimensions
                            image_metadata["height"] = height

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"Pexels API call failed (attempt {retry_state.attempt_number}/3), retrying..."
        ),
    )
    def run(
        self,
        query: str,
        per_page: int = None,
        orientation: str = "landscape",
        session_id: str = "default",
        download: bool = True,
    ) -> Dict:
        """
        Search for images on Pexels with automatic retry on failures.

        Args:
            query: Search query
            per_page: Number of results (max 80, default from Config)
            orientation: Image orientation (landscape/portrait/square)
            session_id: Session identifier for organizing images
            download: Whether to download images

        Returns:
            Search results with image URLs and metadata
        """
        # Use config default if not specified
        if per_page is None:
            per_page = Config.IMAGE_SEARCH_PER_PAGE
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
                timeout=Config.IMAGE_SEARCH_TIMEOUT,
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
                            img_response = requests.get(image_url, timeout=Config.IMAGE_SEARCH_TIMEOUT)
                            img_response.raise_for_status()

                            image_bytes = img_response.content
                            image_hash = hashlib.md5(image_bytes).hexdigest()

                            # Process image with PIL to apply format and max width
                            from PIL import Image
                            import io
                            pil_image = Image.open(io.BytesIO(image_bytes))
                            img_width, img_height = pil_image.size

                            # Apply IMAGE_MAX_WIDTH if configured
                            if img_width > Config.IMAGE_MAX_WIDTH:
                                aspect_ratio = img_height / img_width
                                new_width = Config.IMAGE_MAX_WIDTH
                                new_height = int(new_width * aspect_ratio)
                                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                img_width, img_height = pil_image.size

                            # Use configured image format
                            image_format = Config.IMAGE_FORMAT
                            filename = f"pexels_{image_id}_{image_hash[:8]}.{image_format}"
                            image_path = session_dir / filename

                            # Save with configured format
                            output_buffer = io.BytesIO()
                            pil_image.save(output_buffer, format=image_format.upper())
                            image_bytes = output_buffer.getvalue()

                            with open(image_path, "wb") as f:
                                f.write(image_bytes)

                            image_metadata["path"] = str(image_path)
                            image_metadata["filename"] = filename
                            image_metadata["size_bytes"] = len(image_bytes)
                            image_metadata["hash"] = image_hash
                            image_metadata["width"] = img_width  # Update with actual saved dimensions
                            image_metadata["height"] = img_height

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
