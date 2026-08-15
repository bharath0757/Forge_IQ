import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.product import ProductTwin, ProductAttribute, Conflict, ReviewDecision
from app.services.repository import create_product, create_attribute, create_conflict

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


def test_human_review_accept_ai_value(db_session):
    """Test reviewer accepting AI extracted value: updates attribute status and creates audit log."""
    prod = create_product(db_session, {
        "id": "prod_hr_1",
        "part_number": "3RV2011-1JA10",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Switchgear",
        "overall_quality_score": 0.0,
        "status": "REQUIRES_REVIEW",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_hr_v",
        "name": "voltage",
        "value": "400 V",
        "confidence": 0.85,
        "status": "REQUIRES_REVIEW",
    })

    payload = {
        "attribute_name": "voltage",
        "action": "ACCEPT_AI_VALUE",
        "reason": "Verified against primary datasheet page 4",
        "reviewer": "Senior Engineer",
    }

    resp = client.post(f"/api/products/{prod.id}/review", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["selected_value"] == "400 V"

    # Verify attribute updated
    db_session.refresh(attr)
    assert attr.status == "VERIFIED"
    assert attr.confidence == 1.0

    # Verify ReviewDecision created
    decisions = db_session.query(ReviewDecision).filter(ReviewDecision.product_id == prod.id).all()
    assert len(decisions) == 1
    assert decisions[0].attribute == "voltage"
    assert decisions[0].reviewer_action == "ACCEPT_AI_VALUE"
    assert "datasheet" in decisions[0].reason


def test_human_review_select_alternative_and_resolve_conflict(db_session):
    """Test reviewer selecting alternative value, resolving conflict, and recalculating quality score."""
    prod = create_product(db_session, {
        "id": "prod_hr_2",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Switchgear",
        "overall_quality_score": 0.0,
        "status": "REQUIRES_REVIEW",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_hr_c",
        "name": "current",
        "value": "10 A",
        "confidence": 0.50,
        "status": "CONFLICT",
    })

    conflict = create_conflict(db_session, prod.id, {
        "id": "conf_hr_01",
        "attribute": "current",
        "values": ["10 A", "12 A"],
        "severity": "HIGH",
        "status": "OPEN",
    })

    payload = {
        "attribute_name": "current",
        "action": "SELECT_ALTERNATIVE",
        "selected_value": "12 A",
        "reason": "12 A rating confirmed in manufacturer catalog",
    }

    resp = client.post(f"/api/products/{prod.id}/review", json=payload)
    assert resp.status_code == 200

    # Check attribute value updated
    db_session.refresh(attr)
    assert attr.value == "12 A"
    assert attr.status == "VERIFIED"

    # Check conflict marked as RESOLVED
    db_session.refresh(conflict)
    assert conflict.status == "RESOLVED"


def test_human_review_mark_unknown(db_session):
    """Test reviewer marking an unverified/ambiguous attribute as UNKNOWN."""
    prod = create_product(db_session, {
        "id": "prod_hr_3",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Switchgear",
        "overall_quality_score": 50.0,
        "status": "REQUIRES_REVIEW",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_hr_mat",
        "name": "material",
        "value": "Unknown alloy",
        "confidence": 0.30,
        "status": "REQUIRES_REVIEW",
    })

    payload = {
        "attribute_name": "material",
        "action": "MARK_UNKNOWN",
        "reason": "Not specified in documentation",
    }

    resp = client.post(f"/api/products/{prod.id}/review", json=payload)
    assert resp.status_code == 200

    db_session.refresh(attr)
    assert attr.value is None
    assert attr.status == "UNKNOWN"
    assert attr.confidence == 0.0


def test_product_approve_blocked_by_open_critical_conflict(db_session):
    """Test that open high-severity conflict blocks product approval."""
    prod = create_product(db_session, {
        "id": "prod_hr_4",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Switchgear",
        "overall_quality_score": 80.0,
        "status": "REQUIRES_REVIEW",
    })

    create_conflict(db_session, prod.id, {
        "id": "conf_block_01",
        "attribute": "voltage",
        "values": ["230 V", "400 V"],
        "severity": "HIGH",
        "status": "OPEN",
    })

    # Approval should be blocked
    resp = client.post(f"/api/products/{prod.id}/approve")
    assert resp.status_code == 400
    assert "open high-severity conflict" in resp.json()["detail"]


def test_product_export_json_endpoint(db_session):
    """Test GET /api/products/{id}/export returns canonical JSON twin."""
    prod = create_product(db_session, {
        "id": "prod_hr_export",
        "part_number": "3RV2011-1JA10",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 95.0,
        "status": "REVIEWED",
    })

    create_attribute(db_session, prod.id, {
        "id": "attr_exp_v",
        "name": "voltage",
        "value": "400 V",
        "normalized_value": "400 V",
        "unit": "V",
        "confidence": 0.99,
        "status": "VERIFIED",
    })

    resp = client.get(f"/api/products/{prod.id}/export")
    assert resp.status_code == 200
    data = resp.json()

    assert data["forge_iq_version"] == "1.0"
    assert data["product_twin"]["part_number"] == "3RV2011-1JA10"
    assert len(data["product_twin"]["attributes"]) == 1
    assert data["product_twin"]["attributes"][0]["normalized_value"] == "400 V"
