"""
Document ingestion pipeline.

Orchestrates: receive file → process → store document + chunks to DB.
"""

import uuid
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentChunk
from app.ingestion.processor import DocumentProcessor, ExtractionResult
from app.ingestion.pdf_processor import PDFProcessor
from typing import Dict, Any, List, Optional

# Registry of available processors
_processors: List[DocumentProcessor] = [
    PDFProcessor(),
]


def get_processor(filename: str) -> Optional[DocumentProcessor]:
    """Find a processor that can handle the given file."""
    for proc in _processors:
        if proc.can_handle(filename):
            return proc
    return None


def ingest_document(
    db: Session,
    file_bytes: bytes,
    filename: str,
    file_size: int,
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full ingestion pipeline:
    1. Assign a document ID
    2. Run the appropriate processor
    3. Store the Document record
    4. Store all DocumentChunk records
    5. Return a summary
    """
    document_id = f"doc_{uuid.uuid4().hex[:12]}"

    # Find processor
    processor = get_processor(filename)
    if processor is None:
        # Store a failed document record
        doc = Document(
            id=document_id,
            filename=filename,
            source_type="UNKNOWN",
            file_size=file_size,
            page_count=0,
            status="FAILED",
            error_message=f"No processor available for file: {filename}",
            product_id=product_id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return _doc_response(doc, extracted_text_count=0)

    # Process
    result: ExtractionResult = processor.process(file_bytes, filename, document_id)

    # Store Document record
    doc = Document(
        id=document_id,
        filename=filename,
        source_type=result.source_type,
        file_size=file_size,
        page_count=result.page_count,
        status=result.status,
        error_message=result.error_message,
        product_id=product_id,
    )
    db.add(doc)

    # Store chunks and index for retrieval
    indexed_chunks = []
    for chunk in result.chunks:
        chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
        db_chunk = DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            document_name=filename,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            source_type=chunk.source_type,
            char_count=len(chunk.text),
        )
        db.add(db_chunk)
        indexed_chunks.append(db_chunk)

    db.commit()
    db.refresh(doc)

    # Index in Evidence Retriever for vector search
    try:
        from app.retrieval.retriever import get_evidence_retriever
        retriever = get_evidence_retriever()
        retriever.index_document(
            document_id=document_id,
            document_name=filename,
            chunks=indexed_chunks,
            product_id=product_id
        )
    except Exception as e:
        # Logging error without failing the ingestion transaction
        import logging
        logging.getLogger(__name__).warning(f"Failed to index document in vector store: {e}")

    return _doc_response(doc, extracted_text_count=result.extracted_text_count)


def _doc_response(doc: Document, extracted_text_count: int) -> Dict[str, Any]:
    """Build a consistent API response dict from a Document."""
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "page_count": doc.page_count,
        "extracted_text_count": extracted_text_count,
        "status": doc.status,
        "error_message": doc.error_message,
    }
