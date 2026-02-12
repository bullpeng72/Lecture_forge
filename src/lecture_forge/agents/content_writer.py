"""
Content Writer Agent - Writes lecture content using RAG.
"""

from pathlib import Path
from typing import List

import numpy as np

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import CodeBlock, ImageReference, SectionContent
from lecture_forge.utils import logger
from lecture_forge.utils.content_metrics import (
    calculate_target_metrics,
    evaluate_content_quality,
    format_quality_report,
)
from lecture_forge.utils.prompt_manager import load_prompt


class ContentWriterAgent(BaseAgent):
    """Agent for writing lecture content with RAG."""

    def __init__(self, vector_store: VectorStore = None):
        """
        Initialize Content Writer Agent.

        Args:
            vector_store: Vector store for RAG queries
        """
        super().__init__()
        logger.info("Initializing Content Writer Agent")
        self.vector_store = vector_store

        # Global image tracking for deduplication across sections
        self.used_image_ids = set()
        self.image_usage_count = {}

    def write_all_sections(
        self,
        curriculum: Curriculum,
        available_images: List[dict] = None,
    ) -> List[SectionContent]:
        """
        Write content for all sections in curriculum with global image deduplication.

        Args:
            curriculum: Curriculum plan
            available_images: List of available images with metadata

        Returns:
            List of section contents
        """
        logger.info(f"📝 Writing content for {len(curriculum.sections)} sections with image deduplication")

        section_contents = []

        # Initialize global image tracking
        self.used_image_ids.clear()
        self.image_usage_count.clear()

        for i, section in enumerate(curriculum.sections):
            logger.info(f"\n{'='*60}")
            logger.info(f"Section {i+1}/{len(curriculum.sections)}: {section.title}")
            logger.info(f"{'='*60}")

            # Filter available images (exclude already used ones)
            available_for_section = [img for img in (available_images or []) if img.get("id") not in self.used_image_ids]

            logger.info(
                f"   📷 Available images: {len(available_for_section)} " f"(filtered from {len(available_images or [])})"
            )

            content = self.write_section(
                section=section,
                curriculum=curriculum,
                available_images=available_for_section,
            )

            # Track used images
            for img_ref in content.images:
                self.used_image_ids.add(img_ref.image_id)
                self.image_usage_count[img_ref.image_id] = self.image_usage_count.get(img_ref.image_id, 0) + 1

            logger.info(f"   ✅ Used {len(content.images)} images in this section")
            logger.info(f"   📊 Total unique images used so far: {len(self.used_image_ids)}")

            section_contents.append(content)

        # Final statistics
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Image Usage Statistics:")
        logger.info(f"{'='*60}")
        logger.info(f"   • Total images available: {len(available_images or [])}")
        logger.info(f"   • Unique images used: {len(self.used_image_ids)}")
        logger.info(f"   • Images reused: {sum(1 for c in self.image_usage_count.values() if c > 1)}")
        logger.info(f"   • Unused images: {len(available_images or []) - len(self.used_image_ids)}")

        logger.info(f"Completed writing {len(section_contents)} sections")
        return section_contents

    def write_section(
        self,
        section: Section,
        curriculum: Curriculum,
        available_images: List[dict] = None,
    ) -> SectionContent:
        """
        Write content for a single section using RAG.

        Args:
            section: Section to write content for
            curriculum: Full curriculum for context
            available_images: Available images

        Returns:
            Section content
        """
        # 1. RAG query to get relevant context
        contexts, context_metadatas = self._query_knowledge(section)

        # 2. Select relevant images FIRST (for accurate quality evaluation)
        images = self._select_images(section, available_images or [], context_metadatas)
        logger.info(f"   🖼️  Selected {len(images)} images for quality evaluation")

        # 3. Generate markdown content with LLM (pass image count for quality evaluation)
        markdown_content = self._generate_content(
            section=section,
            curriculum=curriculum,
            contexts=contexts,
            available_image_count=len(images),  # Pass actual image count
        )

        # 4. Extract code blocks (if any)
        code_blocks = self._extract_code_blocks(markdown_content)

        # 5. Count words
        word_count = len(markdown_content.split())

        content = SectionContent(
            section_id=section.id,
            title=section.title,
            markdown_content=markdown_content,
            code_blocks=code_blocks,
            images=images,
            diagrams=[],  # Diagrams will be added by DiagramGenerator
            word_count=word_count,
            estimated_time=section.estimated_time,
            difficulty_level=section.difficulty_level,
        )

        logger.info(f"Section '{section.title}': {word_count} words, {len(code_blocks)} code blocks, {len(images)} images")

        return content

    def _query_knowledge(self, section: Section) -> tuple:
        """Query vector DB for relevant context with increased retrieval.

        Returns:
            Tuple of (documents, metadatas) for RAG context and location-based image matching
        """
        if not self.vector_store:
            return [], []

        # Build comprehensive query from section topics
        query = " ".join(section.topics)

        try:
            # Increase from 5 to 10 for more comprehensive context
            results = self.vector_store.query(query, n_results=10)

            if results and results["documents"]:
                documents = results["documents"][0]
                metadatas = results.get("metadatas", [[]])[0]  # Extract metadatas
                return documents, metadatas
            else:
                return [], []

        except Exception as e:
            logger.warning(f"Error querying vector DB: {e}")
            return [], []

    def _generate_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        available_image_count: int = 0,
    ) -> str:
        """Generate detailed, comprehensive markdown content using LLM with RAG.

        Args:
            section: Section to write
            curriculum: Full curriculum
            contexts: RAG contexts
            available_image_count: Number of images selected for this section (for quality evaluation)
        """
        # Calculate target metrics
        targets = calculate_target_metrics(section.estimated_time, section.difficulty_level)

        # Use more contexts (increase from 8 to 10 for better content)
        context_text = "\n\n---\n\n".join(contexts[:10]) if contexts else "No additional context available."

        # Prepare template variables
        template_vars = {
            # Basic information
            "topic": curriculum.topic,
            "audience_level": curriculum.audience_level,
            "section_title": section.title,
            "estimated_time": section.estimated_time,
            "difficulty_level": section.difficulty_level,
            # Topics and outcomes
            "topics_list": ', '.join(section.topics),
            "learning_outcomes_list": '\n'.join(f'- {outcome}' for outcome in section.learning_outcomes),
            # Target metrics
            "min_words": targets['min_words'],
            "target_words": targets['target_words'],
            "max_words": targets['max_words'],
            "target_subsections": targets['target_subsections'],
            "target_code_examples": targets['target_code_examples'],
            "target_practice_problems": targets['target_practice_problems'],
            # Word count breakdown
            "intro_words": int(targets['target_words'] * 0.10),
            "main_content_words": int(targets['target_words'] * 0.70),
            "summary_words": int(targets['target_words'] * 0.20),
            "words_per_subsection": int(targets['target_words'] * 0.70 / max(1, targets['target_subsections'])),
            # Context
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("content_generation", **template_vars)

        try:
            response = self.invoke_llm(prompt, phase="content_writing")
            content = response.content.strip()

            # Clean up markdown fences
            if content.startswith("```markdown"):
                content = content.split("```markdown")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            # Validate content quality (use actual image count from selected images)
            code_blocks = self._extract_code_blocks(content)
            quality = evaluate_content_quality(
                content=content,
                targets=targets,
                code_block_count=len(code_blocks),
                image_count=available_image_count,  # Use actual selected images count
            )

            logger.info(f"  📊 Initial quality score: {quality['overall_score']}/100 (with {available_image_count} images)")

            # CRITICAL: If NO code examples, generate them separately
            if len(code_blocks) == 0 and targets["target_code_examples"] > 0:
                logger.warning(
                    f"  ❌ CRITICAL: No code examples found! Generating {targets['target_code_examples']} code examples..."
                )

                code_examples_content = self._generate_code_examples(
                    section=section, curriculum=curriculum, contexts=contexts, num_examples=targets["target_code_examples"]
                )

                # Append code examples to content
                content += "\n\n" + code_examples_content

                # Re-extract code blocks
                code_blocks = self._extract_code_blocks(content)
                logger.info(f"  ✅ Added {len(code_blocks)} code examples")

                # Re-evaluate (use actual image count)
                quality = evaluate_content_quality(
                    content=content,
                    targets=targets,
                    code_block_count=len(code_blocks),
                    image_count=available_image_count,  # Use actual selected images count
                )
                logger.info(f"  📊 Quality after adding code: {quality['overall_score']}/100")

            # If quality is too low, try to expand with multiple iterations
            if not quality["meets_requirements"]:
                logger.warning(f"  ⚠️ Content below target. Attempting to expand...")
                logger.info(format_quality_report(quality))

                # Try up to 2 iterations of expansion
                max_iterations = 2
                previous_quality_score = quality["overall_score"]  # Track for improvement check

                for iteration in range(max_iterations):
                    logger.info(f"  🔄 Expansion attempt {iteration + 1}/{max_iterations}")

                    try:
                        expanded_content = self._expand_content(
                            section=section,
                            curriculum=curriculum,
                            contexts=contexts,
                            targets=targets,
                            previous_content=content,
                            previous_quality=quality,
                        )

                        # Check if expansion was successful (content changed)
                        if expanded_content != content and len(expanded_content) > len(content):
                            content = expanded_content

                            # Re-evaluate (use actual image count)
                            code_blocks = self._extract_code_blocks(content)
                            quality = evaluate_content_quality(
                                content=content,
                                targets=targets,
                                code_block_count=len(code_blocks),
                                image_count=available_image_count,  # Use actual selected images count
                            )

                            logger.info(f"  📊 Quality after expansion {iteration + 1}: {quality['overall_score']}/100")

                            # Check improvement effectiveness (prevent wasteful iterations)
                            if iteration > 0:
                                improvement = quality["overall_score"] - previous_quality_score
                                if improvement < 3:  # Less than 3 points improvement
                                    logger.warning(
                                        f"  ⚠️ Minimal improvement (+{improvement:.1f} points). "
                                        "Stopping early to prevent wasteful iterations."
                                    )
                                    break

                            # Stop if meets requirements
                            if quality["meets_requirements"]:
                                logger.info(f"  ✅ Quality threshold met after {iteration + 1} expansion(s)")
                                break

                            # Update previous score for next iteration comparison
                            previous_quality_score = quality["overall_score"]
                        else:
                            logger.warning(f"  ⚠️ Expansion {iteration + 1} produced no change - stopping")
                            break

                    except Exception as e:
                        logger.error(f"  ❌ Expansion {iteration + 1} failed: {e}")
                        break

            return content

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"# {section.title}\n\n*Content generation error: {str(e)}*"

    def _expand_content(
        self,
        section: Section,
        curriculum: Curriculum,
        contexts: List[str],
        targets: dict,
        previous_content: str,
        previous_quality: dict,
    ) -> str:
        """Expand insufficient content to meet requirements."""
        shortfalls = []

        if previous_quality["word_count"] < targets["min_words"]:
            shortfalls.append(
                f"- Words: {previous_quality['word_count']} / {targets['min_words']} (need {targets['min_words'] - previous_quality['word_count']} more)"
            )

        if previous_quality["code_block_count"] < targets["min_code_examples"]:
            shortfalls.append(f"- Code examples: {previous_quality['code_block_count']} / {targets['min_code_examples']}")

        if previous_quality["subsection_count"] < targets["min_subsections"]:
            shortfalls.append(f"- Subsections: {previous_quality['subsection_count']} / {targets['min_subsections']}")

        shortfall_text = "\n".join(shortfalls)

        # Use more contexts for expansion (10 instead of 8)
        context_text = "\n\n---\n\n".join(contexts[:10]) if contexts else ""

        word_gap = targets["target_words"] - previous_quality["word_count"]

        # Prepare template variables
        template_vars = {
            "shortfall_text": shortfall_text,
            "current_word_count": previous_quality["word_count"],
            "min_words": targets["min_words"],
            "target_words": targets["target_words"],
            "word_gap": word_gap,
            "section_title": section.title,
            "estimated_time": section.estimated_time,
            "previous_content": previous_content,
            "depth_words": int(word_gap * 0.4),
            "code_words": int(word_gap * 0.3),
            "pitfall_words": int(word_gap * 0.15),
            "best_practice_words": int(word_gap * 0.15),
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("content_expansion", **template_vars)

        try:
            logger.debug(f"     Sending expansion prompt ({len(prompt)} chars)")

            response = self.invoke_llm(prompt, phase="content_expansion")
            expanded = response.content.strip()

            # Validate expansion actually happened
            if len(expanded) <= len(previous_content):
                logger.warning(f"     ⚠️ Expansion failed - response is not longer than original")
                logger.warning(f"        Original: {len(previous_content)} chars, Expanded: {len(expanded)} chars")
                return previous_content

            # Re-evaluate
            code_blocks = self._extract_code_blocks(expanded)
            image_count = self._count_images(expanded)
            new_quality = evaluate_content_quality(
                content=expanded,
                targets=targets,
                code_block_count=len(code_blocks),
                image_count=image_count,
            )

            word_increase = new_quality["word_count"] - previous_quality["word_count"]
            logger.info(
                f"     ✅ Expansion succeeded: +{word_increase} words ({previous_quality['word_count']} → {new_quality['word_count']})"
            )
            logger.info(f"     📊 Expanded quality score: {new_quality['overall_score']}/100")

            return expanded

        except Exception as e:
            logger.error(f"     ❌ Error expanding content: {type(e).__name__}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return previous_content  # Return original on error

    def _count_images(self, markdown: str) -> int:
        """Count the number of images in markdown content."""
        import re
        # Match markdown image syntax: ![alt](url)
        image_pattern = r'!\[.*?\]\(.*?\)'
        matches = re.findall(image_pattern, markdown)
        return len(matches)

    def _extract_code_blocks(self, markdown: str) -> List[CodeBlock]:
        """Extract code blocks from markdown content."""
        code_blocks = []

        lines = markdown.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for code fence
            if line.strip().startswith("```"):
                # Extract language
                language = line.strip()[3:].strip() or "text"

                # Collect code lines
                code_lines = []
                i += 1

                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1

                code = "\n".join(code_lines)

                code_blocks.append(
                    CodeBlock(
                        language=language,
                        code=code,
                        caption=None,
                    )
                )

            i += 1

        return code_blocks

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

    def _get_keyword_translations(self) -> dict:
        """Comprehensive Korean-English keyword mapping for AI/ML terms."""
        return {
            # ===== AI/ML General =====
            "인공지능": ["artificial intelligence", "ai"],
            "기계학습": ["machine learning", "ml"],
            "딥러닝": ["deep learning", "dl", "deep neural network"],
            "신경망": ["neural network", "nn", "network"],
            # ===== LLM Related =====
            "대형 언어 모델": ["large language model", "llm", "language model", "transformer"],
            "언어 모델": ["language model", "llm", "lm"],
            "트랜스포머": ["transformer", "attention", "self-attention"],
            "어텐션": ["attention", "attention mechanism", "self-attention"],
            "파인튜닝": ["fine-tuning", "finetuning", "fine tuning", "finetune", "training"],
            "프롬프트": ["prompt", "prompting", "prompt engineering"],
            "프롬프트 엔지니어링": ["prompt engineering", "prompting", "prompt design"],
            "컨텍스트": ["context", "contextual", "context window"],
            "컨텍스트 엔지니어링": ["context engineering", "context", "contextual"],
            # ===== Models =====
            "GPT": ["gpt", "generative pre-trained transformer"],
            "BERT": ["bert", "bidirectional encoder"],
            "ChatGPT": ["chatgpt", "chat gpt", "gpt"],
            "LLM": ["llm", "large language model", "language model"],
            # ===== RAG & Vector DB =====
            "RAG": ["rag", "retrieval augmented generation", "retrieval", "augmented"],
            "정보 검색": ["retrieval", "information retrieval", "search", "ir"],
            "검색": ["search", "retrieval", "query", "lookup"],
            "임베딩": ["embedding", "embeddings", "vector embedding", "word embedding"],
            "벡터": ["vector", "vectors", "vectorization"],
            "벡터 데이터베이스": ["vector database", "vector db", "vectordb", "embedding database"],
            "데이터베이스": ["database", "db", "datastore", "storage"],
            "색인": ["index", "indexing"],
            "유사도": ["similarity", "cosine similarity", "distance"],
            # ===== AI Agents =====
            "에이전트": ["agent", "agents", "ai agent", "autonomous"],
            "AI 에이전트": ["ai agent", "agent", "autonomous agent"],
            "자율": ["autonomous", "automation", "automatic"],
            "계획": ["planning", "plan", "strategy"],
            "도구": ["tool", "tools", "function", "api"],
            "실행": ["execution", "execute", "action"],
            "추론": ["reasoning", "inference", "thinking"],
            "의사결정": ["decision making", "decision"],
            # ===== Generation Parameters =====
            "파라미터": ["parameter", "parameters", "hyperparameter", "config"],
            "하이퍼파라미터": ["hyperparameter", "hyper-parameter", "parameter"],
            "온도": ["temperature", "temp", "sampling"],
            "토큰": ["token", "tokens", "tokenization"],
            "생성": ["generation", "generate", "output", "inference"],
            "생성 파라미터": ["generation parameters", "sampling", "decoding"],
            "샘플링": ["sampling", "sample", "decoding"],
            "빔 서치": ["beam search", "beam"],
            "탐욕": ["greedy", "greedy search"],
            # ===== Reinforcement Learning =====
            "강화학습": ["reinforcement learning", "rl", "reward", "policy"],
            "보상": ["reward", "rewards"],
            "정책": ["policy", "policies"],
            "가치함수": ["value function", "value"],
            "Q-학습": ["q-learning", "q learning"],
            "병목": ["bottleneck", "constraint"],
            "병목 현상": ["bottleneck", "bottleneck problem"],
            # ===== Architecture =====
            "아키텍처": ["architecture", "model architecture", "structure"],
            "레이어": ["layer", "layers", "hidden layer"],
            "인코더": ["encoder", "encoding"],
            "디코더": ["decoder", "decoding"],
            "어텐션 메커니즘": ["attention mechanism", "attention", "self-attention"],
            "순환 신경망": ["recurrent neural network", "rnn"],
            "합성곱": ["convolution", "convolutional", "cnn"],
            "완전 연결": ["fully connected", "dense", "fc"],
            # ===== Training Process =====
            "학습": ["training", "learning", "train"],
            "훈련": ["training", "train"],
            "사전학습": ["pre-training", "pretraining", "pretrain"],
            "사전 학습": ["pre-training", "pretraining", "pretrain"],
            "미세조정": ["fine-tuning", "finetuning", "fine tuning"],
            "미세 조정": ["fine-tuning", "finetuning", "fine tuning"],
            "튜닝": ["tuning", "fine-tuning"],
            "최적화": ["optimization", "optimizer", "optimize"],
            "손실함수": ["loss function", "loss", "objective"],
            "손실": ["loss", "loss function"],
            "경사하강": ["gradient descent", "backpropagation", "gradient"],
            "역전파": ["backpropagation", "backprop"],
            "배치": ["batch", "batching", "mini-batch"],
            "에포크": ["epoch", "epochs"],
            # ===== Evaluation =====
            "평가": ["evaluation", "eval", "assessment", "metric"],
            "성능": ["performance", "accuracy", "precision"],
            "정확도": ["accuracy", "acc"],
            "정밀도": ["precision"],
            "재현율": ["recall"],
            "F1": ["f1", "f1-score"],
            "지표": ["metric", "metrics", "measure"],
            # ===== Data =====
            "데이터": ["data", "dataset"],
            "데이터셋": ["dataset", "data", "corpus"],
            "말뭉치": ["corpus", "corpora", "dataset"],
            "전처리": ["preprocessing", "preprocess", "data cleaning"],
            "정규화": ["normalization", "normalize"],
            "토큰화": ["tokenization", "tokenize"],
            "레이블": ["label", "labels", "annotation"],
            # ===== Common CS Terms =====
            "알고리즘": ["algorithm", "algo"],
            "모델": ["model", "models"],
            "예측": ["prediction", "inference", "predict"],
            "분류": ["classification", "classify"],
            "회귀": ["regression"],
            "군집화": ["clustering", "cluster"],
            "차원": ["dimension", "dimensional"],
            "특징": ["feature", "features"],
            # ===== Visualization =====
            "다이어그램": ["diagram", "chart", "visualization"],
            "그래프": ["graph", "plot", "chart"],
            "시각화": ["visualization", "visual", "plot"],
            "플롯": ["plot", "plotting"],
            # ===== Domain Specific =====
            "자연어처리": ["natural language processing", "nlp", "language processing"],
            "컴퓨터비전": ["computer vision", "cv", "image processing"],
            "이미지 처리": ["image processing", "computer vision"],
            "음성인식": ["speech recognition", "speech", "audio"],
            "텍스트 생성": ["text generation", "generation"],
            "번역": ["translation", "machine translation"],
            # ===== Concepts =====
            "개념": ["concept", "concepts"],
            "원리": ["principle", "principles"],
            "방법": ["method", "methods", "approach"],
            "기법": ["technique", "techniques"],
            "전략": ["strategy", "strategies"],
            "패턴": ["pattern", "patterns"],
            "구조": ["structure", "structures"],
            "시스템": ["system", "systems"],
            "프레임워크": ["framework", "frameworks"],
            "라이브러리": ["library", "libraries"],
        }

    def _generate_code_examples(self, section: Section, curriculum: Curriculum, contexts: List[str], num_examples: int) -> str:
        """Generate code examples separately when main content lacks them."""

        context_text = "\n\n---\n\n".join(contexts[:5]) if contexts else ""

        # Prepare template variables
        template_vars = {
            "num_examples": num_examples,
            "section_title": section.title,
            "topic": curriculum.topic,
            "audience_level": curriculum.audience_level,
            "topics_list": ', '.join(section.topics),
            "context_text": context_text,
        }

        # Load prompt from template
        prompt = load_prompt("code_examples_generation", **template_vars)

        try:
            response = self.invoke_llm(prompt, phase="code_generation")
            code_examples_content = response.content.strip()

            # Clean up markdown fences
            if code_examples_content.startswith("```markdown"):
                code_examples_content = code_examples_content.split("```markdown")[1].split("```")[0].strip()
            elif code_examples_content.startswith("```"):
                # Remove only outer code fence, keep inner code blocks
                parts = code_examples_content.split("```")
                if len(parts) >= 3:
                    # Remove first and last ```
                    code_examples_content = "```".join(parts[1:-1])

            return code_examples_content

        except Exception as e:
            logger.error(f"  ❌ Failed to generate code examples: {e}")
            # Return informative fallback when code generation fails
            return f"""
### 코드 예제: {section.title}

> **안내:** 이 섹션의 코드 예제는 자동 생성에 실패하여 표시되지 않았습니다.
> 강의 진행 시 관련 코드를 직접 시연하거나, 생성된 HTML 파일을 편집하여 코드를 추가하실 수 있습니다.

**이 섹션에서 다룰 주제:**
- {section.title}의 핵심 개념 구현
- 실전 활용 예제
- 주의사항 및 베스트 프랙티스

_(코드 생성 실패 원인: {str(e)[:100]})_
"""

    def _expand_keywords(self, topic: str, keyword_map: dict) -> List[str]:
        """Expand topic with English translations and variations."""
        keywords = [topic]  # Original topic

        # Add mapped translations
        for ko_term, en_terms in keyword_map.items():
            if ko_term in topic:
                keywords.extend(en_terms)

        # Extract acronyms (e.g., "LLM" from "대형 언어 모델(LLM)")
        import re

        acronyms = re.findall(r"\b[A-Z]{2,}\b", topic)
        keywords.extend([a.lower() for a in acronyms])

        # Extract English words already in topic
        english_words = re.findall(r"\b[a-zA-Z]{3,}\b", topic)
        keywords.extend([w.lower() for w in english_words])

        # Remove duplicates and empty strings
        keywords = list(set(k for k in keywords if k))

        return keywords
