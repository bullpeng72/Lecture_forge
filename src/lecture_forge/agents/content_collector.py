"""
Content Collector Agent - Collects text content from various sources.
"""

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from lecture_forge.agents.base import BaseAgent
from lecture_forge.config import Config
from lecture_forge.exceptions import PDFParsingError, SearchAPIError, WebScrapingError
from lecture_forge.knowledge.chunker import TextChunker
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.tools.deep_web_crawler import DeepWebCrawler
from lecture_forge.tools.pdf_parser import PDFParserTool
from lecture_forge.tools.search_tool import SerperSearchTool
from lecture_forge.tools.web_scraper import WebScraperTool
from lecture_forge.utils import detect_language, logger


class ContentCollectorAgent(BaseAgent):
    """Agent for collecting text content from PDFs, URLs, and web search."""

    def __init__(self, collection_name: str = "lecture_content"):
        """
        Initialize Content Collector Agent.

        Args:
            collection_name: Name for the vector DB collection
        """
        super().__init__()
        logger.info("Initializing Content Collector Agent")

        # Initialize tools
        self.pdf_parser = PDFParserTool()
        self.web_scraper = WebScraperTool()
        self.search_tool = SerperSearchTool()
        self.deep_crawler = DeepWebCrawler()  # Uses Config defaults

        # Initialize knowledge base components
        self.chunker = TextChunker()
        self.vector_store = VectorStore(collection_name=collection_name)

    def collect(self, sources: Dict[str, List[str]]) -> Dict:
        """
        Collect content from all sources and store in vector DB.

        Args:
            sources: Dictionary with keys 'pdfs', 'urls', 'keywords', 'hada_keywords'

        Returns:
            Collection result with documents and chunks
        """
        logger.info("Starting content collection")

        pdfs = sources.get("pdfs", [])
        urls = sources.get("urls", [])
        keywords = sources.get("keywords", [])
        hada_keywords = sources.get("hada_keywords", [])

        logger.info(
            f"Sources: {len(pdfs)} PDFs, {len(urls)} URLs, " f"{len(keywords)} keywords, {len(hada_keywords)} Hada searches"
        )

        all_documents = []

        # 1. Collect from PDFs
        for pdf_path in pdfs:
            try:
                logger.info(f"Processing PDF: {pdf_path}")
                result = self.pdf_parser.run(pdf_path)

                if result["success"]:
                    all_documents.append(
                        {
                            "text": result["text"],
                            "source": pdf_path,
                            "source_type": "pdf",
                            "metadata": result["metadata"],
                            "pages": result.get("pages", []),  # Store page information
                        }
                    )
                    logger.info(f"✅ Collected from PDF: {len(result['text'])} characters")
                else:
                    logger.error(f"❌ Failed to parse PDF: {result['error']}")

            except Exception as e:
                logger.error(f"Error processing PDF {pdf_path}: {PDFParsingError(e)}")

        # 2. Collect from URLs
        for url in urls:
            try:
                logger.info(f"Processing URL: {url}")
                result = self.web_scraper.run(url)

                if result["success"]:
                    all_documents.append(
                        {
                            "text": result["text"],
                            "source": url,
                            "source_type": "url",
                            "metadata": result["metadata"],
                        }
                    )
                    logger.info(f"✅ Collected from URL: {len(result['text'])} characters")
                else:
                    logger.error(f"❌ Failed to scrape URL: {result['error']}")

            except Exception as e:
                logger.error(f"Error processing URL {url}: {WebScrapingError(e)}")

        # 3. Collect from web searches
        for keyword in keywords:
            try:
                logger.info(f"Searching for: {keyword}")
                result = self.search_tool.run(keyword, num_results=Config.SEARCH_NUM_RESULTS)

                if result["success"]:
                    # Store each result as an individual snippet document
                    for i, item in enumerate(result["results"]):
                        snippet_text = f"{item['title']}\n{item['snippet']}"
                        if item.get("url"):
                            snippet_text += f"\nURL: {item['url']}"

                        all_documents.append(
                            {
                                "text": snippet_text,
                                "source": item.get("url") or f"search:{keyword}:{i}",
                                "source_type": "search_snippet",
                                "metadata": {
                                    "query": keyword,
                                    "title": item.get("title", ""),
                                    "position": item.get("position", i),
                                    "result_type": item.get("type", "organic"),
                                },
                            }
                        )
                    logger.info(f"✅ Stored {len(result['results'])} search snippets for '{keyword}'")

                    # Optionally fetch full pages in parallel (SEARCH_FETCH_FULL_PAGES=true)
                    if Config.SEARCH_FETCH_FULL_PAGES:
                        fetched = self._fetch_search_urls_parallel(
                            result["results"], keyword=keyword, top_n=Config.SEARCH_FETCH_TOP_N
                        )
                        all_documents.extend(fetched)
                        logger.info(f"  📄 Fetched {len(fetched)} full pages for '{keyword}'")
                else:
                    logger.error(f"❌ Search failed: {result['error']}")

            except Exception as e:
                logger.error(f"Error searching for {keyword}: {SearchAPIError(e)}")

        # 4. Deep crawl Hada.io searches
        for hada_keyword in hada_keywords:
            try:
                logger.info(f"Deep crawling Hada.io for: {hada_keyword}")
                crawled_pages = self.deep_crawler.crawl_hada_search(hada_keyword)

                logger.info(f"✅ Crawled {len(crawled_pages)} pages from Hada.io")

                # Add each crawled page as a document
                for page in crawled_pages:
                    all_documents.append(
                        {
                            "text": page["text"],
                            "source": page["url"],
                            "source_type": f"hada_{page['type']}",  # hada_search_page or hada_article
                            "metadata": {
                                **page["metadata"],
                                "search_keyword": hada_keyword,
                                "page_type": page["type"],
                            },
                        }
                    )

            except Exception as e:
                logger.error(f"Error deep crawling Hada.io for {hada_keyword}: {WebScrapingError(e)}")

        # 5. Chunk all documents
        logger.info("Chunking collected documents...")
        all_chunks = []
        chunk_metadatas = []

        for doc_idx, doc in enumerate(all_documents):
            # For PDFs, chunk by page to preserve page information
            if doc["source_type"] == "pdf":
                chunks, metadatas = self._chunk_pdf_with_pages(doc)
                all_chunks.extend(chunks)
                chunk_metadatas.extend(metadatas)
            else:
                # For other sources, chunk normally
                chunks = self.chunker.chunk_text(doc["text"])

                for chunk_idx, chunk in enumerate(chunks):
                    # Detect chunk language
                    chunk_language = detect_language(chunk, default="unknown")

                    all_chunks.append(chunk)
                    chunk_metadatas.append(
                        {
                            "source": doc["source"],
                            "source_type": doc["source_type"],
                            "chunk_index": chunk_idx,
                            "document_index": doc_idx,
                            "language": chunk_language,  # ← Language detection
                            **doc["metadata"],
                        }
                    )

        logger.info(f"Total chunks created: {len(all_chunks)}")

        # J: SHA256-based deduplication — remove duplicate chunks before storing
        _seen_hashes: set = set()
        _deduped_chunks: list = []
        _deduped_metas: list = []
        for chunk, meta in zip(all_chunks, chunk_metadatas):
            h = hashlib.sha256(chunk.encode("utf-8", errors="replace")).hexdigest()
            if h not in _seen_hashes:
                _seen_hashes.add(h)
                _deduped_chunks.append(chunk)
                _deduped_metas.append(meta)
        dup_count = len(all_chunks) - len(_deduped_chunks)
        if dup_count:
            logger.info(
                f"🧹 Deduplication: removed {dup_count} duplicate chunks "
                f"({len(_deduped_chunks)} unique remain)"
            )
        all_chunks, chunk_metadatas = _deduped_chunks, _deduped_metas

        # 5. Store in vector database
        if all_chunks:
            logger.info("Storing in vector database...")
            chunk_ids = [str(uuid.uuid4()) for _ in all_chunks]

            self.vector_store.add_documents(
                documents=all_chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
            )

            stats = self.vector_store.get_stats()
            logger.info(f"✅ Vector DB updated: {stats['document_count']} total documents")

        # 6. Return collection result
        chunk_ids = [str(uuid.uuid4()) for _ in all_chunks]
        result = {
            "success": True,
            "documents": all_documents,
            "chunks": all_chunks,
            "chunk_ids": chunk_ids,
            "metadata": {
                "total_docs": len(all_documents),
                "total_chunks": len(all_chunks),
                "sources": {
                    "pdfs": len(pdfs),
                    "urls": len(urls),
                    "keywords": len(keywords),
                },
                "vector_db": self.vector_store.get_stats(),
            },
        }

        logger.info("Content collection completed")
        return result

    def _chunk_pdf_with_pages(self, doc: dict) -> tuple:
        """
        Chunk PDF document while preserving page information.

        Args:
            doc: Document dictionary with 'pages' information

        Returns:
            Tuple of (chunks, metadatas)
        """
        chunks = []
        metadatas = []

        pages = doc.get("pages", [])

        if not pages:
            # Fallback to regular chunking if no page info
            doc_chunks = self.chunker.chunk_text(doc["text"])
            for chunk_idx, chunk in enumerate(doc_chunks):
                # Detect chunk language
                chunk_language = detect_language(chunk, default="unknown")

                chunks.append(chunk)
                metadatas.append(
                    {
                        "source": doc["source"],
                        "source_type": "pdf",
                        "chunk_index": chunk_idx,
                        "language": chunk_language,  # ← Language detection
                        **doc["metadata"],
                    }
                )
            return chunks, metadatas

        # Chunk by page
        for page_data in pages:
            page_num = page_data["page_number"]
            page_text = page_data["text"]

            if not page_text.strip():
                continue

            # Chunk this page's text
            page_chunks = self.chunker.chunk_text(page_text)

            for chunk_idx, chunk in enumerate(page_chunks):
                # Detect chunk language
                chunk_language = detect_language(chunk, default="unknown")

                chunks.append(chunk)
                metadatas.append(
                    {
                        "source": doc["source"],
                        "source_type": "pdf",
                        "page_number": page_num,  # ✅ Page number preserved
                        "chunk_index": chunk_idx,
                        "total_pages": doc["metadata"].get("total_pages", 0),
                        "language": chunk_language,  # ← Language detection
                    }
                )

        logger.debug(f"  Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks, metadatas

    def _fetch_search_urls_parallel(self, results: List[Dict], keyword: str, top_n: int) -> List[Dict]:
        """
        Fetch full page content for top-N search result URLs in parallel.

        Args:
            results: List of search result dicts (with 'url', 'title', etc.)
            keyword: Original search keyword (for metadata)
            top_n: Maximum number of URLs to fetch

        Returns:
            List of document dicts with full page content (source_type="search_full")
        """
        urls_to_fetch = [(i, item) for i, item in enumerate(results[:top_n]) if item.get("url")]
        if not urls_to_fetch:
            return []

        def _fetch_one(idx_item):
            idx, item = idx_item
            url = item["url"]
            try:
                scrape_result = self.web_scraper.run(url)
                if scrape_result["success"] and scrape_result.get("text", "").strip():
                    return {
                        "text": scrape_result["text"],
                        "source": url,
                        "source_type": "search_full",
                        "metadata": {
                            "query": keyword,
                            "title": item.get("title", ""),
                            "position": item.get("position", idx),
                            "result_type": item.get("type", "organic"),
                            **scrape_result.get("metadata", {}),
                        },
                    }
            except Exception as e:
                logger.warning(f"  ⚠️ Could not fetch {url}: {e}")
            return None

        fetched_docs = []
        with ThreadPoolExecutor(max_workers=min(top_n, 5)) as executor:
            futures = {executor.submit(_fetch_one, idx_item): idx_item for idx_item in urls_to_fetch}
            for future in as_completed(futures):
                doc = future.result()
                if doc is not None:
                    fetched_docs.append(doc)

        return fetched_docs

    def query(self, question: str, n_results: int = 5) -> Dict:
        """
        Query the collected content.

        Args:
            question: Question to search for
            n_results: Number of results to return

        Returns:
            Query results with documents and metadata
        """
        logger.info(f"Querying: {question}")
        results = self.vector_store.query(question, n_results=n_results)

        return {
            "question": question,
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }
