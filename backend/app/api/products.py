import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.repository import create_product, get_product, list_products as list_products_repo

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def _validate_file_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@router.post("")
def ingest_product(
    part_number: str = Form(...),
    brand: str = Form(...),
    description: str = Form(...),
    category: str = Form("General"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    # Validate required fields
    if not part_number.strip():
        raise HTTPException(status_code=422, detail="Part number is required")
    if not brand.strip():
        raise HTTPException(status_code=422, detail="Brand is required")
    if not description.strip():
        raise HTTPException(status_code=422, detail="Description is required")

    # Validate file if provided
    file_info = None
    if file and file.filename:
        safe_filename = os.path.basename(file.filename)
        if not _validate_file_extension(safe_filename):
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        # Read file content safely
        file_content = file.file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=422,
                detail="File exceeds maximum allowed size of 50MB."
            )
        file_info = {
            "filename": safe_filename,
            "size": len(file_content),
            "content_type": file.content_type,
        }

    product_id = f"prod_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    from app.normalization.entity_resolution import get_entity_resolution_service
    resolver = get_entity_resolution_service()
    clean_brand = resolver.clean_brand(brand) or ""
    
    product_data = {
        "id": product_id,
        "part_number": part_number.strip(),
        "brand": clean_brand,
        "description": description.strip(),
        "category": category.strip() or "General",
        "overall_quality_score": 0.0,
        "status": "DRAFT",
        "evidence_count": 1 if file_info else 0,
        "created_at": now,
        "updated_at": now,
    }

    db_product = create_product(db, product_data)

    return {
        "id": db_product.id,
        "part_number": db_product.part_number,
        "brand": db_product.brand,
        "description": db_product.description,
        "category": db_product.category,
        "overall_quality_score": db_product.overall_quality_score,
        "status": db_product.status,
        "evidence_count": db_product.evidence_count,
        "created_at": str(db_product.created_at),
        "updated_at": str(db_product.updated_at),
        "file_info": file_info,
        "message": "Product ingested successfully. AI enrichment is not yet available.",
    }


@router.get("/summary")
def get_catalog_summary(db: Session = Depends(get_db)):
    """
    Return high-level catalog overview KPIs.
    """
    from app.models.product import ProductTwin, Conflict
    products = db.query(ProductTwin).all()
    total = len(products)
    if total == 0:
        return {
            "total_products": 0,
            "verified_count": 0,
            "needs_review_count": 0,
            "conflicts_count": 0,
            "average_quality_score": 0.0,
        }

    verified = sum(1 for p in products if p.status in ("VERIFIED", "PUBLISHED", "REVIEWED"))
    needs_review = sum(1 for p in products if p.status == "REQUIRES_REVIEW")
    open_conflicts = db.query(Conflict).filter(Conflict.status == "OPEN").count()
    avg_score = round(sum(p.overall_quality_score or 0.0 for p in products) / total, 1)

    return {
        "total_products": total,
        "verified_count": verified,
        "needs_review_count": needs_review,
        "conflicts_count": open_conflicts,
        "active_conflicts_count": open_conflicts,
        "average_quality_score": avg_score,
    }


@router.get("")
def list_all_products(
    q: Optional[str] = Query(None, description="Search by part number, brand, category, description"),
    status: Optional[str] = Query(None, description="Filter by status (PROCESSING, READY, REQUIRES_REVIEW, VERIFIED, ALL)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    products = list_products_repo(db, query=q, status=status, category=category)
    return [
        {
            "id": p.id,
            "part_number": p.part_number,
            "brand": p.brand,
            "description": p.description,
            "category": p.category,
            "overall_quality_score": p.overall_quality_score,
            "status": p.status,
            "evidence_count": p.evidence_count,
            "attributes_count": len(p.attributes) if p.attributes else 0,
            "conflicts_count": len([c for c in p.conflicts if c.status == "OPEN"]) if p.conflicts else 0,
            "has_open_conflict": any(c.status == "OPEN" for c in p.conflicts) if p.conflicts else False,
            "created_at": str(p.created_at),
            "updated_at": str(p.updated_at),
        }
        for p in products
    ]


@router.get("/{product_id}")
def get_product_by_id(product_id: str, db: Session = Depends(get_db)):
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.scoring.engine import get_confidence_scoring_engine
    scorer = get_confidence_scoring_engine()

    open_conflicts = {c.attribute for c in product.conflicts if c.status == "OPEN"}
    reviewed_attrs = {rd.attribute for rd in product.review_decisions}

    attributes_data = []
    for attr in product.attributes:
        evidence_list = [
            {
                "id": ev.id,
                "document_name": ev.document_name,
                "page_number": ev.page_number,
                "snippet": ev.snippet,
                "reliability_score": ev.reliability_score,
            }
            for ev in attr.evidence
        ]

        has_conflict = attr.name in open_conflicts
        bd = scorer.calculate_attribute_confidence(
            attribute_name=attr.name,
            attribute_value=attr.value,
            status=attr.status,
            evidence_list=list(attr.evidence),
            agreeing_sources_count=max(1, len(attr.evidence)),
            validation_results=list(attr.validation_results),
            has_open_conflict=has_conflict,
        )

        attributes_data.append({
            "id": attr.id,
            "name": attr.name,
            "value": attr.value,
            "normalized_value": attr.normalized_value,
            "unit": attr.unit,
            "confidence": attr.confidence,
            "status": attr.status,
            "evidence": evidence_list,
            "evidence_ids": [ev.id for ev in attr.evidence],
            "confidence_breakdown": bd.model_dump(),
            "is_human_reviewed": attr.name in reviewed_attrs,
            "has_open_conflict": has_conflict,
        })

    # Fetch validation results and conflicts if any
    validation_items = []
    for attr in product.attributes:
        for vr in attr.validation_results:
            validation_items.append({
                "id": vr.id,
                "attribute_id": vr.attribute_id,
                "rule": vr.rule,
                "passed": vr.passed,
                "message": vr.message,
                "severity": vr.severity,
            })

    conflicts_data = [
        {
            "id": c.id,
            "attribute": c.attribute,
            "values": c.values,
            "severity": c.severity,
            "status": c.status,
        }
        for c in product.conflicts
    ]

    decisions_data = [
        {
            "id": d.id,
            "attribute": d.attribute,
            "previous_value": d.previous_value,
            "selected_value": d.selected_value,
            "reviewer_action": d.reviewer_action,
            "reason": d.reason,
            "timestamp": str(d.timestamp),
        }
        for d in product.review_decisions
    ]

    return {
        "id": product.id,
        "part_number": product.part_number,
        "brand": product.brand,
        "description": product.description,
        "category": product.category,
        "overall_quality_score": product.overall_quality_score,
        "status": product.status,
        "evidence_count": product.evidence_count,
        "attributes": attributes_data,
        "validation_results": validation_items,
        "conflicts": conflicts_data,
        "review_decisions": decisions_data,
        "created_at": str(product.created_at),
        "updated_at": str(product.updated_at),
    }


@router.post("/{product_id}/extract")
def extract_attributes_endpoint(
    product_id: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
):
    """
    Retrieve relevant evidence chunks from vector storage (top-k) and extract structured product attributes.
    Persists attributes and linked evidence in the database.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.ai.extractor import ProductAttributeExtractor
    from app.services.repository import save_extracted_attributes_and_evidence

    extractor = ProductAttributeExtractor()
    product_info = {
        "id": product.id,
        "part_number": product.part_number,
        "brand": product.brand,
        "description": product.description,
        "category": product.category,
    }

    result = extractor.extract(
        product_info=product_info,
        top_k=top_k,
    )

    # Add taxonomy attributes
    from app.taxonomy.engine import get_taxonomy_engine
    tax_engine = get_taxonomy_engine()
    tax_res = tax_engine.classify_product(product.category, product.description, product.brand)
    from app.schemas.product import ProductAttribute, AttributeStatus
    for tax_key, tax_val in tax_res.dict().items():
        result["attributes"].append(ProductAttribute(
            name=tax_key.capitalize(),
            value=tax_val,
            unit="",
            confidence=0.9,
            status=AttributeStatus.VERIFIED,
            evidence_ids=[]
        ))

    # Persist in DB
    db_attrs = save_extracted_attributes_and_evidence(
        db=db,
        product_id=product.id,
        attributes=result["attributes"],
        evidence_items=result["retrieved_evidence"],
    )

    db.refresh(product)

    return {
        "product_id": product.id,
        "status": result["status"],
        "overall_quality_score": product.overall_quality_score,
        "evidence_count": len(result["retrieved_evidence"]),
        "retrieved_evidence": [
            {
                "evidence_id": ev.evidence_id,
                "document_name": ev.document_name,
                "page_number": ev.page_number,
                "chunk_index": ev.chunk_index,
                "snippet": ev.text[:300],
                "similarity_score": ev.similarity_score,
            }
            for ev in result["retrieved_evidence"]
        ],
        "attributes": [
            {
                "name": a.name,
                "value": a.value,
                "normalized_value": a.normalized_value,
                "unit": a.unit,
                "status": a.status,
                "confidence": a.confidence,
                "evidence_ids": [ev.id for ev in a.evidence],
            }
            for a in db_attrs
        ],
    }


@router.post("/{product_id}/normalize")
def normalize_product_attributes_endpoint(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Run canonical normalization on all product attributes without mutating raw values.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.normalization.service import get_normalization_service
    normalizer = get_normalization_service()

    from app.normalization.fraction_normalizer import FractionNormalizer
    from app.normalization.uom_normalizer import UOMNormalizer

    normalized_count = 0
    for attr in product.attributes:
        if attr.value is not None:
            # First, standard normalization
            norm_res = normalizer.normalize_attribute(attr.name, attr.value)
            
            # Refine value with Fraction Normalizer
            refined_val = norm_res.normalized_value or attr.value
            if isinstance(refined_val, str):
                refined_val = FractionNormalizer.normalize_string(refined_val)
                # Refine with UOM Normalizer
                refined_val = UOMNormalizer.normalize_value_and_unit(refined_val)
                
            attr.normalized_value = refined_val
            attr.unit = norm_res.unit
            if norm_res.requires_review:
                attr.status = "REQUIRES_REVIEW"
            normalized_count += 1

    db.commit()
    db.refresh(product)

    return {
        "product_id": product_id,
        "normalized_attributes_count": normalized_count,
        "status": product.status,
        "attributes": [
            {
                "name": a.name,
                "raw_value": a.value,
                "normalized_value": a.normalized_value,
                "unit": a.unit,
                "status": a.status,
            }
            for a in product.attributes
        ]
    }


@router.post("/{product_id}/validate")
def validate_product_endpoint(
    product_id: str,
    run_ai_validation: bool = False,
    db: Session = Depends(get_db),
):
    """
    Run comprehensive validation engine (deterministic rules, cross-source comparison, AI semantic checks)
    on the product's attributes and persist validation results without modifying attributes.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.validation.engine import get_validation_engine
    from app.services.repository import save_validation_results

    validator = get_validation_engine()

    # Build attribute dict
    attr_dict = {
        a.name: {
            "name": a.name,
            "value": a.value,
            "normalized_value": a.normalized_value,
            "unit": a.unit,
            "status": a.status,
            "evidence_ids": [ev.id for ev in a.evidence],
        }
        for a in product.attributes
    }

    # Group multi-source claims from linked evidence
    multi_source_claims = {}
    for a in product.attributes:
        if len(a.evidence) > 1:
            claims = [
                {
                    "source_name": ev.document_name or ev.source_name,
                    "value": a.value,
                    "evidence_id": ev.id,
                }
                for ev in a.evidence
            ]
            multi_source_claims[a.name] = claims

    report = validator.validate_product(
        product_id=product.id,
        attributes=attr_dict,
        multi_source_claims=multi_source_claims,
        run_ai_validation=run_ai_validation,
    )

    # Persist validation results
    save_validation_results(db, product.id, report)
    db.refresh(product)

    return {
        "product_id": product.id,
        "passed": report.passed,
        "status": report.status,
        "total_rules_checked": report.total_rules_checked,
        "passed_count": report.passed_count,
        "failed_count": report.failed_count,
        "conflict_count": report.conflict_count,
        "results": [r.model_dump() for r in report.results],
        "conflicts": [c.model_dump() for c in report.conflicts],
    }


@router.get("/{product_id}/evidence")
def get_product_evidence(
    product_id: str,
    query: Optional[str] = None,
    top_k: int = 5,
    db: Session = Depends(get_db),
):
    """
    Search and retrieve evidence chunks for a specific product from vector storage.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.retrieval.retriever import get_evidence_retriever
    retriever = get_evidence_retriever()

    search_query = query or f"{product.brand} {product.part_number} {product.category} {product.description}"
    evidence_results = retriever.search(
        query=search_query,
        top_k=top_k,
        filter_criteria={"product_id": product_id}
    )

    if not evidence_results:
        # Fallback to general search without filter
        evidence_results = retriever.search(query=search_query, top_k=top_k)

    return {
        "product_id": product_id,
        "query": search_query,
        "count": len(evidence_results),
        "evidence": [ev.model_dump() for ev in evidence_results]
    }


@router.get("/{product_id}/confidence")
def get_product_confidence_endpoint(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Calculate and return the multi-signal explainable confidence scoring breakdown for a product.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.scoring.engine import get_confidence_scoring_engine
    scorer = get_confidence_scoring_engine()

    open_conflicts = {c.attribute for c in product.conflicts if c.status == "OPEN"}

    breakdowns = []
    for attr in product.attributes:
        # Check if attribute has validation results
        attr_val_results = attr.validation_results
        has_conflict = attr.name in open_conflicts

        bd = scorer.calculate_attribute_confidence(
            attribute_name=attr.name,
            attribute_value=attr.value,
            status=attr.status,
            evidence_list=list(attr.evidence),
            agreeing_sources_count=max(1, len(attr.evidence)),
            validation_results=list(attr_val_results),
            has_open_conflict=has_conflict,
        )
        breakdowns.append(bd)

    summary = scorer.calculate_product_confidence(product.id, breakdowns)
    return summary.model_dump()


@router.get("/{product_id}/conflicts")
def get_product_conflicts_endpoint(
    product_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all detected conflicts across sources for a product.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.conflicts.service import get_conflict_service
    service = get_conflict_service()

    conflicts = service.list_conflicts_for_product(db, product_id, status=status)
    return [
        {
            "id": c.id,
            "product_id": c.product_id,
            "attribute": c.attribute,
            "values": c.values,
            "severity": c.severity,
            "status": c.status,
        }
        for c in conflicts
    ]


@router.post("/{product_id}/conflicts/{conflict_id}/resolve")
def resolve_conflict_endpoint(
    product_id: str,
    conflict_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Resolve a specific conflict with reviewer selected value and rationale.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.conflicts.service import get_conflict_service
    from app.conflicts.models import ConflictResolutionRequest, ConflictResolutionAction

    service = get_conflict_service()
    req = ConflictResolutionRequest(
        selected_value=payload.get("selected_value"),
        reason=payload.get("reason", "Manual reviewer resolution"),
        reviewer_action=payload.get("reviewer_action", ConflictResolutionAction.APPROVE_VALUE),
    )

    resolved = service.resolve_conflict(db, conflict_id, req)
    if not resolved:
        raise HTTPException(status_code=404, detail="Conflict not found")

    return {
        "status": "SUCCESS",
        "conflict_id": resolved.id,
        "conflict_status": resolved.status,
        "message": f"Conflict for '{resolved.attribute}' successfully resolved with value '{req.selected_value}'.",
    }


@router.post("/{product_id}/conflicts/{conflict_id}/dismiss")
def dismiss_conflict_endpoint(
    product_id: str,
    conflict_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Dismiss a specific conflict as not actionable or acceptable variance.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.conflicts.service import get_conflict_service
    service = get_conflict_service()
    reason = payload.get("reason", "Dismissed by reviewer")

    dismissed = service.dismiss_conflict(db, conflict_id, reason=reason)
    if not dismissed:
        raise HTTPException(status_code=404, detail="Conflict not found")

    return {
        "status": "SUCCESS",
        "conflict_id": dismissed.id,
        "conflict_status": dismissed.status,
        "message": f"Conflict for '{dismissed.attribute}' dismissed.",
    }


@router.post("/{product_id}/review")
def review_attribute_endpoint(
    product_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Human Review Action:
    - Preserves original AI value.
    - Stores reviewer decision audit record.
    - Updates Product Twin attribute.
    - Resolves or marks conflicts appropriately.
    - Recalculates quality score.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    attribute_name = payload.get("attribute_name")
    action = payload.get("action")  # ACCEPT_AI_VALUE, SELECT_ALTERNATIVE, MARK_UNKNOWN, DISMISS_CONFLICT
    selected_value = payload.get("selected_value")
    reason = payload.get("reason", "Human reviewer decision")
    reviewer = payload.get("reviewer", "Reviewer")

    if not attribute_name or not action:
        raise HTTPException(status_code=400, detail="attribute_name and action are required")

    from app.models.product import ProductAttribute, ReviewDecision, Conflict
    from app.normalization.service import get_normalization_service
    normalizer = get_normalization_service()

    # Find attribute
    attr = db.query(ProductAttribute).filter(
        ProductAttribute.product_id == product_id,
        ProductAttribute.name == attribute_name
    ).first()

    previous_value = attr.value if attr else None

    # Handle action
    if action == "ACCEPT_AI_VALUE":
        if attr:
            attr.status = "VERIFIED"
            attr.confidence = 1.0
            selected_value = attr.value
    elif action == "SELECT_ALTERNATIVE":
        if selected_value is None:
            raise HTTPException(status_code=400, detail="selected_value is required for SELECT_ALTERNATIVE")
        if attr:
            attr.value = selected_value
            norm_res = normalizer.normalize_attribute(attribute_name, selected_value)
            attr.normalized_value = norm_res.normalized_value
            attr.unit = norm_res.unit
            attr.status = "VERIFIED"
            attr.confidence = 1.0
    elif action == "MARK_UNKNOWN":
        if attr:
            attr.value = None
            attr.normalized_value = None
            attr.status = "UNKNOWN"
            attr.confidence = 0.0
            selected_value = None
    elif action == "DISMISS_CONFLICT":
        if attr:
            selected_value = attr.value
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'")

    # Update associated conflicts if any
    conflicts = db.query(Conflict).filter(
        Conflict.product_id == product_id,
        Conflict.attribute == attribute_name,
        Conflict.status == "OPEN"
    ).all()

    for conf in conflicts:
        conf.status = "DISMISSED" if action == "DISMISS_CONFLICT" else "RESOLVED"

    # Store ReviewDecision audit record
    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    decision = ReviewDecision(
        id=decision_id,
        product_id=product_id,
        attribute=attribute_name,
        previous_value=previous_value,
        selected_value=selected_value,
        reviewer_action=action,
        reason=reason,
        timestamp=datetime.utcnow()
    )
    db.add(decision)

    # Recalculate product quality score
    all_attrs = db.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).all()
    verified_count = sum(1 for a in all_attrs if a.status == "VERIFIED" and a.value is not None)
    total_count = max(1, len(all_attrs))
    product.overall_quality_score = round((verified_count / total_count) * 100.0, 1)

    # Check remaining open conflicts
    open_count = db.query(Conflict).filter(
        Conflict.product_id == product_id,
        Conflict.status == "OPEN"
    ).count()

    if open_count == 0 and product.status == "REQUIRES_REVIEW":
        product.status = "REVIEWED"

    db.commit()
    db.refresh(product)

    return {
        "status": "SUCCESS",
        "action": action,
        "attribute_name": attribute_name,
        "selected_value": selected_value,
        "quality_score": product.overall_quality_score,
        "product_status": product.status,
        "decision_id": decision_id,
    }


@router.post("/{product_id}/approve")
def approve_product_endpoint(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Approve and publish the Product Twin if all critical conflicts are resolved.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.models.product import Conflict
    open_critical_conflicts = db.query(Conflict).filter(
        Conflict.product_id == product_id,
        Conflict.status == "OPEN",
        Conflict.severity.in_(["HIGH", "CRITICAL"])
    ).count()

    if open_critical_conflicts > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve product: {open_critical_conflicts} open high-severity conflict(s) must be reviewed first."
        )

    product.status = "PUBLISHED"
    db.commit()
    db.refresh(product)

    return {
        "status": "SUCCESS",
        "product_id": product.id,
        "product_status": product.status,
        "message": "Product Twin approved and published successfully.",
    }


@router.post("/demo/seed")
def seed_demo_catalog_endpoint(db: Session = Depends(get_db)):
    """
    Seed the 5 realistic demonstration products across distinct industrial categories
    (Siemens, ABB, Schneider Electric, Eaton, Phoenix Contact) with full evidence and conflicts.
    """
    from app.services.demo_seeder import seed_demo_products
    products = seed_demo_products(db)
    return {
        "status": "SUCCESS",
        "seeded_count": len(products),
        "products": [
            {
                "id": p.id,
                "part_number": p.part_number,
                "brand": p.brand,
                "category": p.category,
                "quality_score": p.overall_quality_score,
                "status": p.status,
            }
            for p in products
        ],
        "message": f"Successfully seeded {len(products)} realistic industrial demo products.",
    }


@router.post("/demo")
def launch_demo_mode_endpoint(
    product_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Launch ForgeIQ Demo Mode:
    Executes the full 8-stage pipeline. If product_id is provided, runs on that product.
    Otherwise, runs on the default Siemens demo product.
    """
    from app.services.pipeline_runner import get_pipeline_runner
    runner = get_pipeline_runner()

    demo_product_id = product_id or "prod_demo_siemens_3rv2011"
    product = get_product(db, demo_product_id)
    
    if not product and not product_id:
        # Fallback to creating the default demo product if missing
        from app.services.demo_seeder import seed_demo_products
        seed_demo_products(db)
        product = get_product(db, demo_product_id)
        
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    job = runner.create_job(db, demo_product_id)

    # Run the real 8-stage pipeline
    product = runner.run_pipeline(
        db=db,
        job_id=job.id,
        product_id=demo_product_id,
        part_number=product.part_number,
        brand=product.brand,
        description=product.description,
        category=product.category,
    )

    return {
        "status": "SUCCESS",
        "product_id": product.id,
        "job_id": job.id,
        "quality_score": product.overall_quality_score,
        "product_status": product.status,
        "message": "Siemens 3RV2011 demo pipeline executed successfully across all 8 stages.",
    }


@router.get("/{product_id}/job")
def get_product_job_status_endpoint(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Return the live 8-stage processing pipeline execution state and progress messages.
    """
    from app.models.product import ProcessingJob
    job = db.query(ProcessingJob).filter(ProcessingJob.product_id == product_id).order_by(ProcessingJob.started_at.desc()).first()

    if not job:
        return {
            "product_id": product_id,
            "status": "NO_JOB",
            "stage": None,
            "progress": 0,
            "stages": {},
            "messages": ["No processing job found for this product."],
        }

    return {
        "job_id": job.id,
        "product_id": job.product_id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "stages": job.stages,
        "messages": job.messages,
        "started_at": str(job.started_at),
        "completed_at": str(job.completed_at) if job.completed_at else None,
    }


@router.get("/{product_id}/export")
@router.get("/{product_id}/export/json")
def export_product_twin_json(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Export canonical Product Twin JSON structure matching the current reviewed state.
    """
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.scoring.engine import get_confidence_scoring_engine
    scorer = get_confidence_scoring_engine()
    open_conflicts = {c.attribute for c in product.conflicts if c.status == "OPEN"}
    reviewed_attrs = {rd.attribute for rd in product.review_decisions}

    attributes_list = []
    for a in product.attributes:
        has_conf = a.name in open_conflicts
        bd = scorer.calculate_attribute_confidence(
            attribute_name=a.name,
            attribute_value=a.value,
            status=a.status,
            evidence_list=list(a.evidence),
            agreeing_sources_count=max(1, len(a.evidence)),
            validation_results=list(a.validation_results),
            has_open_conflict=has_conf,
        )

        attributes_list.append({
            "name": a.name,
            "value": a.value,
            "normalized_value": a.normalized_value,
            "unit": a.unit,
            "confidence": a.confidence,
            "confidence_score": bd.confidence_score,
            "confidence_band": bd.confidence_band.value,
            "status": a.status,
            "is_human_reviewed": a.name in reviewed_attrs,
            "sources_count": len(a.evidence),
            "evidence_ids": [ev.id for ev in a.evidence],
        })

    evidence_list = []
    for a in product.attributes:
        for ev in a.evidence:
            evidence_list.append({
                "id": ev.id,
                "attribute_name": a.name,
                "document_name": ev.document_name,
                "page_number": ev.page_number,
                "snippet": ev.snippet,
                "reliability_score": ev.reliability_score,
            })

    validation_list = []
    for a in product.attributes:
        for vr in a.validation_results:
            validation_list.append({
                "attribute_name": a.name,
                "rule": vr.rule,
                "passed": vr.passed,
                "severity": vr.severity,
                "message": vr.message,
            })

    conflicts_list = [
        {
            "id": c.id,
            "attribute": c.attribute,
            "values": c.values,
            "severity": c.severity,
            "status": c.status,
        }
        for c in product.conflicts
    ]

    review_history = [
        {
            "attribute": rd.attribute,
            "action": rd.reviewer_action,
            "previous_value": rd.previous_value,
            "selected_value": rd.selected_value,
            "reason": rd.reason,
            "timestamp": str(rd.timestamp),
        }
        for rd in product.review_decisions
    ]

    product_dict = {
        "id": product.id,
        "part_number": product.part_number,
        "brand": product.brand,
        "description": product.description,
        "category": product.category,
        "overall_quality_score": product.overall_quality_score,
        "status": product.status,
        "evidence_count": product.evidence_count,
        "created_at": str(product.created_at),
        "updated_at": str(product.updated_at),
    }

    product_twin_dict = {
        **product_dict,
        "attributes": attributes_list,
        "audit_trail": review_history,
    }

    return {
        "forge_iq_version": "1.0",
        "exported_at": str(datetime.utcnow()),
        "product": product_dict,
        "product_twin": product_twin_dict,
        "attributes": attributes_list,
        "evidence": evidence_list,
        "validation": validation_list,
        "conflicts": conflicts_list,
        "review_history": review_history,
    }


@router.get("/{product_id}/export/csv")
def export_product_twin_csv(
    product_id: str,
    db: Session = Depends(get_db),
):
    """
    Export commerce-friendly flattened CSV representation of the Product Twin.
    """
    import io
    import csv
    from fastapi.responses import Response

    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from app.scoring.engine import get_confidence_scoring_engine
    scorer = get_confidence_scoring_engine()
    open_conflicts = {c.attribute for c in product.conflicts if c.status == "OPEN"}
    reviewed_attrs = {rd.attribute for rd in product.review_decisions}

    output = io.StringIO()
    writer = csv.writer(output)

    # Header columns
    writer.writerow([
        "part_number",
        "brand",
        "description",
        "category",
        "attribute_name",
        "raw_value",
        "canonical_value",
        "unit",
        "confidence_pct",
        "confidence_band",
        "status",
        "sources_count",
        "is_human_reviewed",
        "has_open_conflict",
    ])

    for a in product.attributes:
        has_conf = a.name in open_conflicts
        bd = scorer.calculate_attribute_confidence(
            attribute_name=a.name,
            attribute_value=a.value,
            status=a.status,
            evidence_list=list(a.evidence),
            agreeing_sources_count=max(1, len(a.evidence)),
            validation_results=list(a.validation_results),
            has_open_conflict=has_conf,
        )

        writer.writerow([
            product.part_number,
            product.brand,
            product.description,
            product.category,
            a.name,
            a.value or "",
            a.normalized_value or a.value or "",
            a.unit or "",
            round(bd.confidence_score, 1),
            bd.confidence_band.value,
            a.status,
            len(a.evidence),
            "YES" if a.name in reviewed_attrs else "NO",
            "YES" if has_conf else "NO",
        ])

    csv_data = output.getvalue()
    filename = f"{product.part_number.replace('/', '_')}_twin.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
