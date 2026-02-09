"""
PDF Parser Tool - Extracts text and metadata from PDF files.
"""

from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF

from lecture_forge.utils import logger


class PDFParserTool:
    """Tool for parsing PDF files."""

    name: str = "PDF Parser"
    description: str = "Extracts text, metadata, and structure from PDF files"

    def run(self, pdf_path: str) -> Dict:
        """
        Parse a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Parsed content with text and metadata
        """
        logger.info(f"Parsing PDF: {pdf_path}")

        try:
            # Check if file exists
            path = Path(pdf_path)
            if not path.exists():
                return {
                    "success": False,
                    "text": "",
                    "pages": [],
                    "metadata": {},
                    "error": f"File not found: {pdf_path}",
                }

            # Open PDF
            doc = fitz.open(pdf_path)

            # Extract metadata
            metadata = {
                "total_pages": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "modification_date": doc.metadata.get("modDate", ""),
            }

            # Extract text from all pages
            pages = []
            full_text = []
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()

                pages.append(
                    {
                        "page_number": page_num + 1,
                        "text": text,
                        "word_count": len(text.split()),
                    }
                )

                full_text.append(text)

            doc.close()

            # Combine all text
            combined_text = "\n\n".join(full_text)

            logger.info(f"Successfully parsed PDF: {total_pages} pages, {len(combined_text)} characters")

            return {
                "success": True,
                "text": combined_text,
                "pages": pages,
                "metadata": metadata,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}")
            return {
                "success": False,
                "text": "",
                "pages": [],
                "metadata": {},
                "error": str(e),
            }
