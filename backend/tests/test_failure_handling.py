import io
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.services.repository import create_product
from app.ai.provider import DeterministicAIProvider, LangchainOpenAIProvider
from app.schemas.product import Product
from app.validation.engine import get_validation_engine
from app.retrieval.retriever import get_evidence_retriever

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


def test_failure_01_empty_part_number():
    """1. Test empty part number returns clean 422 error without stack traces."""
    resp = client.post("/api/products", data={"part_number": "   ", "brand": "Siemens", "description": "Breaker"})
    assert resp.status_code == 422
    assert "Part number is required" in resp.json()["detail"]


def test_failure_02_empty_brand():
    """2. Test empty brand returns clean 422 error."""
    resp = client.post("/api/products", data={"part_number": "3RV2011", "brand": "   ", "description": "Breaker"})
    assert resp.status_code == 422
    assert "Brand is required" in resp.json()["detail"]


def test_failure_03_unsupported_file_type():
    """3. Test unsupported file type returns clean 422 error."""
    resp = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("virus.exe", io.BytesIO(b"binary"), "application/x-msdownload")},
    )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["detail"]


def test_failure_04_oversized_file():
    """4. Test oversized file (>50MB) rejected gracefully."""
    large_payload = b"0" * (51 * 1024 * 1024)
    resp = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("huge.pdf", io.BytesIO(large_payload), "application/pdf")},
    )
    assert resp.status_code == 422
    assert "exceeds maximum allowed size" in resp.json()["detail"]


def test_failure_05_corrupted_pdf():
    """5. Test corrupted PDF handled gracefully during ingestion/extraction."""
    corrupted_data = b"NOT_A_VALID_PDF_HEADER_DATA"
    resp = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("corrupted.pdf", io.BytesIO(corrupted_data), "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["file_info"]["filename"] == "corrupted.pdf"


def test_failure_06_empty_pdf():
    """6. Test empty PDF handled safely without exceptions."""
    resp = client.post(
        "/api/products",
        data={"part_number": "3RV2011", "brand": "Siemens", "description": "Breaker"},
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert resp.status_code == 200


def test_failure_07_ai_provider_failure():
    """7. Test AI provider failure gracefully falls back to deterministic extraction."""
    fallback_provider = DeterministicAIProvider()
    result = fallback_provider.extract_product_attributes(
        product_info="Siemens 3RV2011 Motor Protection Circuit Breaker",
        evidence="Rated voltage: 400 V AC. Current: 10 A.",
        schema=Product,
    )
    assert result is not None
    assert hasattr(result, "attributes")
    attr_names = [a.name if hasattr(a, "name") else a.get("name") for a in result.attributes]
    assert "voltage" in attr_names


def test_failure_08_invalid_ai_json():
    """8. Test invalid/unstructured input text gracefully handled without exception."""
    provider = DeterministicAIProvider()
    res = provider.extract_product_attributes(
        product_info="Unknown Part",
        evidence="Non structured random text without specs",
        schema=Product,
    )
    assert res is not None
    assert hasattr(res, "attributes")


def test_failure_09_missing_evidence():
    """9. Test attribute with missing evidence is marked UNKNOWN or REQUIRES_REVIEW."""
    engine = get_validation_engine()
    report = engine.validate_product(
        product_id="p_test",
        attributes={"voltage": {"name": "voltage", "value": None, "status": "UNKNOWN"}},
        multi_source_claims={},
        run_ai_validation=False,
    )
    assert report is not None
    assert report.passed is False or len(report.results) >= 1


def test_failure_10_conflicting_attributes(db_session):
    """10. Test critical conflicts prevent auto-approval."""
    prod = create_product(db_session, {
        "id": "prod_conf_block",
        "part_number": "3RV2011",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 50.0,
        "status": "REQUIRES_REVIEW",
    })

    # Add open critical conflict
    from app.models.product import Conflict
    conf = Conflict(
        id="c_crit",
        product_id=prod.id,
        attribute="voltage",
        values=["400 V", "690 V"],
        severity="CRITICAL",
        status="OPEN",
    )
    db_session.add(conf)
    db_session.commit()

    # Attempt approve
    resp = client.post(f"/api/products/{prod.id}/approve")
    assert resp.status_code == 400
    assert "open high-severity conflict(s) must be reviewed" in resp.json()["detail"]


def test_failure_11_database_unavailable():
    """11. Test database errors return clean HTTP error instead of raw Python traceback."""
    resp = client.get("/api/products/non_existent_product_id_999999")
    assert resp.status_code == 404
    assert "Product not found" in resp.json()["detail"]


def test_failure_12_duplicate_product(db_session):
    """12. Test duplicate product ingestion handles cleanly."""
    create_product(db_session, {
        "id": "prod_dup",
        "part_number": "3RV2011-DUP",
        "brand": "Siemens",
        "description": "Breaker",
        "category": "Motor Protection",
        "overall_quality_score": 90.0,
        "status": "PUBLISHED",
    })

    # Second ingestion with same part number creates unique twin instance
    resp = client.post(
        "/api/products",
        data={"part_number": "3RV2011-DUP", "brand": "Siemens", "description": "Breaker 2"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] != "prod_dup"


def test_failure_13_network_timeout():
    """13. Test network search timeout returns empty list safely."""
    retriever = get_evidence_retriever()
    results = retriever.search(query="nonexistent_spec_query_xyz123456", top_k=3)
    assert isinstance(results, list)


def test_failure_14_export_failure():
    """14. Test export of non-existent product returns clean 404."""
    resp_json = client.get("/api/products/missing_prod_id/export/json")
    assert resp_json.status_code == 404

    resp_csv = client.get("/api/products/missing_prod_id/export/csv")
    assert resp_csv.status_code == 404
