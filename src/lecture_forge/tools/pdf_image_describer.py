"""
PDF Image Description Generator - Infers image descriptions from page text.

This tool analyzes PDF page content to generate descriptions for extracted images,
enabling better image matching without expensive Vision AI.
"""

import json
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from lecture_forge.config import Config
from lecture_forge.utils import logger


class PDFImageDescriber:
    """Generate descriptions for PDF images based on page text context."""

    def __init__(self, model: str = None):
        """
        Initialize PDF Image Describer.

        Args:
            model: LLM model to use (default: gpt-4o-mini for cost efficiency)
        """
        from openai import OpenAI

        self.model = model or "gpt-4o-mini"
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def enhance_images(self, pdf_path: str, image_dir: str, batch_size: int = 5) -> Dict:
        """
        Generate descriptions for PDF images using page text inference.

        Args:
            pdf_path: Path to source PDF
            image_dir: Directory containing extracted images
            batch_size: Number of images to process per page (for batching)

        Returns:
            Dictionary with enhancement results
        """
        logger.info(f"📄 Enhancing PDF images from: {pdf_path}")

        pdf_path = Path(pdf_path)
        image_dir = Path(image_dir)

        if not pdf_path.exists():
            return {"success": False, "error": f"PDF not found: {pdf_path}", "enhanced_count": 0}

        if not image_dir.exists():
            return {"success": False, "error": f"Image directory not found: {image_dir}", "enhanced_count": 0}

        # Load PDF
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            return {"success": False, "error": f"Failed to open PDF: {e}", "enhanced_count": 0}

        # Group images by page
        images_by_page = self._group_images_by_page(image_dir)

        logger.info(f"   Found images from {len(images_by_page)} pages")

        # Process each page
        enhanced_images = []
        total_cost = 0.0

        for page_num, image_files in sorted(images_by_page.items()):
            try:
                # Extract page text
                page_text = self._extract_page_text(doc, page_num)

                if not page_text.strip():
                    logger.warning(f"   Page {page_num}: No text found, skipping")
                    continue

                # Generate descriptions for all images on this page
                descriptions = self._generate_descriptions_for_page(page_num, page_text, len(image_files))

                # Update image files with descriptions
                for img_file, description in zip(image_files, descriptions):
                    enhanced_images.append(
                        {"file": img_file.name, "page": page_num, "description": description, "path": str(img_file)}
                    )

                logger.info(f"   ✅ Page {page_num}: Generated {len(descriptions)} descriptions")

                # Estimate cost (very rough)
                # gpt-4o-mini: ~$0.15/1M input, ~$0.6/1M output
                # Assume ~500 tokens input, ~100 tokens output per page
                page_cost = (500 * 0.15 + 100 * 0.6) / 1_000_000
                total_cost += page_cost

            except Exception as e:
                logger.error(f"   ❌ Page {page_num}: Error - {e}")
                continue

        doc.close()

        # Save descriptions to JSON
        descriptions_file = image_dir / "image_descriptions.json"
        try:
            with open(descriptions_file, "w", encoding="utf-8") as f:
                json.dump(enhanced_images, f, ensure_ascii=False, indent=2)
            logger.info(f"   💾 Saved descriptions to: {descriptions_file}")
        except Exception as e:
            logger.error(f"   Failed to save descriptions: {e}")

        logger.info(f"   📊 Enhanced {len(enhanced_images)} images")
        logger.info(f"   💰 Estimated cost: ${total_cost:.4f}")

        return {
            "success": True,
            "enhanced_count": len(enhanced_images),
            "descriptions_file": str(descriptions_file),
            "estimated_cost": total_cost,
            "enhanced_images": enhanced_images,
        }

    def _group_images_by_page(self, image_dir: Path) -> Dict[int, List[Path]]:
        """Group image files by page number."""
        images_by_page = {}

        for img_file in image_dir.glob("*.png"):
            # Parse filename: page{N}_img{M}_{hash}.png
            try:
                filename = img_file.name
                if filename.startswith("page"):
                    page_part = filename.split("_")[0]  # "page123"
                    page_num = int(page_part.replace("page", ""))

                    if page_num not in images_by_page:
                        images_by_page[page_num] = []

                    images_by_page[page_num].append(img_file)
            except Exception as e:
                logger.warning(f"   Failed to parse filename {img_file.name}: {e}")
                continue

        return images_by_page

    def _extract_page_text(self, doc: fitz.Document, page_num: int) -> str:
        """Extract text from a specific PDF page."""
        try:
            page = doc[page_num - 1]  # page_num is 1-indexed
            text = page.get_text()
            return text
        except Exception as e:
            logger.error(f"   Failed to extract text from page {page_num}: {e}")
            return ""

    def _generate_descriptions_for_page(self, page_num: int, page_text: str, num_images: int) -> List[str]:
        """Generate descriptions for images on a page using LLM."""
        # Limit page text to avoid token limits
        page_text = page_text[:2000]

        prompt = f"""Analyze this page from a technical document and describe the {num_images} image(s) on it.

**Page {page_num} Text:**
{page_text}

**Task:**
This page contains {num_images} image(s). Based on the text content, infer what each image likely shows.

**Requirements:**
- Write 1-2 concise sentences per image
- Use technical keywords for searchability
- Focus on: diagrams, charts, architecture, screenshots, formulas, etc.
- Use English for better keyword matching

**Format:**
Image 1: [description]
Image 2: [description]
...

If you can't infer from text, describe the general topic of the page."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical document analyst. Generate concise, keyword-rich descriptions for images based on surrounding text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )

            content = response.choices[0].message.content.strip()

            # Parse descriptions
            descriptions = self._parse_descriptions(content, num_images)

            return descriptions

        except Exception as e:
            logger.error(f"   LLM call failed for page {page_num}: {e}")
            # Return generic descriptions
            return [f"Image from page {page_num}" for _ in range(num_images)]

    def _parse_descriptions(self, llm_output: str, expected_count: int) -> List[str]:
        """Parse LLM output into individual descriptions."""
        descriptions = []

        # Try to parse "Image 1: ...\nImage 2: ..." format
        lines = llm_output.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("Image"):
                # Extract description after colon
                if ":" in line:
                    desc = line.split(":", 1)[1].strip()
                    descriptions.append(desc)

        # If parsing failed, split by periods or return full text
        if len(descriptions) == 0:
            # Fallback: split by sentences
            sentences = llm_output.split(". ")
            descriptions = [s.strip() for s in sentences if s.strip()]

        # Ensure we have exactly expected_count descriptions
        if len(descriptions) < expected_count:
            # Pad with last description or generic
            last_desc = descriptions[-1] if descriptions else "Technical diagram or chart"
            while len(descriptions) < expected_count:
                descriptions.append(last_desc)

        return descriptions[:expected_count]

    def apply_descriptions_to_images(self, image_dir: str, descriptions_file: str = None) -> int:
        """
        Apply saved descriptions to image metadata.

        Args:
            image_dir: Directory containing images
            descriptions_file: Path to descriptions JSON (default: image_dir/image_descriptions.json)

        Returns:
            Number of images updated
        """
        image_dir = Path(image_dir)

        if descriptions_file is None:
            descriptions_file = image_dir / "image_descriptions.json"
        else:
            descriptions_file = Path(descriptions_file)

        if not descriptions_file.exists():
            logger.error(f"Descriptions file not found: {descriptions_file}")
            return 0

        # Load descriptions
        try:
            with open(descriptions_file, "r", encoding="utf-8") as f:
                enhanced_images = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load descriptions: {e}")
            return 0

        # Create mapping: filename -> description
        desc_map = {img["file"]: img["description"] for img in enhanced_images}

        logger.info(f"Loaded {len(desc_map)} descriptions")

        return len(desc_map)
