import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.product import (
    Product, ProductAttribute, Evidence, AttributeStatus, 
    EntityStatus, SourceType, Source, ValidationResult,
    Conflict, ReviewDecision, ProcessingJob, SeverityLevel,
    ReviewAction
)

def test_evidence_validation():
    # Valid evidence
    ev = Evidence(
        id="ev_123",
        source_name="Siemens Catalog 2023",
        source_type=SourceType.PDF,
        snippet="Operating voltage: 690V",
        extracted_text="690V",
        reliability_score=0.95
    )
    assert ev.reliability_score == 0.95
    assert ev.page_number is None

    # Invalid reliability score
    with pytest.raises(ValidationError):
        Evidence(
            id="ev_124",
            source_name="Unknown",
            source_type=SourceType.WEBSITE,
            snippet="Data",
            extracted_text="Data",
            reliability_score=1.5 # Should fail (le=1.0)
        )

def test_product_attribute_validation():
    # Valid attribute
    attr = ProductAttribute(
        name="operating_voltage",
        value=690,
        unit="V",
        confidence=0.8,
        status=AttributeStatus.VERIFIED,
    )
    assert attr.name == "operating_voltage"
    assert attr.evidence_ids == []

    # Invalid confidence
    with pytest.raises(ValidationError):
        ProductAttribute(
            name="faulty",
            value="N/A",
            confidence=-0.1, # Should fail (ge=0.0)
            status=AttributeStatus.UNKNOWN
        )

def test_product_validation():
    now = datetime.now(timezone.utc)
    
    attr = ProductAttribute(
        name="current_rating",
        value=10,
        unit="A",
        confidence=0.9,
        status=AttributeStatus.VERIFIED
    )
    
    # Valid product
    prod = Product(
        id="prod_123",
        part_number="3RV2011-1JA10",
        brand="Siemens",
        description="Circuit Breaker",
        category="Electrical Components",
        attributes=[attr],
        overall_quality_score=95.5,
        status=EntityStatus.DRAFT,
        evidence_count=1,
        created_at=now,
        updated_at=now
    )
    
    assert prod.part_number == "3RV2011-1JA10"
    assert len(prod.attributes) == 1

    # Invalid overall quality score
    with pytest.raises(ValidationError):
        Product(
            id="prod_124",
            part_number="XYZ",
            brand="Brand",
            description="Desc",
            category="Cat",
            overall_quality_score=105.0, # Should fail (le=100.0)
            status=EntityStatus.DRAFT,
            evidence_count=0,
            created_at=now,
            updated_at=now
        )

def test_source_validation():
    source = Source(
        id="src_1",
        name="Source A",
        type=SourceType.WEBSITE,
        url="https://example.com"
    )
    assert source.id == "src_1"
    assert source.type == SourceType.WEBSITE
    assert source.document_name is None

def test_validation_result():
    vr = ValidationResult(
        rule="rule_1",
        passed=True,
        message="All good",
        severity=SeverityLevel.LOW
    )
    assert vr.passed is True
    assert vr.severity == SeverityLevel.LOW

def test_conflict_validation():
    conflict = Conflict(
        id="conf_1",
        attribute="weight",
        values=[10, 20],
        sources=["src_1", "src_2"],
        severity=SeverityLevel.HIGH,
        status="OPEN"
    )
    assert conflict.attribute == "weight"
    assert len(conflict.values) == 2

def test_review_decision_validation():
    now = datetime.now(timezone.utc)
    decision = ReviewDecision(
        id="dec_1",
        attribute="weight",
        previous_value=10,
        selected_value=20,
        reviewer_action=ReviewAction.MODIFY,
        reason="Correct value",
        timestamp=now
    )
    assert decision.reviewer_action == ReviewAction.MODIFY

def test_processing_job_validation():
    now = datetime.now(timezone.utc)
    job = ProcessingJob(
        id="job_1",
        product_id="prod_1",
        status="RUNNING",
        progress=50,
        started_at=now
    )
    assert job.progress == 50
    assert job.status == "RUNNING"

    with pytest.raises(ValidationError):
        ProcessingJob(
            id="job_2",
            product_id="prod_1",
            status="RUNNING",
            progress=150, # Should fail (le=100)
            started_at=now
        )
