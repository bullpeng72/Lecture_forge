"""
Image Editor Tool - Edit images in generated HTML lectures.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from lecture_forge.config import Config
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.utils import logger


class ImageEditor:
    """Tool for editing images in HTML lectures."""

    def __init__(self, html_path: str):
        """
        Initialize Image Editor.

        Args:
            html_path: Path to HTML lecture file
        """
        self.html_path = Path(html_path)

        if not self.html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        # Load HTML
        with open(self.html_path, "r", encoding="utf-8") as f:
            self.html_content = f.read()

        self.soup = BeautifulSoup(self.html_content, "html.parser")

        # Extract images and diagrams
        self.images = self._extract_images()
        self.diagrams = self._extract_diagrams()

        # Track changes
        self.changes = {
            "delete": set(),          # image indices to delete
            "replace": {},            # image index -> new image info
            "add": [],                # new images to add
            "diagram_delete": set(),  # diagram indices to delete
        }

        # Initialize Vector Store (for finding alternatives)
        self.vector_store = None
        self._init_vector_store()

        logger.info(f"Image Editor initialized: {len(self.images)} images, {len(self.diagrams)} diagrams found")

    def _init_vector_store(self):
        """Initialize Vector Store if available."""
        try:
            # Try to find the most recent vector DB
            vector_db_base = Config.VECTOR_DB_PATH
            if not vector_db_base.exists():
                logger.warning("Vector DB not found - alternative image search disabled")
                return

            # Find all collection directories
            collections = [d for d in vector_db_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if not collections:
                logger.warning("No vector DB collections found")
                return

            # Use the most recent one
            latest_collection = max(collections, key=lambda d: d.stat().st_mtime)
            collection_name = latest_collection.name

            # Load Vector Store with collection name (not persist_directory)
            # VectorStore will construct the full path: Config.VECTOR_DB_PATH / collection_name
            self.vector_store = VectorStore(collection_name=collection_name)
            logger.info(f"Loaded Vector DB: {collection_name}")

        except Exception as e:
            logger.warning(f"Could not initialize Vector Store: {e}")
            self.vector_store = None

    def _extract_images(self) -> List[Dict]:
        """
        Extract all images from HTML.

        Returns:
            List of image metadata dictionaries
        """
        images = []

        # Find all img tags
        img_tags = self.soup.find_all("img")

        for idx, img_tag in enumerate(img_tags, 1):
            # Extract metadata
            img_info = {
                "index": idx,
                "tag": img_tag,
                "src": img_tag.get("src", ""),
                "alt": img_tag.get("alt", ""),
                "caption": self._extract_caption(img_tag),
                "section": self._find_section(img_tag),
                "page": self._extract_page_number(img_tag),
            }

            images.append(img_info)

        return images

    def _extract_diagrams(self) -> List[Dict]:
        """Extract all Mermaid diagrams from HTML.

        Returns:
            List of diagram metadata dictionaries
        """
        diagrams = []

        mermaid_divs = self.soup.find_all("div", class_="mermaid")
        for idx, mermaid_div in enumerate(mermaid_divs, 1):
            # Outer wrapper div (contains title h4 + mermaid div)
            container = mermaid_div.find_parent("div", class_="my-8") or mermaid_div

            # Title from h4 inside the container
            h4 = container.find("h4") if container is not mermaid_div else None
            title = h4.get_text(strip=True) if h4 else f"다이어그램 {idx}"

            # Mermaid code and type (first keyword)
            code = mermaid_div.get_text(strip=True)
            words = code.split()
            diagram_type = words[0].lower() if words else "diagram"

            diagrams.append({
                "index": idx,
                "mermaid_div": mermaid_div,   # used for DOM-order walking
                "container": container,        # decompose() target
                "mermaid_code": code,
                "title": title,
                "diagram_type": diagram_type,
                "section": self._find_section(mermaid_div),
            })

        return diagrams

    def _extract_caption(self, img_tag) -> str:
        """Extract caption from figure or nearby elements."""
        # Try to find parent figure
        figure = img_tag.find_parent("figure")
        if figure:
            figcaption = figure.find("figcaption")
            if figcaption:
                return figcaption.get_text(strip=True)

        # Try to find caption in attribution
        if "attribution" in img_tag.get("data-attribution", ""):
            return img_tag.get("data-attribution", "")

        return ""

    def _find_section(self, img_tag) -> str:
        """Find which section the image belongs to."""
        # Find nearest section header
        for parent in img_tag.parents:
            if parent.name in ["section", "div"]:
                # Look for heading
                heading = parent.find(["h1", "h2", "h3"])
                if heading:
                    return heading.get_text(strip=True)

        return "Unknown section"

    def _extract_page_number(self, img_tag) -> Optional[int]:
        """Extract page number from image metadata."""
        # Check alt text or caption for page number
        alt_text = img_tag.get("alt", "")
        caption = self._extract_caption(img_tag)

        import re

        for text in [alt_text, caption]:
            match = re.search(r"page\s+(\d+)", text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def list_images(self) -> List[Dict]:
        """
        Get list of images with metadata.

        Returns:
            List of image info dictionaries
        """
        image_list = []

        for img in self.images:
            # Mark if scheduled for deletion
            status = "delete" if img["index"] in self.changes["delete"] else "keep"
            if img["index"] in self.changes["replace"]:
                status = "replace"

            image_list.append(
                {
                    "index": img["index"],
                    "description": img["alt"][:50] if img["alt"] else "No description",
                    "caption": img["caption"][:50] if img["caption"] else "",
                    "section": img["section"][:40],
                    "page": img["page"],
                    "status": status,
                }
            )

        return image_list

    def list_elements(self) -> List[Dict]:
        """Return images and diagrams unified in HTML document order.

        Each element dict contains:
            display_index  - unified 1-based display number
            kind           - "image" or "diagram"
            img_index      - image index (kind=="image"), else None
            dgm_index      - diagram index (kind=="diagram"), else None
            title          - display title / alt text
            section        - section heading the element belongs to
            extra          - page number (images) or diagram type (diagrams)
            status         - "keep" / "delete" / "replace"
        """
        img_by_id = {id(img["tag"]): img for img in self.images}
        dgm_by_id = {id(dgm["mermaid_div"]): dgm for dgm in self.diagrams}

        elements = []
        seen_dgm_ids: set = set()

        for tag in self.soup.descendants:
            if not hasattr(tag, "name") or tag.name is None:
                continue

            if tag.name == "img" and id(tag) in img_by_id:
                img = img_by_id[id(tag)]
                status = (
                    "delete" if img["index"] in self.changes["delete"]
                    else "replace" if img["index"] in self.changes["replace"]
                    else "keep"
                )
                elements.append({
                    "kind": "image",
                    "img_index": img["index"],
                    "dgm_index": None,
                    "title": (img["alt"] or img["caption"] or "설명 없음")[:50],
                    "section": img["section"],
                    "extra": f"p.{img['page']}" if img["page"] else "-",
                    "status": status,
                })

            elif tag.name == "div" and "mermaid" in (tag.get("class") or []):
                tag_id = id(tag)
                if tag_id in dgm_by_id and tag_id not in seen_dgm_ids:
                    seen_dgm_ids.add(tag_id)
                    dgm = dgm_by_id[tag_id]
                    status = "delete" if dgm["index"] in self.changes["diagram_delete"] else "keep"
                    elements.append({
                        "kind": "diagram",
                        "img_index": None,
                        "dgm_index": dgm["index"],
                        "title": dgm["title"][:50],
                        "section": dgm["section"],
                        "extra": dgm["diagram_type"],
                        "status": status,
                    })

        for i, el in enumerate(elements, 1):
            el["display_index"] = i

        return elements

    def mark_delete(self, image_index: int) -> bool:
        """
        Mark an image for deletion.

        Args:
            image_index: Image index (1-based)

        Returns:
            True if successful
        """
        if not (1 <= image_index <= len(self.images)):
            logger.error(f"Invalid image index: {image_index}")
            return False

        self.changes["delete"].add(image_index)
        logger.info(f"Marked image {image_index} for deletion")
        return True

    def unmark_delete(self, image_index: int) -> bool:
        """
        Unmark an image for deletion.

        Args:
            image_index: Image index (1-based)

        Returns:
            True if successful
        """
        if image_index in self.changes["delete"]:
            self.changes["delete"].remove(image_index)
            logger.info(f"Unmarked image {image_index} for deletion")
            return True
        return False

    def mark_delete_diagram(self, dgm_index: int) -> bool:
        """Mark a diagram for deletion.

        Args:
            dgm_index: Diagram index (1-based)

        Returns:
            True if successful
        """
        if not (1 <= dgm_index <= len(self.diagrams)):
            logger.error(f"Invalid diagram index: {dgm_index}")
            return False
        self.changes["diagram_delete"].add(dgm_index)
        logger.info(f"Marked diagram {dgm_index} for deletion")
        return True

    def unmark_delete_diagram(self, dgm_index: int) -> bool:
        """Unmark a diagram for deletion.

        Args:
            dgm_index: Diagram index (1-based)

        Returns:
            True if the diagram was in the delete set
        """
        if dgm_index in self.changes["diagram_delete"]:
            self.changes["diagram_delete"].discard(dgm_index)
            logger.info(f"Unmarked diagram {dgm_index} for deletion")
            return True
        return False

    def find_alternative_images(self, image_index: int, max_results: int = 5) -> List[Dict]:
        """
        Find alternative images from Vector DB or filesystem.

        Args:
            image_index: Image index to replace
            max_results: Maximum number of alternatives

        Returns:
            List of alternative image metadata
        """
        if not (1 <= image_index <= len(self.images)):
            logger.error(f"Invalid image index: {image_index}")
            return []

        # Get current image info
        current_img = self.images[image_index - 1]

        # Try Vector DB first (if available)
        if self.vector_store:
            alternatives = self._search_vector_db(current_img, max_results)
            if alternatives:
                return alternatives
            logger.info("No alternatives in Vector DB, trying filesystem search...")

        # Fallback to filesystem search
        return self._search_filesystem(current_img, max_results)

    def _search_vector_db(self, current_img: Dict, max_results: int) -> List[Dict]:
        """
        Search for alternative images in Vector DB.

        Args:
            current_img: Current image info
            max_results: Maximum number of results

        Returns:
            List of alternative images
        """
        # Build search query from context
        query_parts = []
        if current_img["section"]:
            query_parts.append(current_img["section"])
        if current_img["alt"]:
            query_parts.append(current_img["alt"])
        if current_img["caption"]:
            query_parts.append(current_img["caption"])

        query = " ".join(query_parts)

        if not query:
            return []

        logger.info(f"Searching Vector DB: '{query[:100]}'")

        try:
            results = self.vector_store.query(query, n_results=max_results * 3)

            if not results or not results.get("documents"):
                return []

            # Filter for image-type documents
            alternatives = []
            metadatas = results.get("metadatas", [[]])[0]
            documents = results["documents"][0]

            for idx, metadata in enumerate(metadatas):
                if metadata.get("type") == "image":
                    # Check if image file still exists
                    img_path = metadata.get("path", "")
                    if img_path and Path(img_path).exists():
                        alternatives.append(
                            {
                                "index": len(alternatives) + 1,
                                "path": img_path,
                                "description": documents[idx][:100],
                                "page": metadata.get("page"),
                                "source": Path(metadata.get("source", "")).name,
                            }
                        )

                    if len(alternatives) >= max_results:
                        break

            if alternatives:
                logger.info(f"Found {len(alternatives)} images in Vector DB")
            return alternatives

        except Exception as e:
            logger.debug(f"Vector DB search error: {e}")
            return []

    def _search_filesystem(self, current_img: Dict, max_results: int) -> List[Dict]:
        """
        Search for alternative images in filesystem.

        Searches in data/images/ directory for images from the same source
        or nearby pages.

        Args:
            current_img: Current image info
            max_results: Maximum number of results

        Returns:
            List of alternative images
        """
        logger.info("Searching filesystem for alternative images...")

        # Try multiple locations for image directories
        # Prioritize Config.DATA_DIR (centralized storage)
        possible_bases = [
            Config.DATA_DIR / "images",  # User config directory (primary location)
            self.html_path.parent.parent / "data" / "images",  # Relative to HTML (fallback)
            Path.cwd() / "data" / "images",  # Current working directory (dev mode fallback)
        ]

        images_base = None
        for base in possible_bases:
            if base.exists():
                # Check if there are actually images in this directory
                has_images = any(
                    f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".gif"]
                    for d in base.iterdir() if d.is_dir()
                    for f in d.rglob("*") if f.is_file()
                )
                if has_images:
                    images_base = base
                    logger.info(f"Found images directory: {base}")
                    break

        if not images_base:
            logger.warning("Images directory not found in any location")
            return []

        alternatives = []
        current_page = current_img.get("page")
        current_src = current_img.get("src", "")

        logger.info(f"Searching for images near page {current_page}...")

        # Search all session directories
        session_count = 0
        for session_dir in images_base.iterdir():
            if not session_dir.is_dir() or session_dir.name.startswith("."):
                continue
            session_count += 1

            # Check for PDF images
            for img_file in session_dir.rglob("*"):
                if not img_file.is_file():
                    continue

                # Check if it's an image file
                if img_file.suffix.lower() not in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    continue

                # Skip if it's the current image
                if str(img_file) == current_src or img_file.name in current_src:
                    continue

                # Try to extract page number from filename or metadata
                page_match = None
                import re
                page_pattern = re.search(r"page_?(\d+)", img_file.stem, re.IGNORECASE)
                if page_pattern:
                    page_match = int(page_pattern.group(1))

                # Calculate relevance score
                score = 0
                if page_match and current_page:
                    # Prefer images from nearby pages
                    page_diff = abs(page_match - current_page)
                    if page_diff == 0:
                        score = 100
                    elif page_diff <= 2:
                        score = 50
                    elif page_diff <= 5:
                        score = 25
                    else:
                        score = 10
                else:
                    score = 5  # Unknown page

                alternatives.append({
                    "path": str(img_file),
                    "page": page_match,
                    "source": img_file.parent.name,
                    "filename": img_file.name,
                    "score": score,
                })

        logger.info(f"Scanned {session_count} session(s), found {len(alternatives)} candidates")

        # Sort by score and limit results
        alternatives.sort(key=lambda x: x["score"], reverse=True)
        alternatives = alternatives[:max_results]

        # Add index and description
        for idx, alt in enumerate(alternatives, 1):
            alt["index"] = idx
            alt["description"] = f"Image from {alt['source']}"
            if alt["page"]:
                alt["description"] += f" (page {alt['page']})"

        if alternatives:
            logger.info(f"Found {len(alternatives)} alternative images in filesystem")
        else:
            logger.warning("No alternative images found")

        return alternatives

    def replace_image(self, image_index: int, new_image_path: str) -> bool:
        """
        Mark an image for replacement.

        Args:
            image_index: Image index to replace
            new_image_path: Path to new image

        Returns:
            True if successful
        """
        if not (1 <= image_index <= len(self.images)):
            logger.error(f"Invalid image index: {image_index}")
            return False

        if not Path(new_image_path).exists():
            logger.error(f"New image file not found: {new_image_path}")
            return False

        self.changes["replace"][image_index] = {
            "new_path": new_image_path,
        }

        logger.info(f"Marked image {image_index} for replacement")
        return True

    def save_changes(self, output_path: Optional[str] = None) -> str:
        """
        Apply changes and save modified HTML.

        Args:
            output_path: Output file path (default: original_edited.html)

        Returns:
            Path to saved file
        """
        if output_path is None:
            # Generate default output path
            output_path = str(self.html_path.parent / f"{self.html_path.stem}_edited{self.html_path.suffix}")

        # Apply changes to soup
        changes_made = 0

        # 1. Delete images
        for img_index in sorted(self.changes["delete"], reverse=True):
            img_info = self.images[img_index - 1]
            img_tag = img_info["tag"]

            # Remove entire figure if exists, otherwise just img
            figure = img_tag.find_parent("figure")
            if figure:
                figure.decompose()
            else:
                img_tag.decompose()

            changes_made += 1
            logger.debug(f"Deleted image {img_index}")

        # 2. Replace images
        for img_index, replacement in self.changes["replace"].items():
            img_info = self.images[img_index - 1]
            img_tag = img_info["tag"]

            # Update src attribute
            new_path = replacement["new_path"]

            # Convert to relative path if possible
            try:
                rel_path = Path(new_path).relative_to(self.html_path.parent)
                img_tag["src"] = str(rel_path)
            except ValueError:
                # Use absolute path
                img_tag["src"] = new_path

            changes_made += 1
            logger.debug(f"Replaced image {img_index}")

        # 3. Delete diagrams
        for dgm_index in sorted(self.changes["diagram_delete"], reverse=True):
            dgm = self.diagrams[dgm_index - 1]
            dgm["container"].decompose()
            changes_made += 1
            logger.debug(f"Deleted diagram {dgm_index}")

        # 4. Update image/diagram counts in sidebar/header stats
        remaining_images = len(self.soup.find_all("img"))
        for text_node in self.soup.find_all(string=re.compile(r"이미지\s*\d+개")):
            new_text = re.sub(r"(이미지\s*)\d+(개)", rf"\g<1>{remaining_images}\g<2>", str(text_node))
            text_node.replace_with(new_text)
        logger.debug(f"Updated image count to {remaining_images} in HTML stats")

        remaining_diagrams = len(self.soup.find_all("div", class_="mermaid"))
        for text_node in self.soup.find_all(string=re.compile(r"다이어그램\s*\d+개")):
            new_text = re.sub(r"(다이어그램\s*)\d+(개)", rf"\g<1>{remaining_diagrams}\g<2>", str(text_node))
            text_node.replace_with(new_text)
        logger.debug(f"Updated diagram count to {remaining_diagrams} in HTML stats")

        # Save modified HTML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(self.soup))

        logger.info(f"Saved {changes_made} changes to {output_path}")
        return output_path

    def get_summary(self) -> Dict:
        """
        Get summary of pending changes.

        Returns:
            Summary dictionary
        """
        return {
            "total_images": len(self.images),
            "to_delete": len(self.changes["delete"]),
            "to_replace": len(self.changes["replace"]),
            "to_add": len(self.changes["add"]),
            "total_diagrams": len(self.diagrams),
            "diagrams_to_delete": len(self.changes["diagram_delete"]),
        }
