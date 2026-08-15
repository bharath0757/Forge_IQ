import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.services.repository import create_product, create_attribute

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


def test_catalog_summary_endpoint(db_session):
    """Test GET /api/products/summary returns correct KPI calculations."""
    # 1. Initially empty
    resp = client.get("/api/products/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 0
    assert data["verified_count"] == 0
    assert data["average_quality_score"] == 0.0

    # 2. Add products
    create_product(db_session, {
        "id": "prod_1",
        "part_number": "3RV2011-1JA10",
        "brand": "Siemens",
        "description": "Breaker 1",
        "category": "Motor Protection",
        "overall_quality_score": 90.0,
        "status": "PUBLISHED",
    })
    create_product(db_session, {
        "id": "prod_2",
        "part_number": "3RV2021-4BA10",
        "brand": "Siemens",
        "description": "Breaker 2",
        "category": "Motor Protection",
        "overall_quality_score": 60.0,
        "status": "REQUIRES_REVIEW",
    })

    resp = client.get("/api/products/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 2
    assert data["verified_count"] == 1
    assert data["needs_review_count"] == 1
    assert data["average_quality_score"] == 75.0


def test_catalog_search_and_filters(db_session):
    """Test GET /api/products with search query and status filters."""
    create_product(db_session, {
        "id": "p_abb",
        "part_number": "MS132-16",
        "brand": "ABB",
        "description": "Manual Motor Starter",
        "category": "Switchgear",
        "overall_quality_score": 95.0,
        "status": "VERIFIED",
    })
    create_product(db_session, {
        "id": "p_siemens",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Sirius Circuit Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 85.0,
        "status": "REQUIRES_REVIEW",
    })

    # Search query "ABB"
    r_search = client.get("/api/products?q=ABB")
    assert r_search.status_code == 200
    items = r_search.json()
    assert len(items) == 1
    assert items[0]["brand"] == "ABB"

    # Status filter "REQUIRES_REVIEW"
    r_status = client.get("/api/products?status=REQUIRES_REVIEW")
    assert r_status.status_code == 200
    items_status = r_status.json()
    assert len(items_status) == 1
    assert items_status[0]["brand"] == "Siemens"


def test_upload_file_size_and_type_security(db_session):
    """Test file upload reject unsupported types and excessive file size."""
    # Test invalid extension (.exe)
    invalid_file = io.BytesIO(b"malicious payload")
    resp_bad_ext = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("exploit.exe", invalid_file, "application/octet-stream")},
    )
    assert resp_bad_ext.status_code == 422
    assert "Unsupported file type" in resp_bad_ext.json()["detail"]

    # Test valid PDF upload
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample datasheet content")
    resp_valid = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("datasheet.pdf", valid_pdf, "application/pdf")},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["file_info"]["filename"] == "datasheet.pdf"
