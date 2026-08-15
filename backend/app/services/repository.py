from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from app.models.product import (
    ProductTwin, ProductAttribute, Source, Evidence, ValidationResult,
    Conflict, ReviewDecision, ProcessingJob
)

def create_product(db: Session, product_data: Dict[str, Any]) -> ProductTwin:
    db_product = ProductTwin(**product_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def get_product(db: Session, product_id: str) -> Optional[ProductTwin]:
    return (
        db.query(ProductTwin)
        .options(
            selectinload(ProductTwin.attributes).selectinload(ProductAttribute.evidence),
            selectinload(ProductTwin.attributes).selectinload(ProductAttribute.validation_results),
            selectinload(ProductTwin.conflicts),
            selectinload(ProductTwin.review_decisions),
            selectinload(ProductTwin.processing_jobs),
        )
        .filter(ProductTwin.id == product_id)
        .first()
    )

def update_product(db: Session, product_id: str, updates: Dict[str, Any]) -> Optional[ProductTwin]:
    db_product = get_product(db, product_id)
    if db_product:
        for key, value in updates.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product

def list_products(
    db: Session,
    query: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
) -> List[ProductTwin]:
    q = db.query(ProductTwin).options(
        selectinload(ProductTwin.attributes),
        selectinload(ProductTwin.conflicts),
    )
    if status and status != "ALL":
        q = q.filter(ProductTwin.status == status)
    if category and category != "ALL":
        q = q.filter(ProductTwin.category == category)
    if query and query.strip():
        search_pattern = f"%{query.strip()}%"
        q = q.filter(
            (ProductTwin.part_number.ilike(search_pattern)) |
            (ProductTwin.brand.ilike(search_pattern)) |
            (ProductTwin.description.ilike(search_pattern)) |
            (ProductTwin.category.ilike(search_pattern))
        )
    return q.order_by(ProductTwin.updated_at.desc()).all()

def create_attribute(db: Session, product_id: str, attribute_data: Dict[str, Any]) -> ProductAttribute:
    db_attr = ProductAttribute(product_id=product_id, **attribute_data)
    db.add(db_attr)
    db.commit()
    db.refresh(db_attr)
    return db_attr

def create_evidence(db: Session, attribute_id: str, evidence_data: Dict[str, Any]) -> Evidence:
    db_evidence = Evidence(**evidence_data)
    db.add(db_evidence)
    
    # Link to attribute
    db_attr = db.query(ProductAttribute).filter(ProductAttribute.id == attribute_id).first()
    if db_attr:
        db_attr.evidence.append(db_evidence)
    
    db.commit()
    db.refresh(db_evidence)
    return db_evidence

def create_conflict(db: Session, product_id: str, conflict_data: Dict[str, Any]) -> Conflict:
    db_conflict = Conflict(product_id=product_id, **conflict_data)
    db.add(db_conflict)
    db.commit()
    db.refresh(db_conflict)
    return db_conflict

def create_review_decision(db: Session, product_id: str, decision_data: Dict[str, Any]) -> ReviewDecision:
    db_decision = ReviewDecision(product_id=product_id, **decision_data)
    db.add(db_decision)
    
    # Preserve previous value (it's stored in db_decision.previous_value)
    # We optionally can update the attribute's current value here if needed
    db_attr = db.query(ProductAttribute).filter(
        ProductAttribute.product_id == product_id,
        ProductAttribute.name == decision_data.get("attribute")
    ).first()
    
    if db_attr and "selected_value" in decision_data:
        db_attr.value = decision_data["selected_value"]
        # Do not delete previous value, as it is preserved in db_decision
    
    db.commit()
    db.refresh(db_decision)
    return db_decision

def save_extracted_attributes_and_evidence(
    db: Session,
    product_id: str,
    attributes: List[Any],
    evidence_items: List[Any]
) -> List[ProductAttribute]:
    import uuid

    # Build map of existing / created Evidence records
    evidence_db_map = {}
    for ev in evidence_items:
        eid = ev.evidence_id
        db_ev = db.query(Evidence).filter(Evidence.id == eid).first()
        if not db_ev:
            db_ev = Evidence(
                id=eid,
                source_name=ev.document_name,
                source_type="PDF",
                document_name=ev.document_name,
                page_number=ev.page_number,
                snippet=ev.text[:500],
                extracted_text=ev.text,
                reliability_score=ev.similarity_score,
            )
            db.add(db_ev)
            db.flush()
        evidence_db_map[eid] = db_ev

    # Clear existing attributes for this product
    existing_attrs = db.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).all()
    for ea in existing_attrs:
        db.delete(ea)
    db.flush()

    created_attrs: List[ProductAttribute] = []
    extracted_count = 0

    for attr in attributes:
        attr_id = f"attr_{uuid.uuid4().hex[:12]}"
        status_val = attr.status.value if hasattr(attr.status, "value") else str(attr.status)
        if status_val == "VERIFIED" and attr.value is not None:
            extracted_count += 1

        db_attr = ProductAttribute(
            id=attr_id,
            product_id=product_id,
            name=attr.name,
            value=attr.value,
            normalized_value=attr.normalized_value,
            unit=attr.unit,
            confidence=attr.confidence,
            status=status_val,
        )

        # Attach linked evidence
        for eid in attr.evidence_ids:
            if eid in evidence_db_map:
                db_attr.evidence.append(evidence_db_map[eid])

        db.add(db_attr)
        created_attrs.append(db_attr)

    # Update product stats
    product = get_product(db, product_id)
    if product:
        total_attrs = len(attributes) if attributes else 1
        quality_score = round((extracted_count / total_attrs) * 100.0, 1)
        product.overall_quality_score = quality_score
        product.evidence_count = len(evidence_items)
        product.status = "REQUIRES_REVIEW" if any(a.status == "REQUIRES_REVIEW" for a in attributes) else "DRAFT"

    db.commit()
    return created_attrs


def save_validation_results(
    db: Session,
    product_id: str,
    validation_report: Any
) -> None:
    import uuid

    # Map product attributes by name
    attrs = db.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).all()
    attr_map = {a.name: a for a in attrs}

    # Clear old validation results for this product's attributes
    for a in attrs:
        db.query(ValidationResult).filter(ValidationResult.attribute_id == a.id).delete()
    # Clear old conflicts for this product
    db.query(Conflict).filter(Conflict.product_id == product_id).delete()

    for item in validation_report.results:
        attr_obj = attr_map.get(item.attribute_name) if item.attribute_name else None
        val_id = f"val_{uuid.uuid4().hex[:12]}"
        
        # severity string
        sev_str = item.severity.value if hasattr(item.severity, "value") else str(item.severity)

        db_val = ValidationResult(
            id=val_id,
            attribute_id=attr_obj.id if attr_obj else (attrs[0].id if attrs else None),
            rule=item.rule,
            passed=item.passed,
            message=item.message,
            severity=sev_str,
        )
        db.add(db_val)

    # Save conflicts
    for c in validation_report.conflicts:
        conf_id = f"conf_{uuid.uuid4().hex[:12]}"
        sev_str = c.severity.value if hasattr(c.severity, "value") else str(c.severity)
        db_conf = Conflict(
            id=conf_id,
            product_id=product_id,
            attribute=c.attribute_name,
            values=c.conflicting_values,
            severity=sev_str,
            status="OPEN"
        )
        db.add(db_conf)

    # Update product status
    product = get_product(db, product_id)
    if product and validation_report.status == "REQUIRES_REVIEW":
        product.status = "REQUIRES_REVIEW"

    db.commit()
