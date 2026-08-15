import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.retrieval.models import RetrievedEvidence
from app.retrieval.embeddings import DeterministicEmbeddingProvider
from app.retrieval.vector_store import LocalVectorStore
from app.retrieval.retriever import EvidenceRetriever, set_evidence_retriever
from app.ai.extractor import ProductAttributeExtractor, format_evidence_for_prompt
from app.ai.schemas import MotorProtectionCircuitBreakerAttributes, ExtractedAttribute
from app.schemas.product import AttributeStatus
from app.models.product import ProductTwin, ProductAttribute, Evidence
from app.models.document import Document, DocumentChunk
from app.services.repository import create_product, save_extracted_attributes_and_evidence

# Setup SQLite DB for testing
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

app.dependency_overrides[get_db] = override_get_db
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
def sample_retriever():
    """Create a clean local retriever instance with deterministic embeddings."""
    store = LocalVectorStore()
    embedder = DeterministicEmbeddingProvider(dimension=64)
    retriever = EvidenceRetriever(vector_store=store, embedding_provider=embedder)
    set_evidence_retriever(retriever)
    return retriever


def test_index_document_preserves_metadata(sample_retriever):
    """Test that index_document preserves document, page, chunk, text, and similarity."""
    chunks = [
        {
            "id": "chunk_001",
            "page_number": 1,
            "chunk_index": 0,
            "text": "Siemens Sirius 3RV2011 Motor Starter Protector. Operational voltage rated 400 V AC.",
        },
        {
            "id": "chunk_002",
            "page_number": 2,
            "chunk_index": 1,
            "text": "Rated current setting range 0.28 to 0.4 A. Trip class 10. DIN rail mounting.",
        },
        {
            "id": "chunk_003",
            "page_number": 3,
            "chunk_index": 2,
            "text": "Operating frequency 50/60 Hz. 3 poles design for motor branch circuits.",
        }
    ]

    indexed_ids = sample_retriever.index_document(
        document_id="doc_datasheet_01",
        document_name="Siemens_3RV2011_Datasheet.pdf",
        chunks=chunks,
        product_id="prod_siemens_01"
    )

    assert len(indexed_ids) == 3
    assert "chunk_001" in indexed_ids

    # Verify get_evidence preserves full metadata
    fetched = sample_retriever.get_evidence(["chunk_001", "chunk_002"])
    assert len(fetched) == 2
    assert fetched[0].document_name == "Siemens_3RV2011_Datasheet.pdf"
    assert fetched[0].page_number == 1
    assert fetched[0].chunk_index == 0
    assert "voltage rated 400 V" in fetched[0].text
    assert fetched[0].product_id == "prod_siemens_01"


def test_search_configurable_top_k(sample_retriever):
    """Test that search respects the configurable top_k parameter and ranks by similarity."""
    chunks = [
        {"id": "c1", "page_number": 1, "chunk_index": 0, "text": "Voltage rating: 400V AC 50Hz"},
        {"id": "c2", "page_number": 1, "chunk_index": 1, "text": "Current rating: 16 Amperes nominal"},
        {"id": "c3", "page_number": 2, "chunk_index": 2, "text": "Mounting type: DIN Rail 35mm"},
        {"id": "c4", "page_number": 2, "chunk_index": 3, "text": "Standards: IEC 60947-4-1, UL 508"},
        {"id": "c5", "page_number": 3, "chunk_index": 4, "text": "Dimensions: 97mm x 45mm x 97mm"},
    ]
    sample_retriever.index_document(
        document_id="doc_02",
        document_name="specs.pdf",
        chunks=chunks
    )

    # Test top_k = 2
    results_top2 = sample_retriever.search("voltage rating specifications", top_k=2)
    assert len(results_top2) == 2
    assert all(isinstance(r, RetrievedEvidence) for r in results_top2)
    assert results_top2[0].similarity_score >= results_top2[1].similarity_score
    assert results_top2[0].similarity_score > 0.0
    assert results_top2[0].evidence_id == "c1"

    # Test top_k = 4
    results_top4 = sample_retriever.search("voltage rating specifications", top_k=4)
    assert len(results_top4) == 4


def test_format_evidence_for_prompt():
    """Verify evidence is formatted into structured snippets with IDs and metadata."""
    evidence = [
        RetrievedEvidence(
            evidence_id="ev-101",
            document_id="doc-1",
            document_name="Datasheet.pdf",
            page_number=4,
            chunk_index=2,
            text="Rated operational voltage: 400 V AC.",
            similarity_score=0.92,
        )
    ]
    formatted = format_evidence_for_prompt(evidence)
    assert "[Evidence ID: ev-101]" in formatted
    assert "Datasheet.pdf" in formatted
    assert "Page 4" in formatted
    assert "0.9200" in formatted
    assert "Rated operational voltage: 400 V AC." in formatted


def test_extractor_with_grounded_evidence(sample_retriever):
    """Test that extraction uses retrieved evidence and populates evidence IDs in final attributes."""
    # Index sample document chunks
    chunks = [
        {
            "id": "ev_volt_01",
            "page_number": 4,
            "chunk_index": 0,
            "text": "Rated operational voltage Ue = 400 V AC. Frequency 50/60 Hz. Number of poles: 3.",
        }
    ]
    sample_retriever.index_document(
        document_id="doc_siemens",
        document_name="Manufacturer_Datasheet.pdf",
        chunks=chunks,
        product_id="prod_100"
    )

    # Mock AI Provider
    mock_ai_provider = MagicMock()
    mock_ai_provider.extract_product_attributes.return_value = MotorProtectionCircuitBreakerAttributes(
        voltage=ExtractedAttribute(value="400 V", status="EXTRACTED", evidence_ids=["ev_volt_01"]),
        current=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        frequency=ExtractedAttribute(value="50/60 Hz", status="EXTRACTED", evidence_ids=["ev_volt_01"]),
        dimensions=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        material=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        poles=ExtractedAttribute(value=3, status="EXTRACTED", evidence_ids=["ev_volt_01"]),
        trip_class=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        mounting=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        application=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        standards=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[])
    )

    extractor = ProductAttributeExtractor(retriever=sample_retriever, ai_provider=mock_ai_provider)
    result = extractor.extract(
        product_info={
            "id": "prod_100",
            "part_number": "3RV2011",
            "brand": "Siemens",
            "category": "Motor Protection Circuit Breaker",
            "description": "Circuit breaker for motor protection",
        },
        top_k=3
    )

    assert result["status"] == "SUCCESS"
    assert len(result["retrieved_evidence"]) > 0

    # Ensure the LLM received retrieved evidence snippets and NOT blindly the whole raw file
    call_args = mock_ai_provider.extract_product_attributes.call_args[1]
    assert "ev_volt_01" in call_args["evidence"]
    assert "Manufacturer_Datasheet.pdf" in call_args["evidence"]

    # Verify final attributes contain exact evidence IDs and statuses
    attributes = {a.name: a for a in result["attributes"]}
    assert attributes["voltage"].value == "400 V"
    assert attributes["voltage"].status == AttributeStatus.VERIFIED
    assert attributes["voltage"].evidence_ids == ["ev_volt_01"]
    assert attributes["voltage"].confidence > 0.0

    assert attributes["poles"].value == 3
    assert attributes["poles"].evidence_ids == ["ev_volt_01"]

    assert attributes["current"].value is None
    assert attributes["current"].status == AttributeStatus.UNKNOWN
    assert attributes["current"].evidence_ids == []


def test_extractor_insufficient_evidence_fallback(sample_retriever):
    """Test that extractor falls back to UNKNOWN attributes when retrieval yields no evidence."""
    # Ensure retriever is empty
    sample_retriever.vector_store.clear()

    mock_ai_provider = MagicMock()
    extractor = ProductAttributeExtractor(retriever=sample_retriever, ai_provider=mock_ai_provider)

    result = extractor.extract(
        product_info={
            "id": "prod_empty",
            "part_number": "UNKNOWN-001",
            "brand": "UnknownBrand",
            "category": "General",
            "description": "No documents available",
        },
        top_k=5
    )

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert len(result["retrieved_evidence"]) == 0
    # LLM should not even be called when there is zero evidence
    assert mock_ai_provider.extract_product_attributes.call_count == 0

    # All attributes should be UNKNOWN with empty evidence IDs
    for attr in result["attributes"]:
        assert attr.status == AttributeStatus.UNKNOWN
        assert attr.value is None
        assert attr.evidence_ids == []
        assert attr.confidence == 0.0


def test_api_extract_and_evidence_endpoints(db_session, sample_retriever):
    """Test full API integration: indexing, evidence endpoint, extraction endpoint, and persistence."""
    # 1. Create a product in DB
    prod = create_product(db_session, {
        "id": "prod_api_test",
        "part_number": "3RV2011-1AA10",
        "brand": "Siemens",
        "description": "Sirius motor protection circuit breaker",
        "category": "Motor Protection Circuit Breaker",
        "overall_quality_score": 0.0,
        "status": "DRAFT",
        "evidence_count": 0,
    })

    # 2. Index evidence
    sample_retriever.index_document(
        document_id="doc_api_01",
        document_name="Siemens_Datasheet.pdf",
        chunks=[
            {
                "id": "chunk_api_v",
                "page_number": 4,
                "chunk_index": 0,
                "text": "Operational voltage: 400 V AC. Rated current: 0.4 A. Trip class 10.",
            }
        ],
        product_id="prod_api_test"
    )

    # 3. Test GET /api/products/{id}/evidence
    ev_response = client.get(f"/api/products/{prod.id}/evidence?top_k=2")
    assert ev_response.status_code == 200
    ev_data = ev_response.json()
    assert ev_data["count"] > 0
    assert ev_data["evidence"][0]["document_name"] == "Siemens_Datasheet.pdf"

    # 4. Test POST /api/products/{id}/extract with mocked LLM
    with patch("app.ai.provider.LangchainOpenAIProvider.extract_product_attributes") as mock_extract:
        mock_extract.return_value = MotorProtectionCircuitBreakerAttributes(
            voltage=ExtractedAttribute(value="400 V", status="EXTRACTED", evidence_ids=["chunk_api_v"]),
            current=ExtractedAttribute(value="0.4 A", status="EXTRACTED", evidence_ids=["chunk_api_v"]),
            frequency=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            dimensions=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            material=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            poles=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            trip_class=ExtractedAttribute(value="Class 10", status="EXTRACTED", evidence_ids=["chunk_api_v"]),
            mounting=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            application=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            standards=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[])
        )

        extract_response = client.post(f"/api/products/{prod.id}/extract?top_k=3")
        assert extract_response.status_code == 200
        data = extract_response.json()

        assert data["status"] == "SUCCESS"
        assert data["evidence_count"] > 0
        assert data["overall_quality_score"] > 0

        # Check returned attributes have evidence IDs
        v_attr = next(a for a in data["attributes"] if a["name"] == "voltage")
        assert v_attr["value"] == "400 V"
        assert v_attr["status"] == "VERIFIED"
        assert "chunk_api_v" in v_attr["evidence_ids"]

    # 5. Verify database persistence and GET /api/products/{id}
    get_response = client.get(f"/api/products/{prod.id}")
    assert get_response.status_code == 200
    prod_data = get_response.json()
    assert len(prod_data["attributes"]) > 0
    persisted_v = next(a for a in prod_data["attributes"] if a["name"] == "voltage")
    assert persisted_v["value"] == "400 V"
    assert len(persisted_v["evidence"]) > 0
    assert persisted_v["evidence"][0]["document_name"] == "Siemens_Datasheet.pdf"
