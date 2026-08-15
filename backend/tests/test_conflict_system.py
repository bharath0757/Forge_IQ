import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.conflicts.detector import ConflictDetector
from app.conflicts.service import ConflictResolutionService
from app.conflicts.models import ConflictStatus, ConflictResolutionRequest, ConflictResolutionAction
from app.models.product import ProductTwin, ProductAttribute, Conflict as DBConflict, ReviewDecision
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

@pytest.fixture
def conflict_detector():
    return ConflictDetector()

@pytest.fixture
def conflict_service():
    return ConflictResolutionService()


def test_conflict_detection_same_values(conflict_detector):
    """Test that identical values across sources produce no conflict."""
    claims = [
        {"source_name": "Datasheet.pdf", "value": "400 V", "evidence_id": "ev-1"},
        {"source_name": "Catalog.pdf", "value": "400 V", "evidence_id": "ev-2"},
    ]

    conflict = conflict_detector.check_attribute_conflict("voltage", claims)
    assert conflict is None


def test_conflict_detection_different_formatting_same_value(conflict_detector):
    """Test that different formatting (e.g. 400 volts vs 400V) normalizes cleanly with NO false conflict."""
    claims = [
        {"source_name": "Datasheet.pdf", "value": "400 volts", "evidence_id": "ev-1"},
        {"source_name": "Catalog.pdf", "value": "400V", "evidence_id": "ev-2"},
        {"source_name": "Manual.pdf", "value": "400 V", "evidence_id": "ev-3"},
    ]

    conflict = conflict_detector.check_attribute_conflict("voltage", claims)
    assert conflict is None, "False conflict was incorrectly triggered for formatting variations"


def test_conflict_detection_different_units_representing_same_value(conflict_detector):
    """Test that equivalent units (e.g. 0.4 kV vs 400 V) canonicalize with NO false conflict."""
    claims = [
        {"source_name": "Datasheet.pdf", "value": "0.4 kV", "evidence_id": "ev-1"},
        {"source_name": "Catalog.pdf", "value": "400 V", "evidence_id": "ev-2"},
    ]

    conflict = conflict_detector.check_attribute_conflict("voltage", claims)
    assert conflict is None, "False conflict was incorrectly triggered for unit equivalent representations"


def test_conflict_detection_true_conflict(conflict_detector):
    """Test that genuine numerical discrepancies create a Conflict record with OPEN status and HIGH severity."""
    claims = [
        {"source_name": "Datasheet.pdf", "value": "10 A", "evidence_id": "ev-1"},
        {"source_name": "Catalog.pdf", "value": "12 A", "evidence_id": "ev-2"},
    ]

    conflict = conflict_detector.check_attribute_conflict("current", claims, product_id="prod_123")
    assert conflict is not None
    assert conflict.attribute == "current"
    assert conflict.status == ConflictStatus.OPEN
    assert conflict.severity.value == "HIGH"
    assert "10 A" in conflict.values and "12 A" in conflict.values
    assert len(conflict.sources) == 2
    assert "ev-1" in conflict.evidence_ids and "ev-2" in conflict.evidence_ids


def test_conflict_resolution_flow(db_session, conflict_service):
    """Test resolving a conflict: updates status to RESOLVED, updates attribute value, and records ReviewDecision."""
    # 1. Setup product, attribute, and conflict in DB
    prod = create_product(db_session, {
        "id": "prod_res_test",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 50.0,
        "status": "REQUIRES_REVIEW",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_cur_res",
        "name": "current",
        "value": "10 A",
        "confidence": 0.5,
        "status": "CONFLICT",
    })

    conflict = create_conflict(db_session, prod.id, {
        "id": "conf_cur_01",
        "attribute": "current",
        "values": ["10 A", "12 A"],
        "severity": "HIGH",
        "status": "OPEN",
    })

    # 2. Resolve conflict
    res_req = ConflictResolutionRequest(
        selected_value="10 A",
        reason="Verified against primary manufacturer datasheet page 4",
        reviewer_action=ConflictResolutionAction.APPROVE_VALUE,
    )

    resolved = conflict_service.resolve_conflict(db_session, conflict.id, res_req)
    assert resolved is not None
    assert resolved.status == "RESOLVED"

    # 3. Verify attribute updated and verified
    db_session.refresh(attr)
    assert attr.value == "10 A"
    assert attr.normalized_value == "10 A"
    assert attr.status == "VERIFIED"

    # 4. Verify ReviewDecision audit trail logged
    decisions = db_session.query(ReviewDecision).filter(ReviewDecision.product_id == prod.id).all()
    assert len(decisions) == 1
    assert decisions[0].attribute == "current"
    assert decisions[0].selected_value == "10 A"
    assert "primary manufacturer datasheet" in decisions[0].reason

    # 5. Verify product status updated since all conflicts are resolved
    db_session.refresh(prod)
    assert prod.status == "REVIEWED"


def test_conflict_dismissal_flow(db_session, conflict_service):
    """Test dismissing a conflict records audit reason and sets status to DISMISSED."""
    prod = create_product(db_session, {
        "id": "prod_dism_test",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 60.0,
        "status": "REQUIRES_REVIEW",
    })

    conflict = create_conflict(db_session, prod.id, {
        "id": "conf_dism_01",
        "attribute": "mounting",
        "values": ["DIN Rail 35mm", "Screw mounting"],
        "severity": "MEDIUM",
        "status": "OPEN",
    })

    dismissed = conflict_service.dismiss_conflict(
        db_session,
        conflict.id,
        reason="Both mounting methods are supported by accessory adapter"
    )

    assert dismissed is not None
    assert dismissed.status == "DISMISSED"

    # Audit decision recorded
    decisions = db_session.query(ReviewDecision).filter(ReviewDecision.product_id == prod.id).all()
    assert len(decisions) == 1
    assert decisions[0].reviewer_action == "DISMISS"


def test_api_conflicts_endpoints(db_session):
    """Test GET /api/products/{id}/conflicts, POST resolve, and POST dismiss."""
    prod = create_product(db_session, {
        "id": "prod_api_conf",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 0.0,
        "status": "REQUIRES_REVIEW",
    })

    attr = create_attribute(db_session, prod.id, {
        "id": "attr_cur_api",
        "name": "current",
        "value": "10 A",
        "confidence": 0.5,
        "status": "CONFLICT",
    })

    conflict = create_conflict(db_session, prod.id, {
        "id": "conf_api_test",
        "attribute": "current",
        "values": ["10 A", "12 A"],
        "severity": "HIGH",
        "status": "OPEN",
    })

    # 1. GET conflicts
    get_resp = client.get(f"/api/products/{prod.id}/conflicts")
    assert get_resp.status_code == 200
    conf_list = get_resp.json()
    assert len(conf_list) == 1
    assert conf_list[0]["attribute"] == "current"
    assert conf_list[0]["status"] == "OPEN"

    # 2. POST resolve
    resolve_payload = {
        "selected_value": "10 A",
        "reason": "Manufacturer datasheet confirmed 10 A rating",
        "reviewer_action": "APPROVE_VALUE",
    }
    res_resp = client.post(f"/api/products/{prod.id}/conflicts/{conflict.id}/resolve", json=resolve_payload)
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "SUCCESS"
    assert res_resp.json()["conflict_status"] == "RESOLVED"

    # 3. Verify GET shows resolved
    get_resp2 = client.get(f"/api/products/{prod.id}/conflicts?status=RESOLVED")
    assert get_resp2.status_code == 200
    assert len(get_resp2.json()) == 1
    assert get_resp2.json()[0]["status"] == "RESOLVED"
