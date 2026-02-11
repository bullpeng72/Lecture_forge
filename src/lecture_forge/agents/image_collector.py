"""
Image Collector Agent - Collects images from various sources.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.tools.image_extractor import PDFImageExtractorTool, WebImageScraperTool
from lecture_forge.tools.image_search import PexelsSearchTool, UnsplashSearchTool
from lecture_forge.utils import logger


class ImageCollectorAgent(BaseAgent):
    """Agent for collecting images from PDFs, URLs, and image search APIs."""

    def __init__(self, vision_model: str = None, session_id: str = None, vector_store=None):
        """
        Initialize Image Collector Agent.

        Args:
            vision_model: Model for vision tasks (default: Config.VISION_MODEL)
            session_id: Session identifier for organizing images
            vector_store: VectorStore instance for storing image descriptions (optional)
        """
        super().__init__(model=vision_model or Config.DEFAULT_MODEL)
        logger.info("Initializing Image Collector Agent")

        # Generate session ID
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        # Vector store for RAG integration
        self.vector_store = vector_store

        # Initialize tools
        self.pdf_extractor = PDFImageExtractorTool()
        self.web_scraper = WebImageScraperTool()
        self.unsplash_search = UnsplashSearchTool()
        self.pexels_search = PexelsSearchTool()

        # Track collected images
        self.all_images = []
        self.image_hashes = set()  # For global deduplication

    def collect(
        self,
        sources: Dict[str, List[str]],
        download_search_images: bool = True,
        max_images_per_keyword: int = None,
        auto_describe_images: bool = True,
    ) -> Dict:
        """
        Collect images from all sources.

        Args:
            sources: Dictionary with keys 'pdfs', 'urls', 'image_keywords'
            download_search_images: Whether to download images from search APIs
            max_images_per_keyword: Maximum images to collect per keyword
            auto_describe_images: Automatically generate descriptions for PDF images using LLM

        Returns:
            Image collection result
        """
        logger.info("Starting image collection")

        # Use config default if not specified
        if max_images_per_keyword is None:
            max_images_per_keyword = Config.MAX_IMAGES_PER_SEARCH

        pdfs = sources.get("pdfs", [])
        urls = sources.get("urls", [])
        image_keywords = sources.get("image_keywords", [])

        logger.info(f"Sources: {len(pdfs)} PDFs, {len(urls)} URLs, {len(image_keywords)} keywords")

        self.all_images = []
        self.image_hashes = set()

        # 1. Extract images from PDFs
        pdf_images_by_source = {}  # Track PDF path -> images for description generation

        for pdf_path in pdfs:
            try:
                logger.info(f"Extracting images from PDF: {pdf_path}")
                result = self.pdf_extractor.run(pdf_path, session_id=self.session_id)

                if result["success"]:
                    pdf_images = []
                    for img in result["images"]:
                        if img["hash"] not in self.image_hashes:
                            self.all_images.append(img)
                            self.image_hashes.add(img["hash"])
                            pdf_images.append(img)

                    pdf_images_by_source[pdf_path] = pdf_images

                    logger.info(f"✅ Extracted {len(result['images'])} images from PDF")
                else:
                    logger.error(f"❌ Failed to extract images: {result['error']}")

            except Exception as e:
                logger.error(f"Error extracting images from PDF {pdf_path}: {e}")

        # 1.5. Auto-generate descriptions for PDF images
        if auto_describe_images and pdf_images_by_source:
            self._auto_describe_pdf_images(pdf_images_by_source)

        # 2. Scrape images from URLs
        for url in urls:
            try:
                logger.info(f"Scraping images from URL: {url}")

                # First scrape the page to get BeautifulSoup object
                from lecture_forge.tools.web_scraper import WebScraperTool

                scraper = WebScraperTool()
                page_result = scraper.run(url)

                if page_result["success"]:
                    # Parse HTML with BeautifulSoup
                    from bs4 import BeautifulSoup
                    import requests

                    response = requests.get(url, timeout=Config.WEB_SCRAPER_TIMEOUT)
                    soup = BeautifulSoup(response.content, "html.parser")

                    result = self.web_scraper.run(url, soup, session_id=self.session_id)

                    if result["success"]:
                        for img in result["images"]:
                            if img["hash"] not in self.image_hashes:
                                self.all_images.append(img)
                                self.image_hashes.add(img["hash"])

                        logger.info(f"✅ Scraped {len(result['images'])} images from URL")
                    else:
                        logger.error(f"❌ Failed to scrape images: {result['error']}")
                else:
                    logger.error(f"❌ Failed to access URL: {page_result['error']}")

            except Exception as e:
                logger.error(f"Error scraping images from URL {url}: {e}")

        # 3. Search for images with keywords
        for keyword in image_keywords:
            try:
                logger.info(f"Searching images for: {keyword}")

                # Try Pexels first (it seems to work based on our tests)
                result = self.pexels_search.run(
                    query=keyword,
                    per_page=max_images_per_keyword,
                    download=download_search_images,
                    session_id=self.session_id,
                )

                if result["success"]:
                    for img in result["images"]:
                        # Use ID for deduplication since we might not have hash yet
                        img_id = img["id"]
                        if img_id not in [i.get("id") for i in self.all_images]:
                            self.all_images.append(img)

                    logger.info(f"✅ Found {len(result['images'])} images on Pexels")
                else:
                    logger.warning(f"Pexels search failed: {result['error']}")

                    # Try Unsplash as fallback
                    unsplash_result = self.unsplash_search.run(
                        query=keyword,
                        per_page=max_images_per_keyword,
                        download=download_search_images,
                        session_id=self.session_id,
                    )

                    if unsplash_result["success"]:
                        for img in unsplash_result["images"]:
                            img_id = img["id"]
                            if img_id not in [i.get("id") for i in self.all_images]:
                                self.all_images.append(img)

                        logger.info(f"✅ Found {len(unsplash_result['images'])} images on Unsplash")
                    else:
                        logger.warning(f"Unsplash search also failed: {unsplash_result['error']}")

            except Exception as e:
                logger.error(f"Error searching images for {keyword}: {e}")

        # 4. Store image descriptions in Vector DB (if available)
        if self.vector_store:
            self._store_images_in_vector_db()

        # 4.5. Build and save image-page map for PDF images
        pdf_images = [img for img in self.all_images if img.get("source", "").endswith(".pdf")]
        if pdf_images:
            image_page_map = self._build_image_page_map(pdf_images)
            self._save_image_page_map(image_page_map)

        # 5. Organize results
        storage_path = Path(Config.DATA_DIR) / "images" / self.session_id

        # Categorize images by source
        images_by_source = {
            "pdf": [img for img in self.all_images if img.get("source", "").endswith(".pdf")],
            "web": [img for img in self.all_images if img.get("id", "").startswith("web_")],
            "pexels": [img for img in self.all_images if img.get("source") == "pexels"],
            "unsplash": [img for img in self.all_images if img.get("source") == "unsplash"],
        }

        result = {
            "success": True,
            "images": self.all_images,
            "total_collected": len(self.all_images),
            "session_id": self.session_id,
            "storage_path": str(storage_path),
            "images_by_source": {key: len(value) for key, value in images_by_source.items()},
            "metadata": {
                "sources": {
                    "pdfs": len(pdfs),
                    "urls": len(urls),
                    "keywords": len(image_keywords),
                },
            },
        }

        logger.info(f"Image collection completed: {len(self.all_images)} total images")
        logger.info(f"  - PDF: {len(images_by_source['pdf'])}")
        logger.info(f"  - Web: {len(images_by_source['web'])}")
        logger.info(f"  - Pexels: {len(images_by_source['pexels'])}")
        logger.info(f"  - Unsplash: {len(images_by_source['unsplash'])}")

        return result

    def _auto_describe_pdf_images(self, pdf_images_by_source: Dict[str, List[Dict]]):
        """
        Automatically generate descriptions for PDF images.

        Args:
            pdf_images_by_source: Dictionary mapping PDF path to list of images
        """
        from lecture_forge.tools.pdf_image_describer import PDFImageDescriber
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

        logger.info("🔍 Generating descriptions for PDF images...")

        total_images = sum(len(images) for images in pdf_images_by_source.values())
        logger.info(f"   Found {total_images} PDF images to describe")

        describer = PDFImageDescriber()
        total_enhanced = 0
        total_cost = 0.0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:

            for pdf_path, images in pdf_images_by_source.items():
                if not images:
                    continue

                task = progress.add_task(f"Describing images from {Path(pdf_path).name}...", total=len(images))

                try:
                    # Get image directory from first image
                    if images:
                        image_dir = Path(images[0]["path"]).parent
                    else:
                        continue

                    # Generate descriptions
                    result = describer.enhance_images(pdf_path=pdf_path, image_dir=str(image_dir))

                    if result["success"]:
                        # Load the generated descriptions
                        descriptions_file = Path(result["descriptions_file"])
                        if descriptions_file.exists():
                            import json

                            with open(descriptions_file, "r", encoding="utf-8") as f:
                                enhanced_images = json.load(f)

                            # Create a mapping: filename -> description
                            desc_map = {Path(img["path"]).name: img["description"] for img in enhanced_images}

                            # Apply descriptions to our images
                            for img in images:
                                img_filename = Path(img["path"]).name
                                if img_filename in desc_map:
                                    img["description"] = desc_map[img_filename]
                                    img["query"] = desc_map[img_filename]  # Also set query for searchability
                                    img["alt_text"] = desc_map[img_filename]

                            total_enhanced += result["enhanced_count"]
                            total_cost += result.get("estimated_cost", 0.0)

                            logger.info(f"   ✅ Enhanced {result['enhanced_count']} images")
                        else:
                            logger.warning(f"   ⚠️  Descriptions file not found: {descriptions_file}")

                    else:
                        logger.error(f"   ❌ Failed to generate descriptions: {result.get('error')}")

                    progress.update(task, completed=len(images))

                except Exception as e:
                    logger.error(f"   ❌ Error describing images from {pdf_path}: {e}")
                    progress.update(task, completed=len(images))

        if total_enhanced > 0:
            logger.info(f"📸 Auto-description complete:")
            logger.info(f"   • Enhanced: {total_enhanced} images")
            logger.info(f"   • Cost: ${total_cost:.4f}")
        else:
            logger.warning("⚠️  No images were enhanced with descriptions")

    def _store_images_in_vector_db(self):
        """
        Store image descriptions in Vector DB for RAG search.

        This enables semantic search across both text and image content,
        allowing better image-content matching during lecture generation.
        """
        if not self.vector_store:
            logger.warning("⚠️  Vector store not available, skipping image indexing")
            return

        # Filter images with descriptions
        images_with_descriptions = [
            img for img in self.all_images if img.get("description") and img.get("description").strip()
        ]

        if not images_with_descriptions:
            logger.warning("⚠️  No images with descriptions to store in Vector DB")
            return

        logger.info(f"💾 Storing {len(images_with_descriptions)} image descriptions in Vector DB...")

        # Prepare data for vector store
        documents = []
        metadatas = []
        ids = []

        for img in images_with_descriptions:
            # Use description as the searchable text
            description = img["description"]

            # Create metadata with all relevant info
            metadata = {
                "type": "image",
                "image_id": img["id"],
                "source": img.get("source", "unknown"),
                "path": img.get("path", ""),
                "hash": img.get("hash", ""),
                "page": img.get("page"),  # PDF page number if applicable
                "width": img.get("width"),
                "height": img.get("height"),
                "query": img.get("query", description),  # Fallback to description
                "alt_text": img.get("alt_text", description),
            }

            documents.append(description)
            metadatas.append(metadata)
            ids.append(f"img_{img['id']}")

        # Store in vector database
        try:
            self.vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            logger.info(f"   ✅ Indexed {len(documents)} images in Vector DB")
            logger.info(f"   → Images now searchable via RAG")
        except Exception as e:
            logger.error(f"   ❌ Failed to store images in Vector DB: {e}")

    def _build_image_page_map(self, pdf_images: List[Dict]) -> Dict[str, Dict[int, List[Dict]]]:
        """
        Build a mapping of source PDF -> page number -> images.

        Args:
            pdf_images: List of images extracted from PDFs

        Returns:
            Dictionary mapping {source_path: {page_num: [image_info, ...]}}
        """
        image_page_map = {}

        for img in pdf_images:
            source = img.get("source", "")
            page = img.get("page")

            if not source or page is None:
                continue

            # Initialize nested structure
            if source not in image_page_map:
                image_page_map[source] = {}

            if page not in image_page_map[source]:
                image_page_map[source][page] = []

            # Store relevant image info
            image_page_map[source][page].append(
                {
                    "id": img["id"],
                    "path": img.get("path", ""),
                    "hash": img.get("hash", ""),
                    "description": img.get("description", ""),
                    "alt_text": img.get("alt_text", ""),
                    "width": img.get("width"),
                    "height": img.get("height"),
                }
            )

        logger.debug(
            f"Built image-page map: {len(image_page_map)} sources, "
            f"{sum(len(pages) for pages in image_page_map.values())} pages"
        )

        return image_page_map

    def _save_image_page_map(self, image_page_map: Dict[str, Dict[int, List[Dict]]]):
        """
        Save image-page mapping to JSON file for later retrieval.

        Args:
            image_page_map: Mapping from _build_image_page_map()
        """
        import json
        from lecture_forge.config import Config

        if not image_page_map:
            logger.debug("No image-page map to save")
            return

        # Save to session directory
        storage_path = Path(Config.DATA_DIR) / "images" / self.session_id
        storage_path.mkdir(parents=True, exist_ok=True)

        map_file = storage_path / "image_page_map.json"

        try:
            with open(map_file, "w", encoding="utf-8") as f:
                json.dump(image_page_map, f, indent=2, ensure_ascii=False)

            logger.info(f"💾 Saved image-page map to {map_file}")
            logger.debug(f"   → {len(image_page_map)} sources mapped")

        except Exception as e:
            logger.error(f"Failed to save image-page map: {e}")

    def get_images_by_keyword(self, keyword: str) -> List[Dict]:
        """
        Get images relevant to a specific keyword.

        Args:
            keyword: Search keyword

        Returns:
            List of relevant images
        """
        relevant = []

        for img in self.all_images:
            # Check if keyword appears in description, alt text, or query
            description = img.get("description", "").lower()
            alt_text = img.get("alt_text", "").lower()
            query = img.get("query", "").lower()

            if keyword.lower() in description or keyword.lower() in alt_text or keyword.lower() in query:
                relevant.append(img)

        return relevant
