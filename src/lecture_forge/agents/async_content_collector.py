"""
Async Content Collector Agent - Collects text content asynchronously.

Major performance improvement through parallel I/O operations:
- PDF parsing in thread pool (CPU-bound)
- Web scraping in parallel (I/O-bound)
- Search API calls in parallel (I/O-bound)

Expected speedup: 5-10 minutes → 2-3 minutes (70% reduction)
"""

import asyncio
from typing import Dict, List

from lecture_forge.agents.async_base import AsyncBaseAgent
from lecture_forge.knowledge.chunker import TextChunker
from lecture_forge.knowledge.vector_store import VectorStore
from lecture_forge.tools.async_search_tool import AsyncSerperSearchTool
from lecture_forge.tools.async_web_scraper import AsyncWebScraperTool
from lecture_forge.tools.pdf_parser import PDFParserTool
from lecture_forge.utils import detect_language, logger


class AsyncContentCollectorAgent(AsyncBaseAgent):
    """
    Async agent for collecting text content from PDFs, URLs, and web search.

    Performs all I/O operations in parallel for maximum performance.
    """

    def __init__(self, collection_name: str = "lecture_content"):
        """
        Initialize Async Content Collector Agent.

        Args:
            collection_name: Name for the vector DB collection
        """
        super().__init__(max_workers=4)  # 4 threads for PDF parsing
        logger.info("Initializing Async Content Collector Agent")

        # Initialize tools
        self.pdf_parser = PDFParserTool()  # Sync tool (CPU-bound)
        self.web_scraper = AsyncWebScraperTool()
        self.search_tool = AsyncSerperSearchTool()

        # Initialize knowledge base components
        self.chunker = TextChunker()
        self.vector_store = VectorStore(collection_name=collection_name)

        # Rate limiters
        self.search_limiter = self.get_rate_limiter(
            "serper", calls_per_minute=30
        )  # Conservative limit
        self.web_limiter = self.get_rate_limiter(
            "web", calls_per_minute=60
        )  # More generous

    async def collect(self, sources: Dict[str, List[str]]) -> Dict:
        """
        Collect content from all sources asynchronously and store in vector DB.

        All I/O operations run in parallel for maximum performance.

        Args:
            sources: Dictionary with keys 'pdfs', 'urls', 'keywords', 'hada_keywords'

        Returns:
            Collection result with documents and chunks
        """
        logger.info("Starting async content collection")

        pdfs = sources.get("pdfs", [])
        urls = sources.get("urls", [])
        keywords = sources.get("keywords", [])
        hada_keywords = sources.get("hada_keywords", [])

        logger.info(
            f"Sources: {len(pdfs)} PDFs, {len(urls)} URLs, "
            f"{len(keywords)} keywords, {len(hada_keywords)} Hada searches"
        )

        # Create tasks for parallel execution
        tasks = []
        task_types = []

        # 1. PDF parsing tasks (run in thread pool)
        for pdf_path in pdfs:
            task = self._collect_from_pdf(pdf_path)
            tasks.append(task)
            task_types.append(("pdf", pdf_path))

        # 2. URL scraping tasks (async HTTP)
        for url in urls:
            task = self._collect_from_url(url)
            tasks.append(task)
            task_types.append(("url", url))

        # 3. Search tasks (async API)
        for keyword in keywords:
            task = self._collect_from_search(keyword)
            tasks.append(task)
            task_types.append(("search", keyword))

        # 4. Hada.io searches (if implemented)
        for hada_keyword in hada_keywords:
            # TODO: Implement async deep crawler
            logger.warning(
                f"Hada.io async crawler not yet implemented, skipping: {hada_keyword}"
            )

        # Execute all tasks in parallel
        logger.info(f"Executing {len(tasks)} collection tasks in parallel...")
        start_time = asyncio.get_event_loop().time()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ All collection tasks completed in {elapsed:.2f}s")

        # Process results
        all_documents = []
        for (task_type, source), result in zip(task_types, results):
            if isinstance(result, Exception):
                logger.error(f"Task failed ({task_type}, {source}): {result}")
            elif result and result.get("success"):
                all_documents.append(result["document"])
            else:
                logger.warning(f"Task returned no data ({task_type}, {source})")

        logger.info(f"Successfully collected {len(all_documents)} documents")

        # 5. Chunk all documents
        logger.info("Chunking collected documents...")
        all_chunks, chunk_metadatas = await self._chunk_documents_async(
            all_documents
        )

        logger.info(f"Total chunks created: {len(all_chunks)}")

        # 6. Store in vector database (sync operation, but fast)
        if all_chunks:
            logger.info("Storing in vector database...")
            chunk_ids = [f"chunk_{i}" for i in range(len(all_chunks))]

            # Run in executor to avoid blocking
            await self.run_in_executor(
                self.vector_store.add_documents,
                documents=all_chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
            )

            stats = self.vector_store.get_stats()
            logger.info(f"✅ Vector DB updated: {stats['document_count']} total documents")

        # 7. Return collection result
        result = {
            "success": True,
            "documents": all_documents,
            "chunks": all_chunks,
            "chunk_ids": [f"chunk_{i}" for i in range(len(all_chunks))],
            "metadata": {
                "total_docs": len(all_documents),
                "total_chunks": len(all_chunks),
                "sources": {
                    "pdfs": len(pdfs),
                    "urls": len(urls),
                    "keywords": len(keywords),
                },
                "vector_db": self.vector_store.get_stats(),
                "elapsed_seconds": elapsed,
            },
        }

        logger.info(f"Content collection completed in {elapsed:.2f}s")
        return result

    async def _collect_from_pdf(self, pdf_path: str) -> Dict:
        """
        Collect content from PDF (CPU-bound, run in thread pool).

        Args:
            pdf_path: Path to PDF file

        Returns:
            Result dict with document
        """
        try:
            logger.info(f"Processing PDF: {pdf_path}")

            # Run PDF parsing in thread pool (CPU-bound)
            result = await self.run_in_executor(self.pdf_parser.run, pdf_path)

            if result["success"]:
                document = {
                    "text": result["text"],
                    "source": pdf_path,
                    "source_type": "pdf",
                    "metadata": result["metadata"],
                    "pages": result.get("pages", []),
                }

                logger.info(f"✅ Collected from PDF: {len(result['text'])} characters")
                return {"success": True, "document": document}
            else:
                logger.error(f"❌ Failed to parse PDF: {result['error']}")
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return {"success": False, "error": str(e)}

    async def _collect_from_url(self, url: str) -> Dict:
        """
        Collect content from URL (I/O-bound, async).

        Args:
            url: URL to scrape

        Returns:
            Result dict with document
        """
        try:
            logger.info(f"Processing URL: {url}")

            # Rate limiting
            async with self.web_limiter:
                result = await self.web_scraper.run(url)

            if result["success"]:
                document = {
                    "text": result["text"],
                    "source": url,
                    "source_type": "url",
                    "metadata": result["metadata"],
                }

                logger.info(f"✅ Collected from URL: {len(result['text'])} characters")
                return {"success": True, "document": document}
            else:
                logger.error(f"❌ Failed to scrape URL: {result['error']}")
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return {"success": False, "error": str(e)}

    async def _collect_from_search(self, keyword: str) -> Dict:
        """
        Collect content from web search (I/O-bound, async).

        Args:
            keyword: Search keyword

        Returns:
            Result dict with document
        """
        try:
            logger.info(f"Searching for: {keyword}")

            # Rate limiting
            async with self.search_limiter:
                result = await self.search_tool.run(keyword, num_results=5)

            if result["success"]:
                # Create a summary document from search results
                search_text = f"Search results for '{keyword}':\n\n"
                for i, item in enumerate(result["results"], 1):
                    search_text += f"{i}. {item['title']}\n"
                    search_text += f"{item['snippet']}\n"
                    search_text += f"URL: {item['url']}\n\n"

                document = {
                    "text": search_text,
                    "source": f"search:{keyword}",
                    "source_type": "search",
                    "metadata": {
                        "query": keyword,
                        "total_results": result["total_results"],
                    },
                }

                logger.info(f"✅ Collected {result['total_results']} search results")
                return {"success": True, "document": document}
            else:
                logger.error(f"❌ Search failed: {result['error']}")
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error searching for {keyword}: {e}")
            return {"success": False, "error": str(e)}

    async def _chunk_documents_async(
        self, documents: List[Dict]
    ) -> tuple[List[str], List[Dict]]:
        """
        Chunk all documents (CPU-bound, run in thread pool).

        Args:
            documents: List of document dicts

        Returns:
            Tuple of (chunks, metadatas)
        """
        all_chunks = []
        chunk_metadatas = []

        for doc_idx, doc in enumerate(documents):
            # For PDFs, chunk by page to preserve page information
            if doc["source_type"] == "pdf":
                chunks, metadatas = await self.run_in_executor(
                    self._chunk_pdf_with_pages, doc
                )
                all_chunks.extend(chunks)
                chunk_metadatas.extend(metadatas)
            else:
                # For other sources, chunk normally
                chunks = await self.run_in_executor(
                    self.chunker.chunk_text, doc["text"]
                )

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
                            "language": chunk_language,
                            **doc["metadata"],
                        }
                    )

        return all_chunks, chunk_metadatas

    def _chunk_pdf_with_pages(self, doc: dict) -> tuple:
        """
        Chunk PDF document while preserving page information (sync).

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
                chunk_language = detect_language(chunk, default="unknown")

                chunks.append(chunk)
                metadatas.append(
                    {
                        "source": doc["source"],
                        "source_type": "pdf",
                        "chunk_index": chunk_idx,
                        "language": chunk_language,
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
                chunk_language = detect_language(chunk, default="unknown")

                chunks.append(chunk)
                metadatas.append(
                    {
                        "source": doc["source"],
                        "source_type": "pdf",
                        "page_number": page_num,
                        "chunk_index": chunk_idx,
                        "total_pages": doc["metadata"].get("total_pages", 0),
                        "language": chunk_language,
                    }
                )

        logger.debug(f"  Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks, metadatas

    async def query(self, question: str, n_results: int = 5) -> Dict:
        """
        Query the collected content (async).

        Args:
            question: Question to search for
            n_results: Number of results to return

        Returns:
            Query results with documents and metadata
        """
        logger.info(f"Querying: {question}")

        # Run query in executor (ChromaDB is sync)
        results = await self.run_in_executor(
            self.vector_store.query, question, n_results=n_results
        )

        return {
            "question": question,
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }
