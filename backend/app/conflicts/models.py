from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.product import SeverityLevel


class ConflictStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ConflictResolutionAction(str, Enum):
    APPROVE_VALUE = "APPROVE_VALUE"
    OVERRIDE = "OVERRIDE"
    DISMISS = "DISMISS"
    MERGE = "MERGE"


class ConflictResolutionRequest(BaseModel):
    """Payload to resolve or dismiss a product attribute conflict."""
    selected_value: Optional[Any] = Field(default=None, description="The canonical value chosen by reviewer")
    reason: str = Field(description="Audit justification or rationale for the decision")
    reviewer_action: ConflictResolutionAction = Field(default=ConflictResolutionAction.APPROVE_VALUE)


class ConflictDetail(BaseModel):
    """Structured representation of a detected conflict across sources."""
    id: str
    product_id: Optional[str] = None
    attribute: str
    values: List[Any] = Field(description="Distinct raw values extracted from different sources")
    sources: List[str] = Field(description="Names of documents / sources with divergent claims")
    severity: SeverityLevel = SeverityLevel.HIGH
    status: ConflictStatus = ConflictStatus.OPEN
    evidence_ids: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
