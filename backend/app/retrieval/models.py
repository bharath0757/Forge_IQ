from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class RetrievedEvidence(BaseModel):
    """
    Data model representing a retrieved piece of evidence chunk.
    Preserves document, page, chunk index, snippet text, and similarity score.
    """
    evidence_id: str = Field(description="Unique ID for this evidence item / chunk")
    document_id: str = Field(description="Parent document unique identifier")
    document_name: str = Field(description="Original document filename or title")
    page_number: Optional[int] = Field(default=None, description="1-indexed page number where chunk occurs")
    chunk_index: int = Field(default=0, description="Index of the chunk in the document")
    text: str = Field(description="Extracted snippet / chunk text")
    similarity_score: float = Field(default=0.0, description="Similarity score (0.0 to 1.0)")
    product_id: Optional[str] = Field(default=None, description="Optional associated product ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional arbitrary metadata")
