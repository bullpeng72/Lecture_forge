"""
Image Extractor Tool - Extracts images from PDFs and web pages.
"""

import hashlib
from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

from lecture_forge.config import Config
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

        # Load settings from Config (.env)
        self.min_width = Config.IMAGE_MIN_WIDTH
        self.min_height = Config.IMAGE_MIN_HEIGHT
        self.quality_threshold = Config.IMAGE_EXTRACTION_QUALITY_THRESHOLD

        # Statistics tracking
        self.stats = {
            "total_found": 0,
            "size_filtered": 0,
            "quality_filtered": 0,
            "duplicates": 0,
            "extracted": 0,
        }

        # Log loaded settings
        logger.debug(f"PDF Image Extractor initialized:")
        logger.debug(f"  Min size: {self.min_width}x{self.min_height}")
        logger.debug(f"  Quality threshold: {self.quality_threshold}")

    def run(self, pdf_path: str, session_id: str = "default") -> Dict:
        """
        Extract images from a PDF file with quality filtering.

        Args:
            pdf_path: Path to PDF file
            session_id: Session identifier for organizing images

        Returns:
            Extraction result with image paths and metadata
        """
        logger.info(f"Extracting images from PDF: {pdf_path}")

        try:
            # Reset statistics
            self.stats = {
                "total_found": 0,
                "size_filtered": 0,
                "quality_filtered": 0,
                "duplicates": 0,
                "extracted": 0,
            }

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
                        self.stats["total_found"] += 1

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
                            self.stats["duplicates"] += 1
                            continue

                        # Load image to check dimensions
                        import io

                        pil_image = Image.open(io.BytesIO(image_bytes))
                        width, height = pil_image.size

                        # Filter out small images
                        if width < self.min_width or height < self.min_height:
                            logger.debug(f"Skipping small image: {width}x{height}")
                            self.stats["size_filtered"] += 1
                            continue

                        # ✨ NEW: Quality check to filter out meaningless images
                        quality_score = self._evaluate_image_quality(pil_image, width, height, len(image_bytes))

                        if quality_score < self.quality_threshold:
                            logger.debug(
                                f"Skipping low-quality image (page {page_num + 1}, "
                                f"score: {quality_score:.2f}): likely solid color or empty"
                            )
                            self.stats["quality_filtered"] += 1
                            continue

                        # Generate filename
                        filename = f"page{page_num + 1}_img{img_index + 1}_{image_hash[:8]}.{image_ext}"
                        image_path = session_dir / filename

                        # Save image
                        with open(image_path, "wb") as f:
                            f.write(image_bytes)

                        # Store metadata
                        images.append(
                            {
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
                                "extraction_quality": quality_score,  # Store quality score
                            }
                        )

                        extracted_hashes.add(image_hash)
                        self.stats["extracted"] += 1

                    except Exception as e:
                        logger.warning(f"Error extracting image {img_index} from page {page_num + 1}: {e}")
                        continue

            doc.close()

            # Log statistics
            logger.info(f"📊 PDF Image Extraction Statistics:")
            logger.info(f"   • Total found: {self.stats['total_found']}")
            logger.info(f"   • Filtered (size): {self.stats['size_filtered']}")
            logger.info(f"   • Filtered (quality): {self.stats['quality_filtered']}")
            logger.info(f"   • Duplicates: {self.stats['duplicates']}")
            logger.info(f"   • ✅ Extracted: {self.stats['extracted']}")

            # Calculate savings
            if self.stats["total_found"] > 0:
                filter_rate = (self.stats["size_filtered"] + self.stats["quality_filtered"]) / self.stats["total_found"] * 100
                logger.info(f"   • 💰 Filtered out: {filter_rate:.1f}% (saves Vision API costs)")

            return {
                "success": True,
                "images": images,
                "total_extracted": len(images),
                "session_dir": str(session_dir),
                "statistics": self.stats,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error extracting images from PDF {pdf_path}: {e}")
            return {
                "success": False,
                "images": [],
                "error": str(e),
            }

    def _evaluate_image_quality(self, pil_image: Image.Image, width: int, height: int, size_bytes: int) -> float:
        """
        Evaluate image quality to filter out meaningless images during extraction.

        Conservative filtering - only reject obvious junk (solid colors, empty images).

        Args:
            pil_image: PIL Image object
            width: Image width
            height: Image height
            size_bytes: File size in bytes

        Returns:
            Quality score (0.0 ~ 1.0)
        """
        score = 0.0

        # 1. Size evaluation (20 points) - Already passed min size check
        if width >= 800 and height >= 600:
            score += 0.20
        elif width >= 400 and height >= 300:
            score += 0.15
        else:
            score += 0.10

        # 2. Aspect ratio evaluation (20 points)
        if width > 0 and height > 0:
            aspect_ratio = width / height

            if 0.5 <= aspect_ratio <= 2.0:
                score += 0.20
            elif 0.3 <= aspect_ratio <= 3.0:
                score += 0.15
            else:
                score += 0.05

        # 3. Compression ratio check (30 points) - Key metric for detecting solid colors
        if width > 0 and height > 0 and size_bytes > 0:
            pixels = width * height
            bytes_per_pixel = size_bytes / pixels

            # Detect solid color images (very low compression ratio)
            if bytes_per_pixel < 0.05:
                # Extremely low bytes per pixel = solid color or gradient
                logger.debug(
                    f"      Low compression: {bytes_per_pixel:.4f} bpp " f"({size_bytes:,} bytes / {pixels:,} pixels)"
                )
                return 0.0  # Reject solid color images immediately

            # Normal range scoring
            if 0.2 <= bytes_per_pixel <= 1.5:
                score += 0.30
            elif 0.1 <= bytes_per_pixel <= 2.0:
                score += 0.20
            else:
                score += 0.10

        # 4. Content analysis (30 points) - Optional advanced check
        try:
            content_score = self._analyze_image_content_fast(pil_image)
            score += content_score * 0.30
        except Exception as e:
            logger.debug(f"      Content analysis skipped: {e}")
            # Give benefit of doubt if analysis fails
            score += 0.15

        return min(1.0, score)

    def _analyze_image_content_fast(self, pil_image: Image.Image) -> float:
        """
        Fast content analysis for extraction phase.

        Only performs lightweight checks to avoid slowing down extraction.

        Args:
            pil_image: PIL Image object

        Returns:
            Content quality score (0.0 ~ 1.0)
        """
        try:
            import numpy as np

            # Convert to RGB
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            # Resize for faster processing (max 200x200 for extraction phase)
            pil_image.thumbnail((200, 200), Image.Resampling.LANCZOS)

            # Convert to numpy array
            img_array = np.array(pil_image)

            # Fast checks only:
            # 1. Color diversity (60%)
            color_score = self._check_color_diversity_fast(img_array)

            # 2. Edge density (40%)
            edge_score = self._check_edge_density_fast(img_array)

            total_score = color_score * 0.60 + edge_score * 0.40

            return total_score

        except ImportError:
            # numpy not available - skip advanced checks
            return 0.5
        except Exception as e:
            logger.debug(f"      Fast content analysis error: {e}")
            return 0.5

    def _check_color_diversity_fast(self, img_array: "np.ndarray") -> float:
        """
        Fast color diversity check using standard deviation.

        Args:
            img_array: Image as numpy array

        Returns:
            Color diversity score (0.0 ~ 1.0)
        """
        import numpy as np

        # Calculate std dev for each channel
        std_r = np.std(img_array[:, :, 0])
        std_g = np.std(img_array[:, :, 1])
        std_b = np.std(img_array[:, :, 2])
        avg_std = (std_r + std_g + std_b) / 3.0

        # Score based on standard deviation
        if avg_std >= 50:
            return 1.0
        elif avg_std >= 30:
            return 0.7
        elif avg_std >= 15:
            return 0.4
        elif avg_std >= 5:
            return 0.2
        else:
            # Very low std = solid color
            return 0.0

    def _check_edge_density_fast(self, img_array: "np.ndarray") -> float:
        """
        Fast edge density check using simple gradient.

        Args:
            img_array: Image as numpy array

        Returns:
            Edge density score (0.0 ~ 1.0)
        """
        import numpy as np

        # Convert to grayscale
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # Simple gradient calculation (faster than PIL filters)
        grad_x = np.abs(np.diff(gray, axis=1))
        grad_y = np.abs(np.diff(gray, axis=0))

        # Calculate edge density
        edge_pixels = (grad_x > 20).sum() + (grad_y > 20).sum()
        total_pixels = gray.size
        edge_density = edge_pixels / total_pixels

        # Score based on edge density
        if edge_density >= 0.15:
            return 1.0
        elif edge_density >= 0.08:
            return 0.7
        elif edge_density >= 0.04:
            return 0.5
        elif edge_density >= 0.02:
            return 0.3
        else:
            # Very low edge density = blank/empty
            return 0.0


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

        # Load settings from Config (.env)
        self.min_width = Config.IMAGE_MIN_WIDTH
        self.min_height = Config.IMAGE_MIN_HEIGHT

        # Log loaded settings
        logger.debug(f"Web Image Scraper initialized:")
        logger.debug(f"  Min size: {self.min_width}x{self.min_height}")

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
                    images.append(
                        {
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
                        }
                    )

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
