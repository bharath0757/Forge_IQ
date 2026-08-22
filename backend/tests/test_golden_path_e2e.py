import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db

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


def test_golden_path_complete_14_step_scenario():
    """
    End-to-end golden path test verifying all 14 steps through the real backend API:
    1. Product accepted
    2. Document uploaded
    3. Document processed
    4. Evidence generated
    5. Attributes extracted
    6. Attributes normalized
    7. Attributes validated
    8. Confidence calculated
    9. Conflict detected
    10. Product Twin created
    11. Review item created
    12. Human review performed
    13. Product status updated
    14. JSON exported
    """

    # ── Step 1 & 2: Product Accepted & Document Uploaded ──────────────────
    sample_pdf_bytes = (
        b"%PDF-1.4\n"
        b"Siemens SIRIUS 3RV2011-1JA10 Motor Starter Protector.\n"
        b"Rated operational voltage Ue: 400 V AC, 690 V max.\n"
        b"Rated operational current Ie: 10 A. Setting range: 7 - 10 A.\n"
        b"Operational power: 7.5 kW at 400 V.\n"
        b"Operating frequency: 50/60 Hz.\n"
        b"Number of poles: 3P (3 poles).\n"
        b"Dimensions (H x W x D): 97 mm x 45 mm x 97 mm.\n"
    )

    ingest_resp = client.post(
        "/api/products",
        data={
            "part_number": "3RV2011-1JA10",
            "brand": "Siemens",
            "description": "Motor Protection Circuit Breaker. 400 V AC. 10 A. 7.5 kW. 50/60 Hz. 3 Poles. 97 x 45 x 97 mm. 0.45 kg.",
            "category": "Motor Protection Circuit Breakers",
        },
        files={"file": ("siemens_3rv2011_datasheet.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert ingest_resp.status_code == 200, f"Step 1/2 Failed: {ingest_resp.text}"
    product_data = ingest_resp.json()
    product_id = product_data["id"]
    assert product_data["part_number"] == "3RV2011-1JA10"
    assert product_data["brand"] == "Siemens"
    assert product_data["evidence_count"] >= 1

    # ── Step 3 through 10: Run Full Pipeline (Process, Chunks, Extraction, Normalization, Validation, Confidence, Conflicts, Twin)
    pipeline_resp = client.post("/api/products/demo", params={"product_id": product_id})
    assert pipeline_resp.status_code == 200, f"Pipeline Execution Failed: {pipeline_resp.text}"
    demo_prod_id = pipeline_resp.json()["product_id"]

    # Verify live Job status
    job_resp = client.get(f"/api/products/{demo_prod_id}/job")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["status"] == "COMPLETED"
    assert job_data["progress"] == 100
    assert len(job_data["messages"]) >= 5

    # ── Step 10 & 11: Product Twin & Review items created ─────────────────
    twin_resp = client.get(f"/api/products/{demo_prod_id}")
    assert twin_resp.status_code == 200
    twin = twin_resp.json()

    assert twin["part_number"] == "3RV2011-1JA10"
    assert twin["brand"] == "Siemens"
    assert len(twin["attributes"]) >= 7

    # Verify Step 4: Evidence generated with grounded citations
    voltage_attr = next(a for a in twin["attributes"] if a["name"] == "voltage")
    assert voltage_attr["normalized_value"] == "400 V AC"
    assert len(voltage_attr["evidence"]) >= 1
    assert "400" in voltage_attr["evidence"][0]["snippet"]

    # Verify Step 6 & 8: Normalization and Confidence calculated
    assert voltage_attr["confidence_breakdown"] is not None
    assert voltage_attr["confidence_breakdown"]["confidence_band"] in ("HIGH", "MEDIUM")
    assert voltage_attr["confidence_breakdown"]["confidence_score"] >= 60.0

    # Verify Step 9: Conflict detected
    assert len(twin["conflicts"]) >= 1
    current_conflict = next(c for c in twin["conflicts"] if c["attribute"] == "current")
    assert current_conflict["status"] == "OPEN"
    assert "10 A" in current_conflict["values"]
    assert "12 A" in current_conflict["values"]

    # ── Step 12: Human Review Performed ──────────────────────────────────
    # Lead Engineer reviews the current attribute conflict and selects 10 A
    review_resp = client.post(
        f"/api/products/{demo_prod_id}/review",
        json={
            "attribute_name": "current",
            "action": "SELECT_ALTERNATIVE",
            "selected_value": "10 A",
            "reason": "Verified against Siemens primary manufacturer datasheet page 4",
            "reviewer": "Lead Systems Engineer",
        },
    )
    assert review_resp.status_code == 200, f"Review Action Failed: {review_resp.text}"
    rev_data = review_resp.json()
    assert rev_data["status"] == "SUCCESS"
    assert rev_data["selected_value"] == "10 A"

    # Verify conflict was resolved and previous value preserved
    twin_after_review = client.get(f"/api/products/{demo_prod_id}").json()
    resolved_conf = next(c for c in twin_after_review["conflicts"] if c["attribute"] == "current")
    assert resolved_conf["status"] == "RESOLVED"
    reviewed_attr = next(a for a in twin_after_review["attributes"] if a["name"] == "current")
    assert reviewed_attr["is_human_reviewed"] is True
    assert reviewed_attr["value"] == "10 A"

    # ── Step 13: Product Status Updated (Approval & Publish) ──────────────
    approve_resp = client.post(f"/api/products/{demo_prod_id}/approve")
    assert approve_resp.status_code == 200, f"Approval Failed: {approve_resp.text}"
    assert approve_resp.json()["product_status"] == "PUBLISHED"

    # ── Step 14: Canonical JSON & CSV Exported ───────────────────────────
    export_resp = client.get(f"/api/products/{demo_prod_id}/export/json")
    assert export_resp.status_code == 200
    export_json = export_resp.json()
    assert export_json["product"]["part_number"] == "3RV2011-1JA10"
    assert export_json["product"]["status"] == "PUBLISHED"
    assert len(export_json["review_history"]) >= 1
    assert export_json["review_history"][0]["selected_value"] == "10 A"

    # CSV Export
    csv_resp = client.get(f"/api/products/{demo_prod_id}/export/csv")
    assert csv_resp.status_code == 200
    assert "3RV2011-1JA10" in csv_resp.text
