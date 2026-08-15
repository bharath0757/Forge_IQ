import pytest
import csv
import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.product import ProductTwin, ProductAttribute, Evidence, Conflict

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


def test_demo_mode_full_pipeline_execution(db_session):
    """Test POST /api/products/demo executes all 8 stages and creates product with evidence and conflict."""
    resp = client.post("/api/products/demo")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert "prod_siemens_3rv2011_demo" in data["product_id"]
    assert data["job_id"] is not None

    # Check product created
    prod_id = data["product_id"]
    get_prod = client.get(f"/api/products/{prod_id}")
    assert get_prod.status_code == 200
    p_data = get_prod.json()
    assert p_data["brand"] == "Siemens"
    assert p_data["part_number"] == "3RV2011-1JA10"
    assert len(p_data["attributes"]) >= 7

    # Verify intentional conflict created
    assert len(p_data["conflicts"]) >= 1
    conflict_attrs = [c["attribute"] for c in p_data["conflicts"]]
    assert "current" in conflict_attrs


def test_pipeline_job_status_endpoint(db_session):
    """Test GET /api/products/{id}/job returns real 8-stage progress state."""
    # First launch demo
    demo_resp = client.post("/api/products/demo")
    prod_id = demo_resp.json()["product_id"]

    job_resp = client.get(f"/api/products/{prod_id}/job")
    assert job_resp.status_code == 200
    job_data = job_resp.json()

    assert job_data["status"] == "COMPLETED"
    assert job_data["progress"] == 100
    assert "01 IDENTIFY" in job_data["stages"]
    assert "08 PUBLISH" in job_data["stages"]
    assert len(job_data["messages"]) >= 5
    assert any("Product identified" in m for m in job_data["messages"])


def test_export_json_structure(db_session):
    """Test GET /api/products/{id}/export/json returns canonical reviewed structure."""
    demo_resp = client.post("/api/products/demo")
    prod_id = demo_resp.json()["product_id"]

    resp = client.get(f"/api/products/{prod_id}/export/json")
    assert resp.status_code == 200
    data = resp.json()

    assert "forge_iq_version" in data
    assert "product" in data
    assert "attributes" in data
    assert "evidence" in data
    assert "conflicts" in data
    assert "review_history" in data

    assert data["product"]["part_number"] == "3RV2011-1JA10"
    attr_names = [a["name"] for a in data["attributes"]]
    assert "voltage" in attr_names
    assert "current" in attr_names


def test_export_csv_commerce_friendly(db_session):
    """Test GET /api/products/{id}/export/csv returns flattened CSV with valid columns."""
    demo_resp = client.post("/api/products/demo")
    prod_id = demo_resp.json()["product_id"]

    resp = client.get(f"/api/products/{prod_id}/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "3RV2011" in resp.headers["content-disposition"]

    csv_text = resp.text
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert len(rows) >= 7
    first_row = rows[0]
    assert "part_number" in first_row
    assert "canonical_value" in first_row
    assert "confidence_pct" in first_row
    assert "confidence_band" in first_row
    assert "is_human_reviewed" in first_row
    assert first_row["brand"] == "Siemens"


def test_seed_demo_catalog_endpoint(db_session):
    """Test POST /api/products/demo/seed seeds 5 realistic products across categories."""
    resp = client.post("/api/products/demo/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["seeded_count"] == 5
    brands = [p["brand"] for p in data["products"]]
    assert "Siemens" in brands
    assert "ABB" in brands
    assert "Schneider Electric" in brands
    assert "Eaton" in brands
    assert "Phoenix Contact" in brands

    # Check that summary reflects the 5 products
    summary_resp = client.get("/api/products/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_products"] == 5
    assert summary["verified_count"] >= 2
    assert summary["needs_review_count"] >= 2
    assert summary["active_conflicts_count"] >= 1
