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

def test_full_pipeline_integration():
    """
    Test the canonical pipeline with a non-Siemens product.
    Verifies that the extraction uses generic rules, not hardcoded data.
    """
    # 1. Ingest a completely different product (e.g., an Omron sensor)
    sample_pdf_bytes = (
        b"%PDF-1.4\n"
        b"Omron E2E-X5ME1 Proximity Sensor.\n"
        b"Operating voltage: 12 - 24 V DC.\n"
        b"Current consumption: 15 mA max.\n"
        b"Sensing distance: 5 mm.\n"
        b"IP rating: IP67.\n"
        b"Ambient temperature: -25 to 70 deg C.\n"
    )

    ingest_resp = client.post(
        "/api/products",
        data={
            "part_number": "E2E-X5ME1",
            "brand": "Omron",
            "description": "Proximity Sensor. Operating voltage: 12 - 24 V DC. Current consumption: 15 mA max.",
            "category": "Sensors",
        },
        files={"file": ("omron_sensor.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert ingest_resp.status_code == 200, f"Ingest Failed: {ingest_resp.text}"
    product_data = ingest_resp.json()
    product_id = product_data["id"]

    # 2. Run the pipeline (via demo endpoint which runs the pipeline)
    pipeline_resp = client.post("/api/products/demo", params={"product_id": product_id})
    assert pipeline_resp.status_code == 200, f"Pipeline execution failed: {pipeline_resp.text}"

    # 3. Verify Job completed
    job_resp = client.get(f"/api/products/{product_id}/job")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["status"] == "COMPLETED"
    assert job_data["progress"] == 100

    # 4. Fetch the enriched Product Twin
    twin_resp = client.get(f"/api/products/{product_id}")
    assert twin_resp.status_code == 200
    twin = twin_resp.json()

    # 5. Assert canonical entity resolution & taxonomy
    # Ensure it resolved to standard Omron
    assert twin["brand"] == "Omron" 
    
    # 6. Assert generic extraction worked (NO Siemens data)
    attr_names = [a["name"] for a in twin["attributes"]]
    assert "voltage" in attr_names
    
    voltage_attr = next(a for a in twin["attributes"] if a["name"] == "voltage")
    # Using generic extraction, it should have picked up 12-24 V
    assert "12" in str(voltage_attr["value"]) and "24" in str(voltage_attr["value"])

    # Make sure we didn't accidentally inject 400V (the Siemens demo value)
    for a in twin["attributes"]:
        assert "400" not in str(a["value"])

    # 7. Delivery export integration
    export_resp = client.get(f"/api/products/{product_id}/export/json")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["product"]["part_number"] == "E2E-X5ME1"
    assert export_data["product"]["brand"] == "Omron"

def test_batch_uses_canonical_pipeline():
    """
    Verify that batch processing actually runs the pipeline,
    creating attributes and generating delivery records.
    """
    csv_content = (
        "Brand,Mfg_Part_Num,Part_Desc,Category\n"
        "Schneider Electric,LC1D09M7,TeSys D contactor 9A 220V AC coil,Contactors\n"
        "Allen-Bradley,100-C09KF10,Contactor 9A 230V AC,Contactors\n"
    )

    # 1. Upload Batch
    upload_resp = client.post(
        "/api/batch/upload",
        files={"file": ("test_batch.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    job_id = upload_resp.json()["job_id"]

    # 2. Process Chunk
    chunk_resp = client.post(f"/api/batch/{job_id}/process_chunk", params={"chunk_size": 2})
    assert chunk_resp.status_code == 200, chunk_resp.text
    chunk_data = chunk_resp.json()
    
    assert chunk_data["processed"] == 2
    assert chunk_data["succeeded"] == 2
    
    product_ids = chunk_data["product_ids"]
    assert len(product_ids) == 2

    # 3. Verify they were actually enriched (not just DRAFT)
    p1_resp = client.get(f"/api/products/{product_ids[0]}")
    p1 = p1_resp.json()
    
    # Entity resolution should have standardized Allen-Bradley to Rockwell Automation (if that's in the canon)
    # or at least cleaned it.
    
    # Check that they have a job
    job1_resp = client.get(f"/api/products/{product_ids[0]}/job")
    assert job1_resp.status_code == 200
    assert job1_resp.json()["status"] == "COMPLETED"
    
    # It should have extracted voltage from the description (no docs)
    p1_attrs = [a["name"] for a in p1["attributes"]]
    assert "voltage" in p1_attrs or "current" in p1_attrs
