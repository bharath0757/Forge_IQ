from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class EntityStatus(str, Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    REVIEWED = "REVIEWED"
    PUBLISHED = "PUBLISHED"

class AttributeStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SourceType(str, Enum):
    PDF = "PDF"
    WEBSITE = "WEBSITE"
    IMAGE = "IMAGE"
    CATALOG = "CATALOG"
    API = "API"

class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"

class Source(BaseModel):
    id: str
    name: str
    type: SourceType
    url: Optional[str] = None
    document_name: Optional[str] = None

class Evidence(BaseModel):
    id: str
    source_name: str
    source_type: SourceType
    source_url: Optional[str] = None
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    snippet: str
    extracted_text: str
    reliability_score: float = Field(ge=0.0, le=1.0)

class ConflictStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ValidationResult(BaseModel):
    rule: str
    passed: bool
    message: str
    severity: SeverityLevel

class Conflict(BaseModel):
    id: str
    attribute: str
    values: List[Any]
    sources: List[str] # List of source IDs or names
    severity: SeverityLevel
    status: ConflictStatus = ConflictStatus.OPEN

class ReviewDecision(BaseModel):
    id: str
    attribute: str
    previous_value: Any
    selected_value: Any
    reviewer_action: ReviewAction
    reason: str
    timestamp: datetime

class ConfidenceScoreBreakdown(BaseModel):
    confidence_score: float
    confidence_band: ConfidenceBand
    source_reliability: float
    evidence_strength: float
    agreement_score: float
    extraction_quality: float
    validation_factor: float
    conflict_factor: float
    is_blocked_by_conflict: bool = False
    explanation: Optional[str] = None

class ProductAttribute(BaseModel):
    name: str
    value: Any
    normalized_value: Any = None
    unit: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: AttributeStatus
    evidence_ids: List[str] = []
    conflict_ids: List[str] = []
    confidence_breakdown: Optional[ConfidenceScoreBreakdown] = None

class Product(BaseModel):
    id: str
    part_number: str
    brand: str
    description: str
    category: str
    attributes: List[ProductAttribute] = []
    overall_quality_score: float = Field(ge=0.0, le=100.0)
    status: EntityStatus
    evidence_count: int
    conflicts: List[Conflict] = []
    created_at: datetime
    updated_at: datetime

class ProcessingJob(BaseModel):
    id: str
    product_id: str
    status: str # "PENDING", "RUNNING", "COMPLETED", "FAILED"
    progress: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
