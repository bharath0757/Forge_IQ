# cspell:ignore fitz poolclass
import pytest
import fitz
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.ingestion.pdf_processor import PDFProcessor
from app.models.document import Document, DocumentChunk

# Setup in-memory SQLite DB for testing
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
    # Clear tables after each test
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()
    db.close()

@pytest.fixture
def normal_pdf_bytes():
    """Create a simple PDF in memory and return bytes."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello, World! This is a test document for ForgeIQ extraction.")
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

@pytest.fixture
def empty_pdf_bytes():
    """Create an empty PDF with no text."""
    doc = fitz.open()
    doc.new_page() # page with no text
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_pdf_processor_normal(normal_pdf_bytes):
    processor = PDFProcessor()
    result = processor.process(normal_pdf_bytes, "test_doc.pdf", "doc_123")
    
    assert result.status == "COMPLETED"
    assert result.page_count == 1
    assert result.source_type == "PDF"
    assert result.filename == "test_doc.pdf"
    assert result.extracted_text_count > 0
    assert "Hello, World!" in result.chunks[0].text

def test_pdf_processor_empty(empty_pdf_bytes):
    processor = PDFProcessor()
    result = processor.process(empty_pdf_bytes, "empty_doc.pdf", "doc_124")
    
    # Should complete but with no chunks
    assert result.status == "COMPLETED"
    assert result.page_count == 1
    assert result.extracted_text_count == 0
    assert result.error_message is not None
    assert "No extractable text found" in result.error_message

def test_pdf_processor_corrupted():
    processor = PDFProcessor()
    result = processor.process(b"not a pdf", "bad.pdf", "doc_125")
    
    assert result.status == "FAILED"
    assert result.page_count == 0
    assert "Cannot open PDF" in result.error_message

def test_api_upload_document(normal_pdf_bytes, db_session):
    files = {"file": ("demo.pdf", normal_pdf_bytes, "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "demo.pdf"
    assert data["status"] == "COMPLETED"
    assert data["page_count"] == 1
    assert data["extracted_text_count"] > 0
    
    # Verify persistence
    doc_id = data["document_id"]
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.filename == "demo.pdf"
    
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(chunks) > 0
    assert chunks[0].page_number == 1
    assert "Hello, World!" in chunks[0].text

def test_api_upload_invalid_extension(normal_pdf_bytes):
    files = {"file": ("demo.txt", normal_pdf_bytes, "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    
    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]
