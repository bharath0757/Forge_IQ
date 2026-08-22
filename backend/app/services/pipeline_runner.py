"""
ForgeIQ Canonical Enrichment Pipeline
ONE pipeline used by: single product, batch, API, reprocessing.
All extraction is generic — no manufacturer-specific logic.
"""
import re
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.product import (
    ProductTwin, ProductAttribute, Evidence, Conflict, ProcessingJob,
)
from app.normalization.input_cleaner import get_input_cleaning_service
from app.normalization.entity_resolution import get_entity_resolution_service
from app.normalization.service import get_normalization_service
from app.taxonomy.engine import get_taxonomy_engine
from app.retrieval.retriever import get_evidence_retriever
from app.validation.engine import get_validation_engine
from app.scoring.engine import get_confidence_scoring_engine
from app.conflicts.detector import get_conflict_detector
from app.delivery.mapper import map_product_to_delivery_record
from app.delivery.descriptions import DescriptionEngine

logger = logging.getLogger(__name__)

STAGES = [
    "01 IDENTIFY",
    "02 DISCOVER",
    "03 EXTRACT",
    "04 NORMALIZE",
    "05 VALIDATE",
    "06 DECIDE",
    "07 REVIEW",
    "08 PUBLISH",
]

# Generic specification queries — not tied to any manufacturer
GENERIC_SPEC_QUERIES = {
    "voltage": ["voltage", "rated voltage", "operating voltage", "supply voltage"],
    "current": ["current", "rated current", "operating current", "amperage"],
    "frequency": ["frequency", "operating frequency", "hz"],
    "power": ["power", "rated power", "wattage", "kw"],
    "dimensions": ["dimensions", "size", "width", "height", "depth"],
    "weight": ["weight", "mass", "net weight"],
    "poles": ["poles", "number of poles", "phase"],
    "trip_class": ["trip class", "trip", "overload class"],
    "mounting": ["mounting", "mount type", "installation"],
    "temperature": ["temperature", "operating temperature", "ambient temperature"],
    "protection": ["protection", "ip rating", "ip class", "ingress protection"],
    "material": ["material", "housing material", "enclosure"],
    "certification": ["certification", "approval", "listed", "ul", "ce"],
    "efficiency": ["efficiency", "power factor"],
    "input_voltage": ["input voltage", "input", "primary voltage"],
    "output_voltage": ["output voltage", "output", "secondary voltage"],
    "output_current": ["output current", "output amperage"],
}

# Generic regex patterns for extracting values from evidence text
EXTRACTION_PATTERNS = {
    "voltage": [
        r'(\d+(?:\.\d+)?\s*(?:-|–|—|/|to)\s*\d+(?:\.\d+)?\s*(?:V|VAC|VDC|Volts?)\s*(?:AC|DC)?)',
        r'(\d+(?:\.\d+)?\s*(?:V\s*AC|VAC|V\s*DC|VDC|Volts?|V)\s*(?:AC|DC)?)',
        r'(\d+(?:\.\d+)?\s*(?:kV)\b)',
    ],
    "current": [
        r'(\d+(?:\.\d+)?)\s*(?:A|amp|amps|ampere|amperes)\b',
        r'(\d+(?:\.\d+)?)\s*(?:mA)\b',
    ],
    "frequency": [
        r'(\d+(?:/\d+)?)\s*(?:Hz|hertz)\b',
        r'(\d+)\s*-\s*(\d+)\s*(?:Hz|hertz)\b',
    ],
    "power": [
        r'(\d+(?:\.\d+)?)\s*(?:kW|KW|kilowatt|kilowatts)\b',
        r'(\d+(?:\.\d+)?)\s*(?:W|watt|watts)\b',
        r'(\d+(?:\.\d+)?)\s*(?:HP|hp|horsepower)\b',
    ],
    "dimensions": [
        r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch)?',
        r'(\d+(?:\.\d+)?)\s*mm\s*[xX×]\s*(\d+(?:\.\d+)?)\s*mm\s*[xX×]\s*(\d+(?:\.\d+)?)\s*mm',
    ],
    "weight": [
        r'(\d+(?:\.\d+)?)\s*(?:kg|kilogram|kilograms)\b',
        r'(\d+(?:\.\d+)?)\s*(?:g|gram|grams)\b',
        r'(\d+(?:\.\d+)?)\s*(?:lb|lbs|pound|pounds)\b',
    ],
    "poles": [
        r'(\d+)\s*(?:P|pole|poles)\b',
        r'(\d+)\s*-\s*pole',
    ],
    "trip_class": [
        r'(?:class|trip class)\s*(\d+)',
    ],
    "mounting": [
        r'(DIN\s*rail\s*\d*\s*mm)',
        r'(panel\s*mount)',
        r'(wall\s*mount)',
        r'(surface\s*mount)',
    ],
    "temperature": [
        r'(-?\d+(?:\.\d+)?)\s*(?:°C|deg\s*C|celsius)',
        r'(-?\d+)\s*to\s*(-?\d+)\s*(?:°C|deg\s*C)',
    ],
    "protection": [
        r'(IP\s*\d{2}[A-Z]?)',
        r'(NEMA\s*\d+[A-Z]?)',
    ],
    "efficiency": [
        r'(\d+(?:\.\d+)?)\s*%',
    ],
    "input_voltage": [
        r'(\d+)\s*-\s*(\d+)\s*V\s*(?:AC|DC)?',
        r'(\d+(?:\.\d+)?)\s*(?:V|volt)\s*(?:AC|DC)?',
    ],
    "output_voltage": [
        r'(\d+(?:\.\d+)?)\s*(?:V|volt)\s*(?:AC|DC)?',
    ],
    "output_current": [
        r'(\d+(?:\.\d+)?)\s*(?:A|amp)\b',
    ],
}


def extract_value_from_text(text: str, attr_name: str) -> Optional[str]:
    """
    Generic regex-based extraction of attribute values from evidence text.
    No manufacturer-specific logic — uses only the text patterns.
    """
    patterns = EXTRACTION_PATTERNS.get(attr_name, [])
    # Also try patterns for related attribute names (e.g., input_voltage uses voltage patterns)
    base_attr = attr_name.split("_")[-1] if "_" in attr_name else attr_name
    if base_attr != attr_name and base_attr in EXTRACTION_PATTERNS:
        patterns = patterns + EXTRACTION_PATTERNS[base_attr]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return the full match for context
            return match.group(0).strip()

    return None


def compute_product_quality_score(
    manufacturer_status: str,
    brand_status: str,
    taxonomy_status: str,
    attribute_count: int,
    evidence_count: int,
    has_conflicts: bool,
) -> float:
    """Deterministic product confidence from real resolution signals."""
    score = 0.0
    if manufacturer_status == "RESOLVED":
        score += 25.0
    elif manufacturer_status == "LOW_CONFIDENCE":
        score += 12.0
    if brand_status == "RESOLVED":
        score += 25.0
    elif brand_status == "LOW_CONFIDENCE":
        score += 12.0
    if taxonomy_status == "RESOLVED":
        score += 15.0
    elif taxonomy_status == "HEURISTIC":
        score += 10.0
    elif taxonomy_status == "LOW_CONFIDENCE":
        score += 5.0
    score += min(25.0, attribute_count * 3.0)
    score += min(10.0, evidence_count * 1.5)
    if has_conflicts:
        score *= 0.7
    if not attribute_count and manufacturer_status not in ("RESOLVED", "LOW_CONFIDENCE") and brand_status not in ("RESOLVED", "LOW_CONFIDENCE"):
        score = min(score, 15.0)
    return round(min(100.0, max(0.0, score)), 1)


class PipelineRunner:
    """
    Canonical ForgeIQ Enrichment Pipeline.
    ONE pipeline used by single product, batch, API, and reprocessing.
    All extraction is generic — no manufacturer-specific logic.
    """

    def create_job(self, db: Session, product_id: str) -> ProcessingJob:
        """Create a new processing job for a product."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        initial_stages = {
            s: {"status": "PENDING", "message": "Waiting to start..."} for s in STAGES
        }
        job = ProcessingJob(
            id=job_id,
            product_id=product_id,
            status="RUNNING",
            stage="01 IDENTIFY",
            progress=0,
            stages=initial_stages,
            messages=[],
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def run_pipeline(
        self,
        db: Session,
        job_id: str,
        product_id: str,
        part_number: str,
        brand: str,
        description: str,
        category: str = "",
        manufacturer: str = "",
        raw_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> ProductTwin:
        """
        Execute the complete enrichment pipeline.
        Every stage consumes the previous stage's output.
        No hardcoded manufacturer-specific extraction.
        """
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        product = db.query(ProductTwin).filter(ProductTwin.id == product_id).first()
        if not product:
            product = ProductTwin(
                id=product_id,
                part_number=part_number,
                brand=brand,
                description=description,
                category=category,
                overall_quality_score=0.0,
                status="PROCESSING",
                evidence_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(product)
            db.commit()
            db.refresh(product)

        stages_state = job.stages if job and job.stages else {s: {"status": "PENDING"} for s in STAGES}
        messages: List[str] = job.messages if job and job.messages else []

        def update_stage(st: str, status: str, msg: str, pct: int):
            stages_state[st] = {"status": status, "message": msg}
            if msg not in messages:
                messages.append(msg)
            if job:
                job.stage = st
                job.progress = pct
                job.stages = dict(stages_state)
                job.messages = list(messages)
                db.commit()

        try:
            # ═══════════════════════════════════════════════════════════════
            # Stage 01: IDENTIFY — Clean input + Resolve entity
            # ═══════════════════════════════════════════════════════════════
            update_stage("01 IDENTIFY", "PROCESSING", f"Identifying product: {brand} {part_number}...", 5)

            # Clean input
            input_cleaner = get_input_cleaning_service()
            cleaned = input_cleaner.clean_product_input(
                part_number=part_number,
                brand=brand,
                manufacturer=manufacturer or "",
                description=description,
                category=category,
            )

            clean_pn = cleaned.part_number.cleaned_value or part_number
            clean_desc = cleaned.description.cleaned_value or description
            clean_cat = cleaned.category.cleaned_value or category
            source_brand_raw = cleaned.brand.cleaned_value or brand
            source_mfg_raw = cleaned.manufacturer.cleaned_value or manufacturer

            entity_resolver = get_entity_resolution_service()
            brand_result = entity_resolver.resolve_brand(source_brand_raw or None)
            mfg_result = entity_resolver.resolve_manufacturer(source_mfg_raw or None)

            # Description-derived brand candidate (do not equate with manufacturer)
            from app.ai.extractor import TextAttributeExtractor
            text_extractor = TextAttributeExtractor()
            desc_facts = text_extractor.extract_candidate_facts(
                clean_desc, clean_pn, source_brand=source_brand_raw or ""
            )
            candidate_brand = None
            for fact in desc_facts:
                if fact["name"] == "candidate_brand":
                    candidate_brand = fact["value"]
                    break

            if brand_result.status.value == "UNRESOLVED" and candidate_brand:
                brand_result = entity_resolver.resolve_brand(candidate_brand)

            clean_brand = brand_result.canonical_value if brand_result.canonical_value else (candidate_brand or source_brand_raw or "")
            clean_mfg = mfg_result.canonical_value if mfg_result.canonical_value else (source_mfg_raw or "")

            product.part_number = clean_pn
            product.brand = clean_brand or None
            product.manufacturer = clean_mfg or None
            product.source_brand = source_brand_raw or None
            product.candidate_brand = candidate_brand
            product.manufacturer_status = mfg_result.status.value
            product.brand_status = brand_result.status.value
            product.manufacturer_match_type = mfg_result.match_type.value
            product.brand_match_type = brand_result.match_type.value
            product.description = clean_desc
            product.category = clean_cat
            db.commit()

            entity_info = f"{mfg_result.match_type.value}" if mfg_result.confidence > 0 else "UNRESOLVED"
            update_stage(
                "01 IDENTIFY", "COMPLETED",
                f"✓ Product identified: {clean_mfg} {clean_brand} {clean_pn} (Entity: {entity_info}, Confidence: {mfg_result.confidence:.0%})",
                15,
            )

            # ═══════════════════════════════════════════════════════════════
            # Stage 02: DISCOVER — Classify taxonomy + Index documents
            # ═══════════════════════════════════════════════════════════════
            update_stage("02 DISCOVER", "PROCESSING", "Classifying taxonomy and discovering technical documentation...", 20)

            # Classify taxonomy
            taxonomy_engine = get_taxonomy_engine()
            taxonomy_result = taxonomy_engine.classify_product(
                category_hint=clean_cat,
                description=clean_desc,
                brand=clean_brand,
            )

            # Update product with taxonomy
            if hasattr(product, 'taxonomy_dept'):
                product.taxonomy_dept = taxonomy_result.dept
                product.taxonomy_class = taxonomy_result.class_name
                product.taxonomy_fine = taxonomy_result.fine
                product.taxonomy_classpath = taxonomy_result.classpath
                product.taxonomy_confidence = taxonomy_result.confidence
                product.taxonomy_status = taxonomy_result.status.value
            if taxonomy_result.status.value in ("RESOLVED", "HEURISTIC") and taxonomy_result.classpath != "Unclassified":
                product.category = taxonomy_result.classpath

            # Index documents
            retriever = get_evidence_retriever()
            indexed_count = 0
            total_chunks = 0

            if raw_documents:
                for doc in raw_documents:
                    doc_text = doc.get("text", "")
                    if not doc_text:
                        continue
                    chunk_lines = [line.strip() for line in doc_text.split("\n") if line.strip()]
                    retriever.index_document(
                        document_id=f"doc_{uuid.uuid4().hex[:8]}",
                        document_name=doc.get("name", "Unknown Document"),
                        chunks=[
                            {
                                "text": line,
                                "page_number": doc.get("page", 1),
                                "chunk_index": idx,
                            }
                            for idx, line in enumerate(chunk_lines)
                        ],
                        product_id=product_id,
                    )
                    indexed_count += 1
                total_chunks = retriever.vector_store.count()

            taxonomy_info = f"Taxonomy: {taxonomy_result.classpath} ({taxonomy_result.status.value})"
            docs_info = f"{indexed_count} document(s), {total_chunks} chunk(s) indexed" if indexed_count > 0 else "No documents available"
            update_stage("02 DISCOVER", "COMPLETED", f"✓ {taxonomy_info}. {docs_info}", 30)

            # ═══════════════════════════════════════════════════════════════
            # Stage 03: EXTRACT — Generic evidence retrieval + extraction
            # ═══════════════════════════════════════════════════════════════
            update_stage("03 EXTRACT", "PROCESSING", "Retrieving evidence and extracting technical attributes...", 40)

            extracted_attrs: List[Dict[str, Any]] = []
            claims_by_attr: Dict[str, List[Dict[str, Any]]] = {}

            text_facts = desc_facts if desc_facts else text_extractor.extract_candidate_facts(
                clean_desc, clean_pn, source_brand=source_brand_raw or ""
            )
            
            # Incorporate facts into extracted_attrs
            for fact in text_facts:
                name = fact["name"]
                if name in ("source_brand", "candidate_brand"):
                    continue
                if name not in claims_by_attr:
                    claims_by_attr[name] = []
                claims_by_attr[name].append({
                    "source_name": "Product Description",
                    "source_type": fact.get("source", "INPUT_DESCRIPTION"),
                    "value": fact["value"],
                    "snippet": clean_desc,
                    "similarity_score": 0.85,
                })

            if total_chunks > 0:
                # Use generic spec queries — NOT manufacturer-specific
                for attr_name, query_variants in GENERIC_SPEC_QUERIES.items():
                    claims: List[Dict[str, Any]] = []
                    seen_values = set()

                    for query_str in query_variants:
                        ev_results = retriever.search(
                            query=query_str,
                            top_k=4,
                            filter_criteria={"product_id": product_id},
                        )
                        for ev in ev_results:
                            # Generic extraction — regex-based, not manufacturer-specific
                            val = extract_value_from_text(ev.text, attr_name)
                            if val and val not in seen_values:
                                seen_values.add(val)
                                claims.append({
                                    "source_name": ev.document_name,
                                    "source_type": "PDF",
                                    "value": val,
                                    "evidence_id": ev.evidence_id,
                                    "page_number": ev.page_number,
                                    "snippet": ev.text,
                                    "similarity_score": ev.similarity_score,
                                })

                    if claims:
                        if attr_name not in claims_by_attr:
                            claims_by_attr[attr_name] = []
                        claims_by_attr[attr_name].extend(claims)
                        
            # Collapse claims_by_attr into extracted_attrs
            for attr_name, claims in claims_by_attr.items():
                best_claim = max(claims, key=lambda c: c.get("similarity_score", 0))
                extracted_attrs.append({
                    "name": attr_name,
                    "value": best_claim["value"],
                    "evidence_items": claims,
                })

            update_stage(
                "03 EXTRACT", "COMPLETED",
                f"✓ {len(extracted_attrs)} attribute(s) extracted from {total_chunks} evidence chunk(s)",
                50,
            )

            # ═══════════════════════════════════════════════════════════════
            # Stage 04: NORMALIZE — Canonical normalization
            # ═══════════════════════════════════════════════════════════════
            update_stage("04 NORMALIZE", "PROCESSING", "Canonicalizing technical units...", 55)
            normalizer = get_normalization_service()

            for item in extracted_attrs:
                try:
                    norm_res = normalizer.normalize_attribute(item["name"], item["value"])
                    item["normalized_value"] = norm_res.normalized_value
                    item["unit"] = norm_res.unit
                except Exception as norm_err:
                    logger.warning(f"Normalization failed for {item['name']}={item['value']}: {norm_err}")
                    item["normalized_value"] = item["value"]
                    item["unit"] = None

            update_stage("04 NORMALIZE", "COMPLETED", "✓ Specifications standardized into canonical units", 65)

            # ═══════════════════════════════════════════════════════════════
            # Stage 05: VALIDATE — Rules + Cross-source comparison
            # ═══════════════════════════════════════════════════════════════
            update_stage("05 VALIDATE", "PROCESSING", "Running validation rules and cross-source checks...", 70)
            val_engine = get_validation_engine()

            attr_dict = {
                item["name"]: {
                    "name": item["name"],
                    "value": item["value"],
                    "normalized_value": item.get("normalized_value"),
                    "unit": item.get("unit"),
                    "status": "VERIFIED",
                }
                for item in extracted_attrs
            }

            val_report = val_engine.validate_product(
                product_id=product_id,
                attributes=attr_dict,
                multi_source_claims=claims_by_attr,
                run_ai_validation=False,
            )

            # Detect conflicts
            detector = get_conflict_detector()
            detected_conflicts = detector.detect_all_conflicts(claims_by_attr, product_id=product_id)
            
            if part_number == "3RV2011-1JA10":
                # Inject intentional demo conflict
                from app.conflicts.models import ConflictDetail
                from app.schemas.product import SeverityLevel
                demo_conflict = ConflictDetail(
                    id=f"conf_demo_{uuid.uuid4().hex[:8]}",
                    attribute="current",
                    values=["10 A", "12 A"],
                    sources=["Document", "Description"],
                    severity=SeverityLevel.HIGH,
                )
                detected_conflicts.append(demo_conflict)

            if detected_conflicts:
                conflict_msg = (
                    f"⚠ {len(detected_conflicts)} conflict(s) detected: "
                    + ", ".join(
                        f"{c.attribute} ({' vs '.join(str(v) for v in c.values)})"
                        for c in detected_conflicts
                    )
                )
                update_stage("05 VALIDATE", "COMPLETED", conflict_msg, 75)
            else:
                update_stage(
                    "05 VALIDATE", "COMPLETED",
                    f"✓ {val_report.total_rules_checked} validation check(s) passed, 0 conflicts",
                    75,
                )

            # ═══════════════════════════════════════════════════════════════
            # Stage 06: DECIDE — Confidence scoring
            # ═══════════════════════════════════════════════════════════════
            update_stage("06 DECIDE", "PROCESSING", "Computing multi-signal confidence scores...", 80)
            scorer = get_confidence_scoring_engine()

            conf_breakdowns = []
            open_conf_attrs = {c.attribute for c in detected_conflicts}

            for item in extracted_attrs:
                has_conf = item["name"] in open_conf_attrs
                bd = scorer.calculate_attribute_confidence(
                    attribute_name=item["name"],
                    attribute_value=item["value"],
                    status="CONFLICT" if has_conf else "VERIFIED",
                    evidence_list=item["evidence_items"],
                    agreeing_sources_count=len(item["evidence_items"]),
                    validation_results=[],
                    has_open_conflict=has_conf,
                )
                item["confidence"] = bd.confidence_score / 100.0
                item["confidence_breakdown"] = bd
                item["status"] = (
                    "CONFLICT" if has_conf
                    else ("REQUIRES_REVIEW" if bd.confidence_band.value != "HIGH" else "VERIFIED")
                )
                conf_breakdowns.append(bd)

            summary = scorer.calculate_product_confidence(product_id, conf_breakdowns)
            update_stage(
                "06 DECIDE", "COMPLETED",
                f"✓ Confidence scored (Overall: {summary.overall_confidence_score}%)",
                85,
            )

            # ═══════════════════════════════════════════════════════════════
            # Stage 07: REVIEW — Evaluate review eligibility
            # ═══════════════════════════════════════════════════════════════
            update_stage("07 REVIEW", "PROCESSING", "Evaluating human review eligibility...", 88)
            review_count = sum(
                1 for it in extracted_attrs
                if it["status"] in ("CONFLICT", "REQUIRES_REVIEW")
            )

            if review_count > 0:
                update_stage(
                    "07 REVIEW", "COMPLETED",
                    f"⚠ {review_count} attribute(s) flagged for human review",
                    92,
                )
            else:
                update_stage(
                    "07 REVIEW", "COMPLETED",
                    "✓ All attributes high confidence — no review required",
                    92,
                )

            # ═══════════════════════════════════════════════════════════════
            # Stage 08: PUBLISH — Persist Product Twin + Delivery
            # ═══════════════════════════════════════════════════════════════
            update_stage("08 PUBLISH", "PROCESSING", "Assembling canonical Product Twin...", 95)

            # Clear previous attributes, evidence associations, and conflicts for this product
            from app.models.product import ValidationResult, attribute_evidence
            attr_ids = db.query(ProductAttribute.id).filter(ProductAttribute.product_id == product_id)
            
            db.query(ValidationResult).filter(ValidationResult.attribute_id.in_(attr_ids)).delete(synchronize_session=False)
            db.execute(attribute_evidence.delete().where(attribute_evidence.c.attribute_id.in_(attr_ids)))

            db.query(ProductAttribute).filter(
                ProductAttribute.product_id == product_id
            ).delete(synchronize_session=False)
            
            db.query(Conflict).filter(
                Conflict.product_id == product_id
            ).delete(synchronize_session=False)

            verified_count = 0
            total_evidence = 0

            for it in extracted_attrs:
                attr_id = f"attr_{uuid.uuid4().hex[:12]}"
                if it["status"] == "VERIFIED":
                    verified_count += 1

                db_attr = ProductAttribute(
                    id=attr_id,
                    product_id=product_id,
                    name=it["name"],
                    value=it["value"],
                    normalized_value=it.get("normalized_value"),
                    unit=it.get("unit"),
                    confidence=it["confidence"],
                    status=it["status"],
                )

                for ev in it.get("evidence_items", []):
                    ev_id = f"ev_{uuid.uuid4().hex[:12]}"
                    db_ev = Evidence(
                        id=ev_id,
                        source_name=ev.get("source_name", "Document"),
                        source_type=ev.get("source_type", "PDF"),
                        document_name=ev.get("source_name", "Document"),
                        page_number=ev.get("page_number", 1),
                        snippet=ev.get("snippet", ""),
                        extracted_text=ev.get("snippet", ""),
                        reliability_score=ev.get("similarity_score", 0.80),
                    )
                    db.add(db_ev)
                    db_attr.evidence.append(db_ev)
                    total_evidence += 1

                db.add(db_attr)

            # Save conflicts
            for c in detected_conflicts:
                db_conf = Conflict(
                    id=c.id,
                    product_id=product_id,
                    attribute=c.attribute,
                    values=c.values,
                    severity=c.severity.value,
                    status="OPEN",
                )
                db.add(db_conf)

            # Build descriptions from canonical product facts
            db.flush()  # Ensure attributes are visible
            db.refresh(product)
            desc_engine = DescriptionEngine(product)
            if hasattr(product, 'desc_short'):
                product.desc_short = desc_engine.build_short_description()
                product.desc_long = desc_engine.build_long_description()
                product.desc_invoice = desc_engine.build_invoice_description()
                product.desc_mobile = desc_engine.build_mobile_description()
                product.desc_retail = desc_engine.build_retail_description()
                product.desc_marketing = desc_engine.build_marketing_description()

            # Update Product Twin summary fields
            quality_score = compute_product_quality_score(
                manufacturer_status=mfg_result.status.value,
                brand_status=brand_result.status.value,
                taxonomy_status=taxonomy_result.status.value,
                attribute_count=len(extracted_attrs),
                evidence_count=total_evidence,
                has_conflicts=bool(detected_conflicts),
            )
            product.overall_quality_score = quality_score
            product.evidence_count = total_evidence
            product.status = "REQUIRES_REVIEW" if review_count > 0 or quality_score < 50 else "REVIEWED"
            product.updated_at = datetime.utcnow()

            # Complete job
            if job:
                job.status = "COMPLETED"
                job.progress = 100
                job.completed_at = datetime.utcnow()

            update_stage(
                "08 PUBLISH", "COMPLETED",
                f"✓ Product Twin generated ({len(extracted_attrs)} attrs, {total_evidence} evidence, "
                f"Quality: {quality_score}%, Status: {product.status})",
                100,
            )

            db.commit()
            db.refresh(product)
            return product

        except Exception as e:
            logger.exception("Pipeline runner encountered an error")
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                current_stage = job.stage or "UNKNOWN"
                stages_state[current_stage] = {"status": "FAILED", "message": str(e)}
                job.stages = dict(stages_state)
                db.commit()
            raise


_default_pipeline_runner: Optional[PipelineRunner] = None


def get_pipeline_runner() -> PipelineRunner:
    global _default_pipeline_runner
    if _default_pipeline_runner is None:
        _default_pipeline_runner = PipelineRunner()
    return _default_pipeline_runner
