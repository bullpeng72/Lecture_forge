"""
Image Selector - Handles intelligent image selection for lecture sections.
"""

from pathlib import Path
from typing import List, Dict

import numpy as np
from PIL import Image

from lecture_forge.config import Config
from lecture_forge.models.curriculum import Section
from lecture_forge.models.lecture import ImageReference
from lecture_forge.utils import logger


class ImageSelector:
    """Handles image selection with location-based matching and quality scoring."""

    def __init__(self, keyword_expander=None):
        """
        Initialize ImageSelector.
        
        Args:
            keyword_expander: Function to expand keywords (from parent agent)
        """
        self.image_page_map = None
        self._expand_keywords = keyword_expander or (lambda topic, keyword_map: [topic])

    def select_images(
        self, section: Section, available_images: List[dict], context_metadatas: List[dict] = None
    ) -> List[ImageReference]:
        """Select images for a section (wrapper for compatibility)."""
        return self._select_images(section, available_images, context_metadatas)

    def _select_images(
        self, section: Section, available_images: List[dict], context_metadatas: List[dict] = None
    ) -> List[ImageReference]:
        """Select relevant images for section with improved location-based matching.

        Improved multi-phase approach:
        Phase 0: Location-based matching (Vision AI free)
            - Calculate page importance from RAG context (frequency + rank)
            - Evaluate image quality (size, aspect ratio, file size)
            - Smart selection (max 1 per page, global deduplication)
            - Adjacent page expansion if needed
        Phase 1: Search images (Pexels/Unsplash)
            - Keyword-based matching with description/query
        Phase 2: PDF images with descriptions
            - Fallback for PDF images with Vision AI descriptions

        Args:
            section: Section to select images for
            available_images: All available images
            context_metadatas: Metadata from RAG chunks (contains page numbers)

        Returns:
            List of selected image references
        """
        selected = []

        if not available_images:
            logger.warning(f"  ⚠️  No images available for section: {section.title}")
            return selected

        # Calculate max images based on section length (1 per 10 minutes, min 2)
        max_images = max(2, section.estimated_time // 10)
        logger.info(f"  🖼️  Selecting up to {max_images} images for section: {section.title}")

        # Separate PDF images from search images
        pdf_images = [img for img in available_images if img.get("source", "").endswith(".pdf")]
        search_images = [img for img in available_images if not img.get("source", "").endswith(".pdf")]

        logger.debug(f"     Available: {len(search_images)} search images, {len(pdf_images)} PDF images")

        # Phase 0: Location-based matching (NEW!)
        location_matched = 0
        if context_metadatas and pdf_images:
            logger.debug(f"     📍 Trying location-based matching...")
            location_matched_images = self._match_images_by_location(context_metadatas, pdf_images, max_images)
            selected.extend(location_matched_images)
            location_matched = len(location_matched_images)
            logger.info(f"     ✅ Location-based: {location_matched} images matched")

        # Korean-English keyword mapping
        keyword_map = self._get_keyword_translations()

        # Phase 1: Match search images (have descriptions/queries)
        matched_count = 0
        for img in search_images:
            if len(selected) >= max_images:
                break

            img_desc = img.get("description", "").lower()
            img_query = img.get("query", "").lower()
            img_alt = img.get("alt_text", "").lower()

            # Combine all text for matching
            img_text = f"{img_desc} {img_query} {img_alt}"

            # Skip if no text
            if not img_text.strip():
                continue

            # Try to match with section topics
            matched = False
            matched_topic = None

            for topic in section.topics:
                search_keywords = self._expand_keywords(topic, keyword_map)

                for keyword in search_keywords:
                    if keyword.lower() in img_text:
                        matched = True
                        matched_topic = topic
                        matched_count += 1
                        logger.debug(f"     ✅ Search image match #{matched_count}: '{keyword}' in {img.get('id', 'unknown')}")
                        break

                if matched:
                    break

            if matched:
                selected.append(
                    ImageReference(
                        image_id=img.get("id", ""),
                        path=img.get("path", ""),
                        description=img.get("description", "") or img.get("query", "") or img_alt,
                        caption=matched_topic,
                        attribution=img.get("attribution", ""),
                    )
                )

        # Phase 2: Try to match PDF images (if they have descriptions)
        pdf_matched = 0
        pdf_skipped = 0

        if len(selected) < max_images and pdf_images:
            logger.debug(f"     📄 Trying to match PDF images...")

            for img in pdf_images:
                if len(selected) >= max_images:
                    break

                img_desc = img.get("description", "").lower()
                img_alt = img.get("alt_text", "").lower()

                # PDF images may have description if Vision AI was used
                if img_desc:
                    # Try matching with description
                    matched = False
                    matched_topic = None

                    for topic in section.topics:
                        search_keywords = self._expand_keywords(topic, keyword_map)

                        for keyword in search_keywords:
                            if keyword.lower() in img_desc:
                                matched = True
                                matched_topic = topic
                                pdf_matched += 1
                                logger.debug(f"     ✅ PDF image match: '{keyword}' in page {img.get('page', '?')}")
                                break

                        if matched:
                            break

                    if matched:
                        selected.append(
                            ImageReference(
                                image_id=img.get("id", ""),
                                path=img.get("path", ""),
                                description=img.get("description", ""),
                                caption=f"{matched_topic} (PDF page {img.get('page', '?')})",
                                attribution=f"Source: {Path(img['source']).name}, page {img['page']}",
                            )
                        )
                else:
                    # PDF image without description - can't match without Vision AI
                    pdf_skipped += 1

        # Summary logging
        logger.info(f"     📊 Selected {len(selected)}/{max_images} images")
        logger.debug(f"        - Location-based: {location_matched}")
        logger.debug(f"        - Search images: {matched_count}")
        logger.debug(f"        - PDF images: {pdf_matched}")

        if pdf_skipped > 0:
            logger.info(f"     💡 {pdf_skipped} PDF images skipped (no descriptions)")
            logger.info(f"        Tip: Use 'lecture-forge improve --enhance-pdf-images' to add descriptions")

        if len(selected) == 0 and available_images:
            logger.warning(f"     ⚠️  No matching images found for topics: {section.topics[:3]}")

        return selected

    def _match_images_by_location(
        self, context_metadatas: List[dict], pdf_images: List[dict], max_images: int
    ) -> List[ImageReference]:
        """
        Improved location-based image matching (Vision AI free).

        Key improvements:
        1. Page importance calculation (frequency + rank)
        2. Image quality filtering (size, aspect ratio)
        3. Smart selection (max 1 per page, deduplication)
        4. Adjacent page expansion if needed

        Args:
            context_metadatas: Metadata from RAG chunks (contains source and page_number)
            pdf_images: Available PDF images
            max_images: Maximum images to select

        Returns:
            List of matched image references
        """
        selected = []

        # 1. Calculate page importance from RAG context
        page_importance = self._calculate_page_importance(context_metadatas)

        if not page_importance:
            logger.debug(f"        No PDF page info in RAG context")
            return selected

        # 2. Load image-page map
        image_page_map = self._load_image_page_map()
        if not image_page_map:
            logger.debug(f"        No image-page map found")
            return selected

        # 3. Collect candidate images with scoring
        candidates = []

        for source, page_scores in page_importance.items():
            if source not in image_page_map:
                continue

            # Process pages in importance order
            for page_num, importance_score in page_scores:
                page_str = str(page_num)
                if page_str not in image_page_map[source]:
                    continue

                page_images = image_page_map[source][page_str]

                # Evaluate images from this page
                for idx, img_info in enumerate(page_images):
                    # Find full image object
                    full_img = next((img for img in pdf_images if img.get("id") == img_info["id"]), None)

                    if not full_img:
                        continue

                    # Quality check (Vision AI free)
                    quality_score = self._evaluate_image_quality_simple(full_img)

                    if quality_score < Config.IMAGE_SELECTION_QUALITY_THRESHOLD:
                        logger.debug(
                            f"           ⏭️  Skip {full_img.get('id', 'unknown')} "
                            f"(quality: {quality_score:.2f}, threshold: {Config.IMAGE_SELECTION_QUALITY_THRESHOLD})"
                        )
                        continue

                    # Calculate final score with content-type-aware weighting
                    content_type = full_img.get("content_type", "unknown")

                    # Adjust weights based on content type
                    # Diagrams/charts get higher quality weight (more important than page location)
                    if content_type in ["diagram", "chart"]:
                        quality_weight = Config.IMAGE_WEIGHT_QUALITY  # Increase quality importance
                        importance_weight = Config.IMAGE_WEIGHT_IMPORTANCE
                        position_weight = Config.IMAGE_WEIGHT_POSITION
                    elif content_type in ["screenshot", "technical"]:
                        quality_weight = 0.25
                        importance_weight = 0.65
                        position_weight = 0.10
                    else:
                        quality_weight = 0.20  # Default
                        importance_weight = 0.70
                        position_weight = 0.10

                    final_score = (
                        importance_score * importance_weight  # Page importance
                        + quality_score * quality_weight     # Image quality (includes content type bonus)
                        + (1.0 / (idx + 1)) * position_weight  # Position in page
                    )

                    candidates.append(
                        {
                            "image": full_img,
                            "score": final_score,
                            "page": page_num,
                            "source": source,
                            "page_importance": importance_score,
                            "quality": quality_score,
                        }
                    )

        # 4. Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # 5. Smart selection with constraints
        selected = self._smart_select_images(candidates, max_images)

        # 6. If not enough images, expand to adjacent pages
        if len(selected) < max_images:
            selected = self._expand_to_adjacent_pages(selected, max_images, page_importance, image_page_map, pdf_images)

        logger.info(f"     ✅ Location-based: {len(selected)} images matched")

        return selected

    def _load_image_page_map(self) -> dict:
        """Load image-page mapping from JSON file.

        Returns:
            Image-page map dictionary, or empty dict if not found
        """
        import json
        from lecture_forge.config import Config

        try:
            # Try to find the most recent session's image map
            images_dir = Path(Config.DATA_DIR) / "images"
            if not images_dir.exists():
                return {}

            # Find all session directories with image_page_map.json
            map_files = list(images_dir.glob("*/image_page_map.json"))
            if not map_files:
                return {}

            # Use the most recent one
            latest_map_file = max(map_files, key=lambda p: p.stat().st_mtime)

            with open(latest_map_file, "r", encoding="utf-8") as f:
                image_page_map = json.load(f)

            logger.debug(f"        Loaded image-page map from {latest_map_file.name}")
            return image_page_map

        except Exception as e:
            logger.debug(f"        Failed to load image-page map: {e}")
            return {}

    def _calculate_page_importance(self, context_metadatas: List[dict]) -> dict:
        """
        Calculate page importance from RAG context.

        Importance = Frequency (70%) + Rank (30%)

        Args:
            context_metadatas: Metadata from RAG query results

        Returns:
            {source: [(page_num, importance_score), ...]} (sorted by importance)
        """
        from collections import defaultdict, Counter

        # Collect page info by source
        source_pages = defaultdict(list)

        for rank, metadata in enumerate(context_metadatas):
            if not metadata:
                continue

            source = metadata.get("source", "")
            page_num = metadata.get("page_number")

            if source.endswith(".pdf") and page_num is not None:
                source_pages[source].append({"page": page_num, "rank": rank})  # Position in RAG results (0 = best)

        # Calculate importance for each page
        page_importance = {}

        for source, pages_info in source_pages.items():
            # Count frequency
            page_freq = Counter(p["page"] for p in pages_info)
            max_freq = max(page_freq.values()) if page_freq else 1

            # Calculate score for each page
            page_scores = {}

            for page_num in page_freq:
                # Frequency score (normalized)
                freq_score = page_freq[page_num] / max_freq

                # Rank score (best rank for this page)
                ranks = [p["rank"] for p in pages_info if p["page"] == page_num]
                best_rank = min(ranks)
                rank_score = 1.0 - (best_rank / len(context_metadatas))

                # Final importance (frequency 70% + rank 30%)
                importance = freq_score * 0.7 + rank_score * 0.3

                page_scores[page_num] = importance

            # Sort by importance
            sorted_pages = sorted(page_scores.items(), key=lambda x: x[1], reverse=True)

            page_importance[source] = sorted_pages

        # Log top pages
        logger.debug(f"        📊 Page importance calculated:")
        for source, pages in page_importance.items():
            top_pages = pages[:3]
            logger.debug(f"           {Path(source).name}: {[(p, f'{s:.2f}') for p, s in top_pages]}")

        return page_importance

    def _evaluate_image_quality_simple(self, image: dict) -> float:
        """
        Enhanced image quality evaluation with content type awareness.

        Priority system:
        1. Use extraction_quality if available (from enhanced extraction algorithm)
        2. Apply content_type bonus (diagrams/charts prioritized)
        3. Fallback to basic quality evaluation if no extraction_quality

        Criteria:
        - Size: Is it large enough?
        - Aspect ratio: Is it in normal range?
        - File size: Not too small?
        - Compression ratio: Meaningful content vs empty space?
        - Content type: Diagram/chart/screenshot detection
        - Extraction quality: Pre-calculated quality score

        Args:
            image: Image metadata dict

        Returns:
            Quality score (0.0 ~ 1.0)
        """
        # ✨ NEW: Use pre-calculated extraction_quality if available
        extraction_quality = image.get("extraction_quality")
        content_type = image.get("content_type", "unknown")

        if extraction_quality is not None:
            # Use the enhanced quality score from extraction phase
            base_score = extraction_quality

            # Apply content type bonus
            content_bonus = self._get_content_type_bonus(content_type)
            final_score = min(1.0, base_score + content_bonus)

            logger.debug(
                f"           📊 Quality (enhanced): {extraction_quality:.2f} "
                f"+ type_bonus({content_type})={content_bonus:.2f} "
                f"= {final_score:.2f}"
            )

            return final_score

        # Fallback: Calculate quality if extraction_quality not available
        score = 0.0

        width = image.get("width", 0)
        height = image.get("height", 0)
        size_bytes = image.get("size_bytes", 0)
        img_path = image.get("path", "")

        # 1. Size evaluation (25 points)
        if width >= 800 and height >= 600:
            score += 0.25
        elif width >= 600 and height >= 400:
            score += 0.20
        elif width >= 400 and height >= 300:
            score += 0.15
        elif width >= 200 and height >= 200:
            score += 0.08
        else:
            return 0.0  # Too small - reject immediately

        # 2. Aspect ratio evaluation (20 points)
        if width > 0 and height > 0:
            aspect_ratio = width / height

            # Normal range: 0.5 ~ 2.0 (portrait 2:1 ~ landscape 2:1)
            if 0.7 <= aspect_ratio <= 1.5:
                score += 0.20  # Ideal ratio
            elif 0.5 <= aspect_ratio <= 2.0:
                score += 0.15  # Acceptable range
            elif 0.3 <= aspect_ratio <= 3.0:
                score += 0.08  # Slightly extreme
            else:
                return 0.0  # Too extreme - reject

        # 3. File size evaluation (15 points)
        if size_bytes >= 100_000:  # >= 100KB
            score += 0.15
        elif size_bytes >= 50_000:  # >= 50KB
            score += 0.12
        elif size_bytes >= 10_000:  # >= 10KB
            score += 0.08
        else:
            score += 0.0  # Very small file (likely icon/logo)

        # 4. Compression ratio check (15 points)
        # Meaningful images have higher compression ratio (more details)
        if width > 0 and height > 0 and size_bytes > 0:
            pixels = width * height
            bytes_per_pixel = size_bytes / pixels

            # Good range: 0.1 ~ 2.0 bytes per pixel
            # Too low = solid color or empty, Too high = uncompressed/bloated
            if 0.2 <= bytes_per_pixel <= 1.5:
                score += 0.15
            elif 0.1 <= bytes_per_pixel <= 2.0:
                score += 0.10
            elif bytes_per_pixel < 0.05:
                # Very low bytes per pixel = likely solid color box
                logger.debug(f"           ⏭️  Low compression ratio: {bytes_per_pixel:.4f} bpp - likely empty/solid")
                return 0.0  # Reject solid color images
            else:
                score += 0.05

        # 5. Advanced content analysis (25 points) - Only if image file exists
        if img_path and Path(img_path).exists():
            try:
                content_score = self._analyze_image_content(img_path)
                score += content_score * 0.25
            except Exception as e:
                logger.debug(f"           ⚠️  Content analysis failed: {e}")
                # If analysis fails, give benefit of doubt with partial score
                score += 0.10

        return min(1.0, score)

    def _get_content_type_bonus(self, content_type: str) -> float:
        """
        Get bonus score based on content type.

        Educational priority:
        - diagram: Highest priority (technical diagrams, flowcharts, architecture)
        - chart: High priority (graphs, data visualizations)
        - screenshot: Medium-high priority (UI examples, demos)
        - technical: Medium priority (technical illustrations)
        - photo: Low priority (general photos)
        - unknown: No bonus

        Args:
            content_type: Content type classification

        Returns:
            Bonus score (0.0 ~ 0.15)
        """
        bonuses = {
            "diagram": 0.15,      # Highest - technical diagrams
            "chart": 0.12,        # High - data visualizations
            "screenshot": 0.10,   # Medium-high - UI examples
            "technical": 0.08,    # Medium - technical content
            "photo": 0.03,        # Low - general photos
            "unknown": 0.0,       # No bonus
        }

        return bonuses.get(content_type, 0.0)

    def _analyze_image_content(self, img_path: str) -> float:
        """
        Analyze image content to filter out meaningless images.

        Checks:
        1. Color diversity (reject solid color boxes)
        2. Edge density (reject empty/blank images)
        3. Content complexity (entropy-based)

        Args:
            img_path: Path to image file

        Returns:
            Content quality score (0.0 ~ 1.0)
        """
        try:
            from PIL import Image
            import numpy as np

            # Load image
            img = Image.open(img_path)

            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize for faster processing (max 400x400)
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)

            # Convert to numpy array
            img_array = np.array(img)

            # 1. Color diversity check (40 points)
            color_score = self._check_color_diversity(img_array)

            # 2. Edge density check (30 points)
            edge_score = self._check_edge_density(img_array)

            # 3. Content complexity check (30 points)
            complexity_score = self._check_content_complexity(img_array)

            # Weighted average
            total_score = color_score * 0.40 + edge_score * 0.30 + complexity_score * 0.30

            logger.debug(
                f"           📊 Content analysis: color={color_score:.2f}, "
                f"edge={edge_score:.2f}, complexity={complexity_score:.2f}, "
                f"total={total_score:.2f}"
            )

            return total_score

        except Exception as e:
            logger.debug(f"           ⚠️  Image content analysis error: {e}")
            return 0.5  # Neutral score on error

    def _check_color_diversity(self, img_array: "np.ndarray") -> float:
        """
        Check color diversity to reject solid color images.

        Args:
            img_array: Image as numpy array (H, W, 3)

        Returns:
            Color diversity score (0.0 ~ 1.0)
        """
        import numpy as np

        # Calculate color histogram for each channel
        hist_r = np.histogram(img_array[:, :, 0], bins=32, range=(0, 256))[0]
        hist_g = np.histogram(img_array[:, :, 1], bins=32, range=(0, 256))[0]
        hist_b = np.histogram(img_array[:, :, 2], bins=32, range=(0, 256))[0]

        # Normalize histograms
        hist_r = hist_r / hist_r.sum()
        hist_g = hist_g / hist_g.sum()
        hist_b = hist_b / hist_b.sum()

        # Count non-zero bins (unique colors)
        unique_colors = ((hist_r > 0.001).sum() + (hist_g > 0.001).sum() + (hist_b > 0.001).sum()) / 3.0

        # Check if color is concentrated in few bins (solid color)
        max_concentration_r = hist_r.max()
        max_concentration_g = hist_g.max()
        max_concentration_b = hist_b.max()
        avg_concentration = (max_concentration_r + max_concentration_g + max_concentration_b) / 3.0

        # Scoring
        score = 0.0

        # 1. Unique colors (50%)
        if unique_colors >= 20:  # Many colors
            score += 0.5
        elif unique_colors >= 10:
            score += 0.3
        elif unique_colors >= 5:
            score += 0.15
        else:  # Very few colors - likely solid/gradient
            score += 0.0

        # 2. Color concentration (50%)
        if avg_concentration < 0.3:  # Well distributed
            score += 0.5
        elif avg_concentration < 0.5:
            score += 0.3
        elif avg_concentration < 0.7:
            score += 0.15
        else:  # Highly concentrated - solid color
            return 0.0  # Reject immediately

        return min(1.0, score)

    def _check_edge_density(self, img_array: "np.ndarray") -> float:
        """
        Check edge density to detect actual content vs blank images.

        Args:
            img_array: Image as numpy array (H, W, 3)

        Returns:
            Edge density score (0.0 ~ 1.0)
        """
        import numpy as np
        from PIL import Image, ImageFilter

        try:
            # Convert to grayscale
            img_gray = Image.fromarray(img_array).convert("L")

            # Apply edge detection (Sobel-like filter)
            edges = img_gray.filter(ImageFilter.FIND_EDGES)
            edge_array = np.array(edges)

            # Calculate edge density
            edge_pixels = (edge_array > 30).sum()  # Threshold for edge
            total_pixels = edge_array.size
            edge_density = edge_pixels / total_pixels

            # Scoring based on edge density
            if edge_density >= 0.15:  # High detail (diagrams, charts, photos)
                return 1.0
            elif edge_density >= 0.08:  # Moderate detail
                return 0.8
            elif edge_density >= 0.04:  # Some detail
                return 0.5
            elif edge_density >= 0.02:  # Low detail
                return 0.3
            else:  # Very low - likely blank/solid
                return 0.0

        except Exception as e:
            logger.debug(f"           ⚠️  Edge detection error: {e}")
            return 0.5

    def _check_content_complexity(self, img_array: "np.ndarray") -> float:
        """
        Check content complexity using entropy.

        Higher entropy = more information = meaningful image

        Args:
            img_array: Image as numpy array (H, W, 3)

        Returns:
            Complexity score (0.0 ~ 1.0)
        """
        import numpy as np
        from scipy.stats import entropy

        try:
            # Calculate entropy for each color channel
            entropies = []

            for channel in range(3):  # R, G, B
                hist = np.histogram(img_array[:, :, channel], bins=256, range=(0, 256))[0]
                hist = hist / hist.sum()  # Normalize

                # Remove zeros to avoid log(0)
                hist = hist[hist > 0]

                # Calculate Shannon entropy
                channel_entropy = entropy(hist, base=2)
                entropies.append(channel_entropy)

            avg_entropy = np.mean(entropies)

            # Scoring based on entropy
            # Max entropy for 8-bit image = 8 bits
            if avg_entropy >= 6.0:  # Very high complexity
                return 1.0
            elif avg_entropy >= 5.0:  # High complexity
                return 0.8
            elif avg_entropy >= 4.0:  # Moderate complexity
                return 0.6
            elif avg_entropy >= 3.0:  # Low complexity
                return 0.4
            elif avg_entropy >= 2.0:  # Very low
                return 0.2
            else:  # Extremely low - likely solid color
                return 0.0

        except ImportError:
            # scipy not available - use simplified metric
            logger.debug(f"           ⚠️  scipy not available, using simplified complexity check")

            # Use standard deviation as proxy for complexity
            std_r = np.std(img_array[:, :, 0])
            std_g = np.std(img_array[:, :, 1])
            std_b = np.std(img_array[:, :, 2])
            avg_std = (std_r + std_g + std_b) / 3.0

            # Scoring based on std dev
            if avg_std >= 60:
                return 1.0
            elif avg_std >= 40:
                return 0.7
            elif avg_std >= 20:
                return 0.4
            elif avg_std >= 10:
                return 0.2
            else:
                return 0.0

        except Exception as e:
            logger.debug(f"           ⚠️  Complexity check error: {e}")
            return 0.5

    def _smart_select_images(self, candidates: List[dict], max_images: int) -> List[ImageReference]:
        """
        Smart image selection with constraints.

        Constraints:
        1. Max 1 image per page
        2. Global deduplication (skip already used images)
        3. Ensure diversity

        Args:
            candidates: List of candidate dicts (sorted by score)
            max_images: Maximum images to select

        Returns:
            List of selected ImageReference objects
        """
        selected = []
        used_pages = {}  # {(source, page): count}

        for candidate in candidates:
            if len(selected) >= max_images:
                break

            img = candidate["image"]
            img_id = img.get("id")
            source = candidate["source"]
            page = candidate["page"]

            # 1. Global deduplication check
            if hasattr(self, "used_image_ids") and img_id in self.used_image_ids:
                logger.debug(f"           ⏭️  Skip {img_id} (already used in previous section)")
                continue

            # 2. Page limit check (max 1 per page)
            page_key = (source, page)
            page_usage = used_pages.get(page_key, 0)

            if page_usage >= 1:
                logger.debug(f"           ⏭️  Skip page {page} (already selected from this page)")
                continue

            # Select this image!
            selected.append(
                ImageReference(
                    image_id=img_id,
                    path=img.get("path", ""),
                    description=img.get("description", "") or f"From page {page}",
                    caption=f"From source material (page {page})",
                    attribution=f"Source: {Path(source).name}, page {page}",
                )
            )

            used_pages[page_key] = page_usage + 1

            logger.debug(
                f"           ✅ Selected from page {page} "
                f"(score: {candidate['score']:.2f}, "
                f"importance: {candidate['page_importance']:.2f}, "
                f"quality: {candidate['quality']:.2f})"
            )

        return selected

    def _expand_to_adjacent_pages(
        self,
        selected: List[ImageReference],
        max_images: int,
        page_importance: dict,
        image_page_map: dict,
        pdf_images: List[dict],
    ) -> List[ImageReference]:
        """
        Expand to adjacent pages if not enough images found.

        Strategy:
        - Check ±1, ±2 pages from important pages
        - Apply same quality criteria

        Args:
            selected: Currently selected images
            max_images: Target number of images
            page_importance: Page importance scores
            image_page_map: Image-page mapping
            pdf_images: Available PDF images

        Returns:
            Updated list of selected images
        """
        if len(selected) >= max_images:
            return selected

        logger.debug(f"        🔍 Expanding to adjacent pages (need {max_images - len(selected)} more)")

        # Track used pages
        used_pages = set()
        for img in selected:
            if "page " in img.caption:
                try:
                    page_num = int(img.caption.split("page ")[-1].rstrip(")"))
                    source = img.attribution.split("Source: ")[-1].split(", page")[0]
                    used_pages.add((source, page_num))
                except (AttributeError, ValueError, IndexError) as e:
                    logger.debug(f"Could not parse image metadata from caption/attribution: {e}")
                    pass

        # Expand search
        for source, page_scores in page_importance.items():
            if len(selected) >= max_images:
                break

            if source not in image_page_map:
                continue

            # Process top 3 important pages
            for page_num, importance in page_scores[:3]:
                if len(selected) >= max_images:
                    break

                # Try adjacent pages (±1, ±2)
                for offset in [1, -1, 2, -2]:
                    adjacent_page = page_num + offset
                    page_key = (source, adjacent_page)

                    # Skip if already used
                    if page_key in used_pages:
                        continue

                    page_str = str(adjacent_page)
                    if page_str not in image_page_map[source]:
                        continue

                    # Check images from adjacent page
                    page_images = image_page_map[source][page_str]

                    for img_info in page_images:
                        if len(selected) >= max_images:
                            break

                        # Find full image
                        full_img = next((img for img in pdf_images if img.get("id") == img_info["id"]), None)

                        if not full_img:
                            continue

                        # Global deduplication check
                        img_id = full_img.get("id")
                        if hasattr(self, "used_image_ids") and img_id in self.used_image_ids:
                            continue

                        # Quality check
                        quality = self._evaluate_image_quality_simple(full_img)

                        if quality >= Config.IMAGE_SELECTION_QUALITY_THRESHOLD:
                            selected.append(
                                ImageReference(
                                    image_id=img_id,
                                    path=full_img.get("path", ""),
                                    description=full_img.get("description", "") or f"From page {adjacent_page} (adjacent)",
                                    caption=f"From source material (page {adjacent_page})",
                                    attribution=f"Source: {Path(source).name}, page {adjacent_page}",
                                )
                            )
                            used_pages.add(page_key)
                            logger.debug(f"           ✅ Added from adjacent page {adjacent_page} (offset: {offset:+d})")
                            break  # Only 1 image per page

        logger.debug(f"        📷 Total after expansion: {len(selected)} images")

        return selected

