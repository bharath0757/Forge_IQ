from typing import Any, Optional, Dict
from pydantic import BaseModel, Field


class NormalizedAttributeResult(BaseModel):
    """
    Result of normalizing an extracted attribute value.
    Preserves raw_value, canonical normalized_value, and unit.
    """
    raw_value: Any = Field(description="The exact original raw extracted value (preserved verbatim)")
    normalized_value: Any = Field(default=None, description="The canonical normalized representation")
    unit: Optional[str] = Field(default=None, description="The canonical unit of measurement")
    numeric_value: Optional[float] = Field(default=None, description="Parsed numeric value if scalar")
    is_ambiguous: bool = Field(default=False, description="True if value could not be unambiguously converted")
    requires_review: bool = Field(default=False, description="True if manual reviewer inspection is recommended")
    message: Optional[str] = Field(default=None, description="Explanation or normalization notes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Detailed parsed components")
    
    # Pipeline integration fields
    label: Optional[str] = Field(default=None, description="The canonical label/name of the attribute")
    confidence: float = Field(default=0.0, description="Confidence score of the attribute")
    validation_status: Optional[str] = Field(default=None, description="Status from validation engine")
    conflict_status: Optional[str] = Field(default=None, description="Status from conflict detector")
    review_status: Optional[str] = Field(default=None, description="Human review status")
    source_ids: list[str] = Field(default_factory=list, description="IDs of sources supporting this attribute")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of evidence chunks supporting this attribute")
