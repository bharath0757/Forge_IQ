import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.product import (
    ProductTwin, ProductAttribute, Source, Evidence, ValidationResult,
    Conflict, ReviewDecision, ProcessingJob
)
from app.services.repository import (
    create_product, get_product, update_product, list_products,
    create_attribute, create_evidence, create_conflict, create_review_decision
)

# Use in-memory SQLite for fast testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_create_and_get_product(db):
    product_data = {
        "id": "prod_1",
        "part_number": "PN-123",
        "brand": "Acme",
        "description": "Anvil",
        "category": "Tools",
        "overall_quality_score": 95.0,
        "status": "DRAFT"
    }
    
    product = create_product(db, product_data)
    assert product.id == "prod_1"
    assert product.brand == "Acme"
    
    fetched_product = get_product(db, "prod_1")
    assert fetched_product is not None
    assert fetched_product.part_number == "PN-123"

def test_update_product(db):
    create_product(db, {"id": "prod_2", "brand": "Old Brand"})
    
    updated = update_product(db, "prod_2", {"brand": "New Brand"})
    assert updated.brand == "New Brand"
    
    fetched = get_product(db, "prod_2")
    assert fetched.brand == "New Brand"

def test_create_attribute_and_evidence(db):
    create_product(db, {"id": "prod_3"})
    
    attr_data = {
        "id": "attr_1",
        "name": "weight",
        "value": {"value": 10, "unit": "kg"},
        "confidence": 0.9,
        "status": "VERIFIED"
    }
    attr = create_attribute(db, "prod_3", attr_data)
    assert attr.name == "weight"
    
    ev_data = {
        "id": "ev_1",
        "source_name": "Catalog",
        "source_type": "PDF",
        "snippet": "Weighs 10kg",
        "extracted_text": "10kg",
        "reliability_score": 0.8
    }
    ev = create_evidence(db, "attr_1", ev_data)
    assert ev.id == "ev_1"
    
    # Check relationship
    db.refresh(attr)
    assert len(attr.evidence) == 1
    assert attr.evidence[0].id == "ev_1"

def test_create_review_decision(db):
    create_product(db, {"id": "prod_4"})
    attr_data = {
        "id": "attr_2",
        "name": "color",
        "value": "red",
        "confidence": 0.5,
        "status": "REQUIRES_REVIEW"
    }
    attr = create_attribute(db, "prod_4", attr_data)
    
    decision_data = {
        "id": "dec_1",
        "attribute": "color",
        "previous_value": "red",
        "selected_value": "blue",
        "reviewer_action": "MODIFY",
        "reason": "Corrected from red to blue"
    }
    decision = create_review_decision(db, "prod_4", decision_data)
    assert decision.reviewer_action == "MODIFY"
    
    # Check that attribute was updated
    db.refresh(attr)
    assert attr.value == "blue"
    # Previous value should still be preserved in the decision record
    assert decision.previous_value == "red"
