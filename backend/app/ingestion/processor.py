"""
DocumentProcessor abstraction for ForgeIQ.

Provides a base class that any document processor (PDF, image, etc.)
must implement. This allows swapping or extending extraction backends
without changing the rest of the pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExtractedChunk:
    """A single chunk of text extracted from a document."""
    page_number: Optional[int]
    chunk_index: int
    text: str
    source_type: str  # "PDF", "IMAGE", etc.


@dataclass
class ExtractionResult:
    """Full result of processing a document."""
    document_id: str
    filename: str
    source_type: str
    page_count: int
    chunks: List[ExtractedChunk] = field(default_factory=list)
    status: str = "COMPLETED"  # COMPLETED or FAILED
    error_message: Optional[str] = None

    @property
    def extracted_text_count(self) -> int:
        return len(self.chunks)


class DocumentProcessor(ABC):
    """Abstract base class for document processors."""

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this processor handles."""
        ...

    @abstractmethod
    def process(self, file_bytes: bytes, filename: str, document_id: str) -> ExtractionResult:
        """
        Process a document and return extracted chunks.

        Args:
            file_bytes: Raw file content.
            filename: Original filename.
            document_id: Unique ID assigned to this document.

        Returns:
            ExtractionResult with all extracted chunks and metadata.
        """
        ...

    def can_handle(self, filename: str) -> bool:
        """Check if this processor can handle the given file."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return f".{ext}" in self.supported_extensions()
