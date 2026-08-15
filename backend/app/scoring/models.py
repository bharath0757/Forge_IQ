from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"      # 90-100%
    MEDIUM = "MEDIUM"  # 70-89%
    LOW = "LOW"        # 0-69%


class ConfidenceScoreBreakdown(BaseModel):
    """
    Deterministic confidence score breakdown providing full explainability for each attribute.
    """
    attribute_name: str
    confidence_score: float = Field(ge=0.0, le=100.0, description="Final normalized confidence percentage (0-100)")
    confidence_band: ConfidenceBand = Field(description="Confidence band: HIGH (90-100), MEDIUM (70-89), LOW (0-69)")
    
    # Individual Scoring Factors (each 0.0 to 1.0 or multiplier)
    source_reliability: float = Field(ge=0.0, le=1.0, description="Reliability weight of the source document type")
    evidence_strength: float = Field(ge=0.0, le=1.0, description="Quality and similarity score of supporting evidence snippets")
    agreement_score: float = Field(ge=0.0, le=1.5, description="Multiplier reflecting number of independent agreeing sources")
    extraction_quality: float = Field(ge=0.0, le=1.0, description="Clarity, schema adherence, and unambiguous normalization")
    validation_factor: float = Field(ge=0.0, le=1.0, description="Deterministic rule compliance factor")
    conflict_factor: float = Field(ge=0.0, le=1.0, description="Penalty multiplier if open conflicts exist")

    is_blocked_by_conflict: bool = Field(default=False, description="True if an active conflict prevents automatic approval")
    explanation: str = Field(description="Human-readable summary of how the score was calculated")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supplementary metrics")


class ProductConfidenceSummary(BaseModel):
    """
    Aggregated confidence metrics for an entire Product Twin entity.
    """
    product_id: str
    overall_confidence_score: float = Field(ge=0.0, le=100.0)
    overall_confidence_band: ConfidenceBand
    high_confidence_attributes: int
    medium_confidence_attributes: int
    low_confidence_attributes: int
    has_blocking_conflicts: bool
    attributes: List[ConfidenceScoreBreakdown] = Field(default_factory=list)
