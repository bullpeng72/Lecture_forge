"""
Integration tests for content collection pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock

from lecture_forge.knowledge.vector_store import VectorStore


@pytest.mark.integration
class TestContentCollectionPipeline:
    """Test content collection and processing."""

    @patch("lecture_forge.tools.pdf_parser.fitz")
    def test_pdf_to_knowledge_base(self, mock_fitz, temp_dir, sample_pdf_path, test_env_vars):
        """Test PDF processing to knowledge base."""
        # Mock PDF parsing
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample PDF content about machine learning"

        # Mock document methods
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page  # Enable doc[0] access
        mock_doc.metadata = {
            "title": "ML Tutorial",
            "author": "Test Author",
            "subject": "",
            "creator": "",
            "producer": "",
            "creationDate": "",
            "modDate": "",
        }
        mock_doc.close = MagicMock()  # Mock close method
        mock_fitz.open.return_value = mock_doc

        # Create collection agent
        collection_name = "pdf_test"

        vector_store = VectorStore(collection_name=collection_name)

        # In a real scenario, ContentCollectorAgent would:
        # 1. Parse PDF
        # 2. Chunk text
        # 3. Add to vector store
        # For now, we'll test the components separately

        from lecture_forge.tools.pdf_parser import PDFParserTool
        from lecture_forge.knowledge.chunker import TextChunker

        # Parse PDF
        parser = PDFParserTool()
        result = parser.run(str(sample_pdf_path))

        # Chunk content
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_text(result["text"])

        # Add to vector store
        vector_store.add_documents(
            documents=chunks,
            metadatas=[{"source": "sample.pdf", "chunk": i} for i in range(len(chunks))],
            ids=[f"pdf_chunk_{i}" for i in range(len(chunks))],
        )

        # Verify
        query_results = vector_store.query("machine learning", n_results=1)
        assert len(query_results["documents"][0]) > 0

    @patch("requests.get")
    def test_web_scraping_to_knowledge_base(self, mock_get, temp_dir, test_env_vars):
        """Test web scraping to knowledge base."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        html_content = b"""
        <html>
            <body>
                <h1>Machine Learning Tutorial</h1>
                <p>This is a comprehensive guide to machine learning.</p>
                <p>We cover supervised and unsupervised learning.</p>
            </body>
        </html>
        """
        mock_response.content = html_content
        mock_response.text = html_content.decode("utf-8")
        mock_get.return_value = mock_response

        # Scrape and process
        from lecture_forge.tools.web_scraper import WebScraperTool
        from lecture_forge.knowledge.chunker import TextChunker

        scraper = WebScraperTool()
        result = scraper.run("https://example.com/ml-tutorial")

        assert result["success"] is True
        assert "machine learning" in result["text"].lower()

        # Chunk and store
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_text(result["text"])

        vector_store = VectorStore(collection_name="web_test")

        vector_store.add_documents(
            documents=chunks,
            metadatas=[{"source": "https://example.com/ml-tutorial", "chunk": i} for i in range(len(chunks))],
            ids=[f"web_chunk_{i}" for i in range(len(chunks))],
        )

        # Verify
        query_results = vector_store.query("machine learning", n_results=1)
        assert len(query_results["documents"][0]) > 0


@pytest.mark.integration
class TestMultiSourceCollection:
    """Test collecting from multiple sources."""

    def test_combine_multiple_sources(self, temp_dir, sample_text_content):
        """Test combining content from PDF and web sources."""
        vector_store = VectorStore(collection_name="multi_source_test")

        # Simulate PDF content
        pdf_content = "PDF content about supervised learning and neural networks."
        # Simulate web content
        web_content = "Web article about unsupervised learning and clustering."

        from lecture_forge.knowledge.chunker import TextChunker

        chunker = TextChunker(chunk_size=200, chunk_overlap=50)

        # Process PDF
        pdf_chunks = chunker.chunk_text(pdf_content)
        vector_store.add_documents(
            documents=pdf_chunks,
            metadatas=[{"source": "book.pdf", "type": "pdf"} for _ in pdf_chunks],
            ids=[f"pdf_{i}" for i in range(len(pdf_chunks))],
        )

        # Process web
        web_chunks = chunker.chunk_text(web_content)
        vector_store.add_documents(
            documents=web_chunks,
            metadatas=[{"source": "web.com", "type": "web"} for _ in web_chunks],
            ids=[f"web_{i}" for i in range(len(web_chunks))],
        )

        # Query for supervised learning (should find PDF)
        results_supervised = vector_store.query("supervised learning", n_results=1)
        assert "supervised" in results_supervised["documents"][0][0].lower()

        # Query for unsupervised learning (should find web)
        results_unsupervised = vector_store.query("unsupervised learning", n_results=1)
        assert "unsupervised" in results_unsupervised["documents"][0][0].lower()
