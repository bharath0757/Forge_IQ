import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.validation.engine import ValidationEngine
from app.validation.rules import (
    RequiredAttributeRule,
    NumericFormatRule,
    UnitConsistencyRule,
    ImpossibleValueRule,
    DuplicateAttributeRule,
)
from app.validation.cross_source import CrossSourceValidator
from app.validation.models import ValidationStatus, ValidationSeverity
from app.models.product import ProductTwin, ProductAttribute, Evidence, ValidationResult as DBValidationResult
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
def validation_engine():
    return ValidationEngine()


def test_valid_attribute_passes_all_rules(validation_engine):
    """Test that standard valid attributes pass all deterministic checks."""
    attributes = {
        "voltage": {"value": "400 V", "normalized_value": "400 V", "unit": "V", "status": "VERIFIED"},
        "current": {"value": "10 A", "normalized_value": "10 A", "unit": "A", "status": "VERIFIED"},
        "frequency": {"value": "50/60 Hz", "normalized_value": "50/60 Hz", "unit": "Hz", "status": "VERIFIED"},
        "poles": {"value": 3, "normalized_value": 3, "unit": "poles", "status": "VERIFIED"},
    }

    report = validation_engine.validate_product(
        product_id="prod_valid",
        attributes=attributes,
    )

    assert report.passed is True
    assert report.status == "VERIFIED"
    assert report.failed_count == 0
    assert report.conflict_count == 0
    assert all(r.passed for r in report.results)


def test_missing_required_attribute(validation_engine):
    """Test that missing required attribute triggers a HIGH severity failure."""
    attributes = {
        "voltage": {"value": "400 V", "normalized_value": "400 V", "unit": "V", "status": "VERIFIED"},
        "current": {"value": None, "status": "UNKNOWN"},  # Missing required current
    }

    report = validation_engine.validate_product(
        product_id="prod_missing",
        attributes=attributes,
    )

    assert report.passed is False
    assert report.status == "REQUIRES_REVIEW"
    failed_results = [r for r in report.results if not r.passed]
    assert any(r.rule == "RequiredAttributesCheck" and r.attribute_name == "current" for r in failed_results)
    curr_res = next(r for r in failed_results if r.attribute_name == "current")
    assert curr_res.severity == ValidationSeverity.HIGH


def test_invalid_unit_consistency(validation_engine):
    """Test that incompatible units (e.g. voltage in kg) trigger CRITICAL failure."""
    attributes = {
        "voltage": {"value": "400 kg", "unit": "kg", "status": "EXTRACTED"},
        "current": {"value": "10 A", "unit": "A", "status": "VERIFIED"},
    }

    report = validation_engine.validate_product(
        product_id="prod_bad_unit",
        attributes=attributes,
    )

    assert report.passed is False
    assert report.status == "REQUIRES_REVIEW"
    unit_res = next(r for r in report.results if r.rule == "UnitConsistencyCheck" and r.attribute_name == "voltage")
    assert unit_res.passed is False
    assert unit_res.severity == ValidationSeverity.CRITICAL
    assert "Unit mismatch" in unit_res.message


def test_impossible_value_detection(validation_engine):
    """Test that physically impossible or out-of-range specs trigger CRITICAL failure."""
    attributes = {
        "voltage": {"value": "-120 V", "unit": "V", "status": "EXTRACTED"},
        "current": {"value": "10 A", "unit": "A", "status": "VERIFIED"},
        "frequency": {"value": "5000 Hz", "unit": "Hz", "status": "EXTRACTED"},
    }

    report = validation_engine.validate_product(
        product_id="prod_impossible",
        attributes=attributes,
    )

    assert report.passed is False
    failed_imp = [r for r in report.results if r.rule == "ImpossibleValueCheck" and not r.passed]
    assert len(failed_imp) >= 1
    assert any(r.attribute_name == "frequency" for r in failed_imp)


def test_cross_source_conflicting_sources():
    """Test that conflicting values across sources produce CONFLICT status with HIGH severity."""
    validator = CrossSourceValidator()

    claims = [
        {"source_name": "Datasheet.pdf", "value": "10 A", "evidence_id": "ev-1"},
        {"source_name": "Catalog.pdf", "value": "12 A", "evidence_id": "ev-2"},
    ]

    result = validator.compare_sources("current", claims)

    assert result.is_conflict is True
    assert result.status == ValidationStatus.CONFLICT
    assert result.severity == ValidationSeverity.HIGH
    assert "10 A" in result.conflicting_values and "12 A" in result.conflicting_values
    assert "Conflicting values detected" in result.message
    assert "ev-1" in result.evidence_ids and "ev-2" in result.evidence_ids


def test_cross_source_matching_sources():
    """Test that matching values across sources with different formatting pass consistency check."""
    validator = CrossSourceValidator()

    # Formats differ (400 volts vs 400V vs 400 V AC), but canonical value matches
    claims = [
        {"source_name": "Datasheet.pdf", "value": "400 volts", "evidence_id": "ev-1"},
        {"source_name": "Manual.pdf", "value": "400V", "evidence_id": "ev-2"},
    ]

    result = validator.compare_sources("voltage", claims)

    assert result.is_conflict is False
    assert result.status == ValidationStatus.PASSED
    assert result.severity == ValidationSeverity.LOW
    assert "consistently verified" in result.message


def test_validation_never_silently_modifies_attributes(validation_engine):
    """Ensure validation is strictly non-destructive and produces results without altering attribute values."""
    original_val = "400 volts"
    attributes = {
        "voltage": {"name": "voltage", "value": original_val, "unit": "V", "status": "VERIFIED"},
        "current": {"name": "current", "value": "10 A", "unit": "A", "status": "VERIFIED"},
    }

    report = validation_engine.validate_product(
        product_id="prod_non_destructive",
        attributes=attributes,
    )

    # Attribute dict was not mutated
    assert attributes["voltage"]["value"] == original_val
    assert isinstance(report.results, list)
    assert len(report.results) > 0


def test_api_normalize_and_validate_endpoints(db_session):
    """Test POST /api/products/{id}/normalize and POST /api/products/{id}/validate endpoints."""
    # 1. Create a product with attributes in DB
    prod = create_product(db_session, {
        "id": "prod_val_api",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Sirius Breaker",
        "category": "Motor Protection Circuit Breaker",
        "overall_quality_score": 0.0,
        "status": "DRAFT",
    })

    attr_v = create_attribute(db_session, prod.id, {
        "id": "attr_v1",
        "name": "voltage",
        "value": "400 volts",
        "confidence": 0.9,
        "status": "EXTRACTED",
    })
    attr_c = create_attribute(db_session, prod.id, {
        "id": "attr_c1",
        "name": "current",
        "value": "10 amps",
        "confidence": 0.9,
        "status": "EXTRACTED",
    })

    # 2. Test POST /api/products/{id}/normalize
    norm_resp = client.post(f"/api/products/{prod.id}/normalize")
    assert norm_resp.status_code == 200
    norm_data = norm_resp.json()
    assert norm_data["normalized_attributes_count"] == 2
    v_norm = next(a for a in norm_data["attributes"] if a["name"] == "voltage")
    assert v_norm["raw_value"] == "400 volts"
    assert v_norm["normalized_value"] == "400 V"
    assert v_norm["unit"] == "V"

    # 3. Test POST /api/products/{id}/validate
    val_resp = client.post(f"/api/products/{prod.id}/validate")
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["passed"] is True
    assert val_data["status"] == "VERIFIED"
    assert val_data["passed_count"] > 0
    assert val_data["failed_count"] == 0

    # 4. Verify results via GET /api/products/{id}
    get_resp = client.get(f"/api/products/{prod.id}")
    assert get_resp.status_code == 200
    prod_data = get_resp.json()
    assert len(prod_data["validation_results"]) > 0
    assert any(vr["rule"] == "RequiredAttributesCheck" and vr["passed"] for vr in prod_data["validation_results"])
