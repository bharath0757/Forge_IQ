# cspell:ignore fitz
"""
Document processor using PyMuPDF (fitz).

Handles:
- Normal text PDFs
- PDFs with tables (extracts as structured text)
- Scanned PDFs (extracts any available text layer)
- Empty or corrupted PDFs (returns graceful error)
"""

import fitz  # PyMuPDF
from typing import List
from app.ingestion.processor import DocumentProcessor, ExtractionResult, ExtractedChunk

# Maximum characters per chunk before splitting
CHUNK_MAX_CHARS = 2000
# Minimum characters for a chunk to be worth keeping
CHUNK_MIN_CHARS = 10


class PDFProcessor(DocumentProcessor):
    """Extracts text and tables from PDF documents."""

    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    def process(self, file_bytes: bytes, filename: str, document_id: str) -> ExtractionResult:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            return ExtractionResult(
                document_id=document_id,
                filename=filename,
                source_type="PDF",
                page_count=0,
                status="FAILED",
                error_message=f"Cannot open PDF: {str(e)}",
            )

        if doc.page_count == 0:
            doc.close()
            return ExtractionResult(
                document_id=document_id,
                filename=filename,
                source_type="PDF",
                page_count=0,
                status="FAILED",
                error_message="PDF has no pages",
            )

        all_chunks: List[ExtractedChunk] = []
        chunk_index = 0

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            page_number = page_num + 1  # 1-indexed

            # ── Extract tables first ─────────────────────────────
            table_texts = self._extract_tables(page)

            # ── Extract regular text ─────────────────────────────
            page_text = page.get_text("text").strip()

            # Combine: tables get their own chunks, then remaining text
            if table_texts:
                for table_text in table_texts:
                    if len(table_text.strip()) >= CHUNK_MIN_CHARS:
                        for sub_chunk in self._split_text(table_text.strip(), CHUNK_MAX_CHARS):
                            all_chunks.append(ExtractedChunk(
                                page_number=page_number,
                                chunk_index=chunk_index,
                                text=sub_chunk,
                                source_type="PDF",
                            ))
                            chunk_index += 1

            if page_text and len(page_text) >= CHUNK_MIN_CHARS:
                for sub_chunk in self._split_text(page_text, CHUNK_MAX_CHARS):
                    all_chunks.append(ExtractedChunk(
                        page_number=page_number,
                        chunk_index=chunk_index,
                        text=sub_chunk,
                        source_type="PDF",
                    ))
                    chunk_index += 1

        page_count = doc.page_count
        doc.close()

        # If no text was extracted at all, mark as completed but note it
        status = "COMPLETED"
        error_msg = None
        if len(all_chunks) == 0:
            error_msg = "No extractable text found (possibly a scanned PDF without OCR)"

        return ExtractionResult(
            document_id=document_id,
            filename=filename,
            source_type="PDF",
            page_count=page_count,
            chunks=all_chunks,
            status=status,
            error_message=error_msg,
        )

    def _extract_tables(self, page: fitz.Page) -> List[str]:
        """Extract tables from a page using PyMuPDF's built-in table finder."""
        table_texts = []
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for table in tabs.tables:
                    rows = table.extract()
                    if not rows:
                        continue
                    # Convert table rows to readable text
                    lines = []
                    for row in rows:
                        cells = [str(cell).strip() if cell else "" for cell in row]
                        line = " | ".join(cells)
                        if line.replace("|", "").strip():
                            lines.append(line)
                    if lines:
                        table_texts.append("\n".join(lines))
        except Exception:
            # Table extraction is best-effort; don't fail the whole page
            pass
        return table_texts

    @staticmethod
    def _split_text(text: str, max_chars: int) -> List[str]:
        """Split text into chunks respecting paragraph boundaries."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current = ""

        for para in paragraphs:
            # If a single paragraph exceeds max, split by sentences
            if len(para) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Split long paragraph by newlines, then by length
                lines = para.split("\n")
                for line in lines:
                    if len(current) + len(line) + 1 > max_chars and current:
                        chunks.append(current.strip())
                        current = ""
                    current += line + "\n"
                continue

            if len(current) + len(para) + 2 > max_chars and current:
                chunks.append(current.strip())
                current = ""
            current += para + "\n\n"

        if current.strip():
            chunks.append(current.strip())

        return chunks
