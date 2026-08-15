from typing import Any, List, Optional
from pydantic import BaseModel, Field

class ExtractedAttribute(BaseModel):
    value: Any = Field(description="The extracted value, or null if not found")
    status: str = Field(description="Status of the extraction: 'EXTRACTED', 'UNKNOWN', or 'REQUIRES_REVIEW'")
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="List of evidence IDs that support this attribute. Must reference provided evidence IDs."
    )

class MotorProtectionCircuitBreakerAttributes(BaseModel):
    voltage: ExtractedAttribute
    current: ExtractedAttribute
    frequency: ExtractedAttribute
    dimensions: ExtractedAttribute
    material: ExtractedAttribute
    poles: ExtractedAttribute
    trip_class: ExtractedAttribute
    mounting: ExtractedAttribute
    application: ExtractedAttribute
    standards: ExtractedAttribute
