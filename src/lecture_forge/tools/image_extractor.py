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

                        # Detect content type for better image selection
                        content_type = self._classify_image_content_type(pil_image, quality_score)

                        # Apply IMAGE_MAX_WIDTH if configured
                        if width > Config.IMAGE_MAX_WIDTH:
                            aspect_ratio = height / width
                            new_width = Config.IMAGE_MAX_WIDTH
                            new_height = int(new_width * aspect_ratio)
                            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            width, height = pil_image.size
                            logger.debug(f"Resized image to {width}x{height}")

                        # Use configured image format
                        image_format = Config.IMAGE_FORMAT
                        filename = f"page{page_num + 1}_img{img_index + 1}_{image_hash[:8]}.{image_format}"
                        image_path = session_dir / filename

                        # Save image with configured format and high quality
                        import io
                        output_buffer = io.BytesIO()

                        # Use high quality settings for WebP
                        if image_format.lower() == 'webp':
                            pil_image.save(output_buffer, format='WEBP', quality=95, method=6)
                        else:
                            pil_image.save(output_buffer, format=image_format.upper(), quality=95)

                        image_bytes = output_buffer.getvalue()

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
                                "format": image_format,
                                "size_bytes": len(image_bytes),
                                "hash": image_hash,
                                "extraction_quality": quality_score,  # Store quality score
                                "content_type": content_type,  # Store content type (diagram, chart, etc.)
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

        Enhanced filtering - detects diagrams, charts, text-rich images, and filters out decorative elements.

        Args:
            pil_image: PIL Image object
            width: Image width
            height: Image height
            size_bytes: File size in bytes

        Returns:
            Quality score (0.0 ~ 1.0)
        """
        score = 0.0

        # 1. Size evaluation (15 points) - Prefer larger images
        if width >= 800 and height >= 600:
            score += 0.15
        elif width >= 600 and height >= 400:
            score += 0.12
        elif width >= 400 and height >= 300:
            score += 0.10
        else:
            score += 0.05

        # 2. Aspect ratio evaluation (15 points) - Prefer standard ratios
        if width > 0 and height > 0:
            aspect_ratio = width / height

            # Standard ratios (diagrams, charts, screenshots)
            if 0.5 <= aspect_ratio <= 2.0:
                score += 0.15
            elif 0.3 <= aspect_ratio <= 3.0:
                score += 0.10
            else:
                # Very wide or tall = likely decorative banner/sidebar
                score += 0.02

        # 3. Compression ratio check (20 points) - Detect solid colors
        if width > 0 and height > 0 and size_bytes > 0:
            pixels = width * height
            bytes_per_pixel = size_bytes / pixels

            # Detect solid color images (very low compression ratio)
            if bytes_per_pixel < 0.05:
                logger.debug(
                    f"      Low compression: {bytes_per_pixel:.4f} bpp " f"({size_bytes:,} bytes / {pixels:,} pixels)"
                )
                return 0.0  # Reject solid color images immediately

            # Normal range scoring
            if 0.2 <= bytes_per_pixel <= 1.5:
                score += 0.20
            elif 0.1 <= bytes_per_pixel <= 2.0:
                score += 0.15
            else:
                score += 0.05

        # 4. Content analysis (30 points) - Color diversity + edge density
        try:
            content_score = self._analyze_image_content_fast(pil_image)
            score += content_score * 0.30
        except Exception as e:
            logger.debug(f"      Content analysis skipped: {e}")
            score += 0.10  # Lower benefit of doubt

        # 5. 🆕 Meaningful content detection (20 points) - NEW!
        try:
            meaningful_score = self._detect_meaningful_content(pil_image, width, height)
            score += meaningful_score * 0.20

            # Bonus: If image is likely diagram/chart, boost score
            if meaningful_score >= 0.8:
                logger.debug(f"      ⭐ High-value content detected (diagram/chart/text)")
                score += 0.10  # Bonus for educational content
        except Exception as e:
            logger.debug(f"      Meaningful content detection skipped: {e}")
            score += 0.05

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

    def _detect_meaningful_content(self, pil_image: Image.Image, width: int, height: int) -> float:
        """
        Detect meaningful content patterns (diagrams, charts, text, technical illustrations).

        This helps identify educational/informative images vs decorative ones.

        Args:
            pil_image: PIL Image object
            width: Image width
            height: Image height

        Returns:
            Meaningful content score (0.0 ~ 1.0)
        """
        try:
            import numpy as np

            score = 0.0

            # Convert to RGB for analysis
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            # Resize for faster processing (max 300x300 for meaningful detection)
            analysis_img = pil_image.copy()
            analysis_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            img_array = np.array(analysis_img)

            # 1. Text/diagram indicator: High contrast regions (40%)
            contrast_score = self._detect_high_contrast_regions(img_array)
            score += contrast_score * 0.40

            # 2. Structured patterns: Detect lines/grids (30%)
            structure_score = self._detect_structured_patterns(img_array)
            score += structure_score * 0.30

            # 3. Color patterns: Technical diagrams often use limited color palette (30%)
            color_pattern_score = self._analyze_color_patterns(img_array)
            score += color_pattern_score * 0.30

            return min(1.0, score)

        except Exception as e:
            logger.debug(f"      Meaningful content detection error: {e}")
            return 0.5  # Neutral score on error

    def _detect_high_contrast_regions(self, img_array: "np.ndarray") -> float:
        """
        Detect high contrast regions that often indicate text or diagrams.

        Args:
            img_array: Image as numpy array

        Returns:
            Contrast score (0.0 ~ 1.0)
        """
        import numpy as np

        # Convert to grayscale
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # Calculate local contrast (using simple block-based method)
        h, w = gray.shape
        block_size = 10
        high_contrast_blocks = 0
        total_blocks = 0

        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = gray[i : i + block_size, j : j + block_size]
                block_std = np.std(block)

                # High local contrast = likely text or diagram edges
                if block_std > 40:
                    high_contrast_blocks += 1
                total_blocks += 1

        if total_blocks == 0:
            return 0.0

        contrast_ratio = high_contrast_blocks / total_blocks

        # Score based on contrast ratio
        if contrast_ratio >= 0.3:
            return 1.0  # Likely text or detailed diagram
        elif contrast_ratio >= 0.2:
            return 0.8
        elif contrast_ratio >= 0.1:
            return 0.6
        elif contrast_ratio >= 0.05:
            return 0.3
        else:
            return 0.1

    def _detect_structured_patterns(self, img_array: "np.ndarray") -> float:
        """
        Detect structured patterns like lines, grids, boxes (common in diagrams/charts).

        Args:
            img_array: Image as numpy array

        Returns:
            Structure score (0.0 ~ 1.0)
        """
        import numpy as np

        # Convert to grayscale
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # Detect horizontal and vertical lines using projection
        h, w = gray.shape

        # Horizontal line detection (project onto y-axis)
        h_projection = np.mean(gray, axis=1)
        h_variance = np.var(h_projection)

        # Vertical line detection (project onto x-axis)
        v_projection = np.mean(gray, axis=0)
        v_variance = np.var(v_projection)

        # High variance in projections = structured content (lines, grids)
        avg_variance = (h_variance + v_variance) / 2

        # Score based on variance
        if avg_variance >= 1500:
            return 1.0  # Strong grid/line structure
        elif avg_variance >= 1000:
            return 0.8
        elif avg_variance >= 500:
            return 0.6
        elif avg_variance >= 200:
            return 0.4
        else:
            return 0.2

    def _classify_image_content_type(self, pil_image: Image.Image, quality_score: float) -> str:
        """
        Classify image content type based on analysis results.

        Args:
            pil_image: PIL Image object
            quality_score: Overall quality score (0.0 ~ 1.0)

        Returns:
            Content type: "diagram", "chart", "screenshot", "technical", "photo", or "unknown"
        """
        try:
            import numpy as np

            # High quality score suggests meaningful content
            if quality_score < 0.4:
                return "unknown"

            # Convert to RGB for analysis
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            # Resize for faster processing
            analysis_img = pil_image.copy()
            analysis_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            img_array = np.array(analysis_img)

            # Detect content characteristics
            contrast_score = self._detect_high_contrast_regions(img_array)
            structure_score = self._detect_structured_patterns(img_array)
            color_pattern_score = self._analyze_color_patterns(img_array)

            # Classification logic based on scores
            # High structure + limited colors = diagram/chart
            if structure_score >= 0.7 and color_pattern_score >= 0.7:
                if contrast_score >= 0.7:
                    return "diagram"  # Technical diagram with text
                else:
                    return "chart"  # Chart/graph

            # High contrast + high structure = screenshot or technical illustration
            if contrast_score >= 0.8 and structure_score >= 0.6:
                return "screenshot"

            # High quality with mixed characteristics = technical content
            if quality_score >= 0.6:
                return "technical"

            # Lower quality but acceptable = photo or general image
            if quality_score >= 0.4:
                return "photo"

            return "unknown"

        except Exception as e:
            logger.debug(f"      Content type classification error: {e}")
            # Fallback based on quality score only
            if quality_score >= 0.7:
                return "technical"
            elif quality_score >= 0.5:
                return "photo"
            else:
                return "unknown"

    def _analyze_color_patterns(self, img_array: "np.ndarray") -> float:
        """
        Analyze color patterns - technical diagrams often use limited, distinct colors.

        Args:
            img_array: Image as numpy array

        Returns:
            Color pattern score (0.0 ~ 1.0)
        """
        import numpy as np

        # Flatten colors
        h, w, _ = img_array.shape
        pixels = img_array.reshape(-1, 3)

        # Calculate unique colors (with quantization to avoid counting similar colors)
        quantized = (pixels // 32) * 32  # Quantize to 8 levels per channel
        unique_colors = len(np.unique(quantized, axis=0))

        # Technical diagrams typically have 5-50 distinct colors
        # Photos typically have 100+ distinct colors
        # Solid/simple graphics have <5 colors

        if 10 <= unique_colors <= 60:
            return 1.0  # Ideal range for diagrams/charts
        elif 5 <= unique_colors <= 80:
            return 0.8
        elif 3 <= unique_colors <= 100:
            return 0.6
        elif unique_colors < 3:
            return 0.1  # Too simple = likely logo or solid color
        else:
            # Too many colors = likely photo or decorative
            # But could still be screenshot or complex diagram
            return 0.5


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
                    response = requests.get(img_url, timeout=Config.IMAGE_SEARCH_TIMEOUT)
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

                    # Apply IMAGE_MAX_WIDTH if configured
                    if width > Config.IMAGE_MAX_WIDTH:
                        aspect_ratio = height / width
                        new_width = Config.IMAGE_MAX_WIDTH
                        new_height = int(new_width * aspect_ratio)
                        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        width, height = pil_image.size

                    # Use configured image format
                    image_format = Config.IMAGE_FORMAT

                    # Generate filename
                    filename = f"web_img{idx + 1}_{image_hash[:8]}.{image_format}"
                    image_path = session_dir / filename

                    # Save image with configured format and high quality
                    import io
                    output_buffer = io.BytesIO()

                    # Use high quality settings for WebP
                    if image_format.lower() == 'webp':
                        pil_image.save(output_buffer, format='WEBP', quality=95, method=6)
                    else:
                        pil_image.save(output_buffer, format=image_format.upper(), quality=95)

                    image_bytes = output_buffer.getvalue()

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
