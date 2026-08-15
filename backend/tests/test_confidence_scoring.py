import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.scoring.engine import ConfidenceScoringEngine
from app.scoring.models import ConfidenceBand, ConfidenceScoreBreakdown
from app.models.product import ProductTwin, ProductAttribute, Evidence, ValidationResult
from app.services.repository import create_product, create_attribute, create_evidence

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_database):
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def scoring_engine():
    return ConfidenceScoringEngine()


def test_confidence_scoring_high_band(scoring_engine):
    """Test high confidence score calculation with strong evidence and official datasheet."""
    evidence = [
        {"document_name": "Siemens_Manufacturer_Datasheet.pdf", "reliability_score": 0.98},
        {"document_name": "Siemens_Catalog.pdf", "reliability_score": 0.95},
    ]

    breakdown = scoring_engine.calculate_attribute_confidence(
        attribute_name="voltage",
        attribute_value="400 V",
        status="VERIFIED",
        evidence_list=evidence,
        agreeing_sources_count=2,
        validation_results=[],
        has_open_conflict=False,
    )

    assert breakdown.confidence_score >= 90.0
    assert breakdown.confidence_band == ConfidenceBand.HIGH
    assert breakdown.source_reliability == 1.00
    assert breakdown.evidence_strength >= 0.95
    assert breakdown.agreement_score >= 1.00
    assert breakdown.validation_factor == 1.00
    assert breakdown.conflict_factor == 1.00
    assert breakdown.is_blocked_by_conflict is False
    assert "Score:" in breakdown.explanation


def test_confidence_scoring_conflict_penalty_and_blocking(scoring_engine):
    """Test that open conflicts impose a 50% penalty and block automatic approval."""
    evidence = [
        {"document_name": "Datasheet.pdf", "reliability_score": 0.95}
    ]

    breakdown = scoring_engine.calculate_attribute_confidence(
        attribute_name="current",
        attribute_value="10 A",
        status="CONFLICT",
        evidence_list=evidence,
        agreeing_sources_count=1,
        validation_results=[],
        has_open_conflict=True,  # Disagreement across sources
    )

    # Conflict factor penalty applied
    assert breakdown.conflict_factor == 0.50
    assert breakdown.confidence_score < 70.0  # Dropped significantly due to conflict
    assert breakdown.confidence_band == ConfidenceBand.LOW
    assert breakdown.is_blocked_by_conflict is True  # Blocks auto approval!
    assert "BLOCKED" in breakdown.explanation


def test_confidence_scoring_validation_failure_penalty(scoring_engine):
    """Test that critical validation failure severely drops score and blocks approval."""
    critical_val = [
        {"rule": "ImpossibleValueCheck", "passed": False, "severity": "CRITICAL"}
    ]

    breakdown = scoring_engine.calculate_attribute_confidence(
        attribute_name="frequency",
        attribute_value="5000 Hz",
        status="FAILED",
        evidence_list=[{"document_name": "doc.pdf", "reliability_score": 0.9}],
        agreeing_sources_count=1,
        validation_results=critical_val,
    )

    assert breakdown.validation_factor == 0.10
    assert breakdown.confidence_score <= 10.0
    assert breakdown.confidence_band == ConfidenceBand.LOW
    assert breakdown.is_blocked_by_conflict is True


def test_confidence_scoring_unknown_attribute(scoring_engine):
    """Test that missing / UNKNOWN attribute yields 0 confidence."""
    breakdown = scoring_engine.calculate_attribute_confidence(
        attribute_name="material",
        attribute_value=None,
        status="UNKNOWN",
        evidence_list=[],
    )

    assert breakdown.confidence_score == 0.0
    assert breakdown.confidence_band == ConfidenceBand.LOW
    assert breakdown.source_reliability == 0.0
    assert breakdown.evidence_strength == 0.0


def test_product_confidence_summary(scoring_engine):
    """Test product-wide confidence aggregation."""
    b1 = ConfidenceScoreBreakdown(
        attribute_name="voltage",
        confidence_score=95.0,
        confidence_band=ConfidenceBand.HIGH,
        source_reliability=1.0,
        evidence_strength=0.95,
        agreement_score=1.0,
        extraction_quality=1.0,
        validation_factor=1.0,
        conflict_factor=1.0,
        is_blocked_by_conflict=False,
        explanation="High confidence voltage",
    )
    b2 = ConfidenceScoreBreakdown(
        attribute_name="current",
        confidence_score=85.0,
        confidence_band=ConfidenceBand.MEDIUM,
        source_reliability=0.9,
        evidence_strength=0.9,
        agreement_score=1.0,
        extraction_quality=1.0,
        validation_factor=1.0,
        conflict_factor=1.0,
        is_blocked_by_conflict=False,
        explanation="Medium confidence current",
    )

    summary = scoring_engine.calculate_product_confidence("prod_1", [b1, b2])

    assert summary.product_id == "prod_1"
    assert summary.overall_confidence_score == 90.0
    assert summary.high_confidence_attributes == 1
    assert summary.medium_confidence_attributes == 1
    assert summary.has_blocking_conflicts is False


def test_api_confidence_endpoint(db_session):
    """Test GET /api/products/{id}/confidence endpoint."""
    prod = create_product(db_session, {
        "id": "prod_conf_api",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 90.0,
        "status": "DRAFT",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_v_api",
        "name": "voltage",
        "value": "400 V",
        "confidence": 0.95,
        "status": "VERIFIED",
    })

    ev = create_evidence(db_session, attr.id, {
        "id": "ev_v_api",
        "source_name": "Siemens_Datasheet.pdf",
        "document_name": "Siemens_Datasheet.pdf",
        "source_type": "PDF",
        "snippet": "Rated voltage: 400 V AC",
        "extracted_text": "Rated voltage: 400 V AC",
        "reliability_score": 0.96,
    })

    resp = client.get(f"/api/products/{prod.id}/confidence")
    assert resp.status_code == 200
    data = resp.json()

    assert data["product_id"] == prod.id
    assert data["overall_confidence_score"] > 80.0
    assert len(data["attributes"]) == 1
    v_breakdown = data["attributes"][0]
    assert v_breakdown["attribute_name"] == "voltage"
    assert v_breakdown["source_reliability"] == 1.00
    assert v_breakdown["confidence_band"] == "HIGH"
    assert "Score:" in v_breakdown["explanation"]
