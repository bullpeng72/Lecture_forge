"""
Image Search Tool - Searches for images using Unsplash and Pexels APIs.
"""

import hashlib
import io
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from PIL import Image

from lecture_forge.config import Config
from lecture_forge.utils import logger
from lecture_forge.utils.retry import make_api_retry


class BaseImageSearchTool:
    """Base class for image search tools with shared download/save logic."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the image search tool.

        Args:
            output_dir: Directory to save downloaded images (defaults to Config.DATA_DIR/images)
        """
        if output_dir is None:
            output_dir = str(Config.DATA_DIR / "images")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _download_and_save_image(
        self,
        image_url: str,
        image_id: str,
        prefix: str,
        session_dir: Path,
        extra_headers: Optional[dict] = None,
    ) -> Tuple[bytes, int, int, str, str]:
        """
        Download an image, resize if needed, and save to disk.

        Args:
            image_url: URL of the image to download
            image_id: Unique identifier for the image (used in filename)
            prefix: Filename prefix (e.g. "unsplash", "pexels")
            session_dir: Directory to save the file into
            extra_headers: Optional HTTP headers for the download request

        Returns:
            Tuple of (image_bytes, width, height, filename, md5_hash)
        """
        kwargs: dict = {"timeout": Config.IMAGE_SEARCH_TIMEOUT}
        if extra_headers:
            kwargs["headers"] = extra_headers

        img_response = requests.get(image_url, **kwargs)
        img_response.raise_for_status()

        image_bytes = img_response.content
        image_hash = hashlib.md5(image_bytes).hexdigest()

        pil_image = Image.open(io.BytesIO(image_bytes))
        width, height = pil_image.size

        if width > Config.IMAGE_MAX_WIDTH:
            aspect_ratio = height / width
            new_width = Config.IMAGE_MAX_WIDTH
            new_height = int(new_width * aspect_ratio)
            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            width, height = pil_image.size

        image_format = Config.IMAGE_FORMAT
        filename = f"{prefix}_{image_id}_{image_hash[:8]}.{image_format}"
        image_path = session_dir / filename

        output_buffer = io.BytesIO()
        if image_format.lower() == "webp":
            pil_image.save(output_buffer, format="WEBP", quality=95, method=6)
        else:
            pil_image.save(output_buffer, format=image_format.upper(), quality=95)

        image_bytes = output_buffer.getvalue()
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        return image_bytes, width, height, filename, image_hash

    def _error_response(self, query: str, error_msg: str) -> Dict:
        """Return a standardised error result dict."""
        return {
            "success": False,
            "images": [],
            "query": query,
            "error": error_msg,
        }


class UnsplashSearchTool(BaseImageSearchTool):
    """Tool for searching images on Unsplash."""

    name: str = "Unsplash Search"
    description: str = "Searches for high-quality, free-to-use images on Unsplash"

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the Unsplash search tool.

        Args:
            output_dir: Directory to save downloaded images (defaults to Config.DATA_DIR/images)
        """
        super().__init__(output_dir)
        self.access_key = Config.UNSPLASH_ACCESS_KEY
        self.api_url = "https://api.unsplash.com/search/photos"

    @make_api_retry("Unsplash")
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
        if per_page is None:
            per_page = Config.IMAGE_SEARCH_PER_PAGE
        logger.info(f"Searching Unsplash for: {query}")

        if not self.access_key:
            return self._error_response(query, "UNSPLASH_ACCESS_KEY not configured in .env")

        try:
            headers = {"Authorization": f"Client-ID {self.access_key}"}
            params = {
                "query": query,
                "per_page": min(per_page, 30),  # API max is 30
                "orientation": orientation,
            }

            response = requests.get(
                self.api_url,
                params=params,
                headers=headers,
                timeout=Config.IMAGE_SEARCH_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            images = []
            session_dir = None

            if "results" in data:
                if download:
                    session_dir = self.output_dir / session_id
                    session_dir.mkdir(parents=True, exist_ok=True)

                for idx, photo in enumerate(data["results"]):
                    try:
                        image_url = photo["urls"]["full"]
                        download_url = photo["links"]["download_location"]
                        image_id = photo["id"]

                        image_metadata = {
                            "id": f"unsplash_{image_id}",
                            "url": image_url,
                            "download_url": download_url,
                            "description": photo.get("description") or photo.get("alt_description", ""),
                            "width": photo["width"],
                            "height": photo["height"],
                            "color": photo.get("color", "#000000"),
                            "author": photo["user"]["name"],
                            "author_username": photo["user"]["username"],
                            "attribution": f"Photo by {photo['user']['name']} on Unsplash",
                            "license": "Unsplash License",
                            "source": "unsplash",
                            "query": query,
                        }

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

                            image_bytes, width, height, filename, image_hash = (
                                self._download_and_save_image(
                                    image_url, image_id, "unsplash", session_dir, headers
                                )
                            )
                            image_metadata.update({
                                "path": str(session_dir / filename),
                                "filename": filename,
                                "size_bytes": len(image_bytes),
                                "hash": image_hash,
                                "width": width,
                                "height": height,
                            })

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
            return self._error_response(query, f"API request failed: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error during Unsplash search: {e}")
            return self._error_response(query, str(e))


class PexelsSearchTool(BaseImageSearchTool):
    """Tool for searching images on Pexels."""

    name: str = "Pexels Search"
    description: str = "Searches for high-quality, free-to-use images on Pexels"

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the Pexels search tool.

        Args:
            output_dir: Directory to save downloaded images (defaults to Config.DATA_DIR/images)
        """
        super().__init__(output_dir)
        self.api_key = Config.PEXELS_API_KEY
        self.api_url = "https://api.pexels.com/v1/search"

    @make_api_retry("Pexels")
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
        if per_page is None:
            per_page = Config.IMAGE_SEARCH_PER_PAGE
        logger.info(f"Searching Pexels for: {query}")

        if not self.api_key:
            logger.warning("PEXELS_API_KEY not configured, skipping Pexels search")
            return self._error_response(query, "PEXELS_API_KEY not configured in .env")

        try:
            headers = {"Authorization": self.api_key}
            params = {
                "query": query,
                "per_page": min(per_page, 80),  # API max is 80
                "orientation": orientation,
            }

            response = requests.get(
                self.api_url,
                params=params,
                headers=headers,
                timeout=Config.IMAGE_SEARCH_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            images = []
            session_dir = None

            if "photos" in data:
                if download:
                    session_dir = self.output_dir / session_id
                    session_dir.mkdir(parents=True, exist_ok=True)

                for idx, photo in enumerate(data["photos"]):
                    try:
                        image_url = photo["src"]["original"]
                        image_id = str(photo["id"])

                        image_metadata = {
                            "id": f"pexels_{image_id}",
                            "url": image_url,
                            "description": photo.get("alt", ""),
                            "width": photo["width"],
                            "height": photo["height"],
                            "photographer": photo["photographer"],
                            "photographer_url": photo["photographer_url"],
                            "attribution": f"Photo by {photo['photographer']} on Pexels",
                            "license": "Pexels License",
                            "source": "pexels",
                            "query": query,
                        }

                        if download:
                            image_bytes, width, height, filename, image_hash = (
                                self._download_and_save_image(
                                    image_url, image_id, "pexels", session_dir
                                )
                            )
                            image_metadata.update({
                                "path": str(session_dir / filename),
                                "filename": filename,
                                "size_bytes": len(image_bytes),
                                "hash": image_hash,
                                "width": width,
                                "height": height,
                            })

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
            return self._error_response(query, f"API request failed: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error during Pexels search: {e}")
            return self._error_response(query, str(e))
