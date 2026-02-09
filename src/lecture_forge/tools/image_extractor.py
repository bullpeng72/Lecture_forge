"""
Image Extractor Tool - Extracts images from PDFs and web pages.
"""

import hashlib
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image

from lecture_forge.utils import logger


class PDFImageExtractorTool:
    """Tool for extracting images from PDF files."""

    name: str = "PDF Image Extractor"
    description: str = "Extracts images from PDF files"

    def __init__(self, output_dir: str = "./data/images"):
        """
        Initialize the image extractor.

        Args:
            output_dir: Directory to save extracted images
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Minimum image dimensions to filter out small icons/logos
        self.min_width = 200
        self.min_height = 200

    def run(self, pdf_path: str, session_id: str = "default") -> Dict:
        """
        Extract images from a PDF file.

        Args:
            pdf_path: Path to PDF file
            session_id: Session identifier for organizing images

        Returns:
            Extraction result with image paths and metadata
        """
        logger.info(f"Extracting images from PDF: {pdf_path}")

        try:
            # Create session directory
            session_dir = self.output_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # Check if file exists
            path = Path(pdf_path)
            if not path.exists():
                return {
                    "success": False,
                    "images": [],
                    "error": f"File not found: {pdf_path}",
                }

            # Open PDF
            doc = fitz.open(pdf_path)
            images = []
            extracted_hashes = set()  # For deduplication

            # Extract images from all pages
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    try:
                        # Get image XREF (reference)
                        xref = img[0]

                        # Extract image
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]

                        # Calculate hash for deduplication
                        image_hash = hashlib.md5(image_bytes).hexdigest()

                        if image_hash in extracted_hashes:
                            logger.debug(f"Skipping duplicate image: {image_hash}")
                            continue

                        # Load image to check dimensions
                        import io
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        width, height = pil_image.size

                        # Filter out small images
                        if width < self.min_width or height < self.min_height:
                            logger.debug(f"Skipping small image: {width}x{height}")
                            continue

                        # Generate filename
                        filename = f"page{page_num + 1}_img{img_index + 1}_{image_hash[:8]}.{image_ext}"
                        image_path = session_dir / filename

                        # Save image
                        with open(image_path, "wb") as f:
                            f.write(image_bytes)

                        # Store metadata
                        images.append({
                            "id": f"pdf_{image_hash[:12]}",
                            "path": str(image_path),
                            "filename": filename,
                            "source": pdf_path,
                            "page": page_num + 1,
                            "width": width,
                            "height": height,
                            "format": image_ext,
                            "size_bytes": len(image_bytes),
                            "hash": image_hash,
                        })

                        extracted_hashes.add(image_hash)

                    except Exception as e:
                        logger.warning(f"Error extracting image {img_index} from page {page_num + 1}: {e}")
                        continue

            doc.close()

            logger.info(f"Extracted {len(images)} images from PDF (after deduplication and filtering)")

            return {
                "success": True,
                "images": images,
                "total_extracted": len(images),
                "session_dir": str(session_dir),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error extracting images from PDF {pdf_path}: {e}")
            return {
                "success": False,
                "images": [],
                "error": str(e),
            }


class WebImageScraperTool:
    """Tool for scraping images from web pages."""

    name: str = "Web Image Scraper"
    description: str = "Scrapes images from web pages"

    def __init__(self, output_dir: str = "./data/images"):
        """
        Initialize the web image scraper.

        Args:
            output_dir: Directory to save scraped images
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Minimum image dimensions
        self.min_width = 200
        self.min_height = 200

    def run(self, url: str, soup, session_id: str = "default") -> Dict:
        """
        Extract images from a web page (requires BeautifulSoup object).

        Args:
            url: Source URL
            soup: BeautifulSoup object of the page
            session_id: Session identifier

        Returns:
            Extraction result with image URLs and metadata
        """
        logger.info(f"Extracting images from web page: {url}")

        try:
            from urllib.parse import urljoin
            import requests

            # Create session directory
            session_dir = self.output_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            images = []
            extracted_hashes = set()

            # Find all img tags
            img_tags = soup.find_all("img")

            for idx, img in enumerate(img_tags):
                try:
                    # Get image URL
                    img_url = img.get("src") or img.get("data-src")
                    if not img_url:
                        continue

                    # Make absolute URL
                    img_url = urljoin(url, img_url)

                    # Skip data URLs and very long URLs
                    if img_url.startswith("data:") or len(img_url) > 500:
                        continue

                    # Download image
                    response = requests.get(img_url, timeout=10)
                    response.raise_for_status()

                    image_bytes = response.content

                    # Calculate hash for deduplication
                    image_hash = hashlib.md5(image_bytes).hexdigest()

                    if image_hash in extracted_hashes:
                        continue

                    # Load image to check dimensions
                    import io
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    width, height = pil_image.size

                    # Filter out small images
                    if width < self.min_width or height < self.min_height:
                        continue

                    # Determine format
                    image_format = pil_image.format.lower() if pil_image.format else "jpg"

                    # Generate filename
                    filename = f"web_img{idx + 1}_{image_hash[:8]}.{image_format}"
                    image_path = session_dir / filename

                    # Save image
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    # Get alt text if available
                    alt_text = img.get("alt", "")

                    # Store metadata
                    images.append({
                        "id": f"web_{image_hash[:12]}",
                        "path": str(image_path),
                        "filename": filename,
                        "source": url,
                        "original_url": img_url,
                        "width": width,
                        "height": height,
                        "format": image_format,
                        "size_bytes": len(image_bytes),
                        "hash": image_hash,
                        "alt_text": alt_text,
                    })

                    extracted_hashes.add(image_hash)

                except Exception as e:
                    logger.warning(f"Error downloading image {img_url}: {e}")
                    continue

            logger.info(f"Extracted {len(images)} images from web page")

            return {
                "success": True,
                "images": images,
                "total_extracted": len(images),
                "session_dir": str(session_dir),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error extracting images from URL {url}: {e}")
            return {
                "success": False,
                "images": [],
                "error": str(e),
            }
