import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.product import (
    ProductTwin, ProductAttribute, Evidence, Conflict, ValidationResult, ReviewDecision
)
from app.retrieval.retriever import get_evidence_retriever

DEMO_PRODUCTS_DATA: List[Dict[str, Any]] = [
    # ── Product 1: Siemens 3RV2011-1JA10 (Requires Review - Intentional Conflict) ──
    {
        "id": "prod_demo_siemens_3rv2011",
        "part_number": "3RV2011-1JA10",
        "brand": "Siemens",
        "category": "Motor Protection Circuit Breakers",
        "description": "SIRIUS Motor Starter Protector / Circuit Breaker, 400 V AC, 10 A, 7.5 kW, 50/60 Hz, 3 Poles, 97 x 45 x 97 mm, 0.45 kg, DIN Rail Mount",
        "overall_quality_score": 87.5,
        "status": "REQUIRES_REVIEW",
        "evidence_count": 3,
        "attributes": [
            {"name": "voltage", "value": "400 V AC", "normalized_value": "400 V", "unit": "V", "confidence": 0.98, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Rated operational voltage Ue: 400 V AC, 690 V max."},
            {"name": "current", "value": "10 A", "normalized_value": "10 A", "unit": "A", "confidence": 0.65, "status": "CONFLICT", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Rated operational current Ie: 10 A. Setting range: 7 - 10 A."},
            {"name": "frequency", "value": "50/60 Hz", "normalized_value": "50/60 Hz", "unit": "Hz", "confidence": 0.99, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Operating frequency: 50/60 Hz."},
            {"name": "poles", "value": "3P", "normalized_value": "3", "unit": None, "confidence": 0.99, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Number of poles: 3P (3 poles)."},
            {"name": "power", "value": "7.5 kW", "normalized_value": "7.5 kW", "unit": "kW", "confidence": 0.96, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Operational power: 7.5 kW at 400 V."},
            {"name": "trip_class", "value": "Class 10", "normalized_value": "Class 10", "unit": None, "confidence": 0.95, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Trip class: Class 10 thermal overload."},
            {"name": "dimensions", "value": "45 x 97 x 97 mm", "normalized_value": "45x97x97 mm", "unit": "mm", "confidence": 0.97, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Dimensions (H x W x D): 97 mm x 45 mm x 97 mm."},
            {"name": "mounting", "value": "DIN rail 35 mm", "normalized_value": "DIN rail 35 mm", "unit": None, "confidence": 0.98, "status": "VERIFIED", "source": "Siemens SIRIUS Primary Datasheet (DEMO DATA)", "page": 4, "snippet": "Mounting: DIN rail 35 mm / Screw fixing."},
        ],
        "conflicts": [
            {
                "id": "conf_siemens_current",
                "attribute": "current",
                "values": ["10 A", "12 A"],
                "severity": "HIGH",
                "status": "OPEN",
            }
        ],
    },
    # ── Product 2: ABB MS132-16 (Verified - High Confidence) ──────────────────────
    {
        "id": "prod_demo_abb_ms132",
        "part_number": "MS132-16",
        "brand": "ABB",
        "category": "Manual Motor Starters",
        "description": "Compact manual motor starter with thermal and magnetic protection, 10 to 16 A setting range, 690 V AC",
        "overall_quality_score": 100.0,
        "status": "VERIFIED",
        "evidence_count": 2,
        "attributes": [
            {"name": "voltage", "value": "690 V AC", "normalized_value": "690 V", "unit": "V", "confidence": 0.99, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 2, "snippet": "Rated operational voltage: 690 V AC."},
            {"name": "current", "value": "16 A", "normalized_value": "16 A", "unit": "A", "confidence": 0.99, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 2, "snippet": "Rated operational current Ie: 16 A, Setting range 10.0 ... 16.0 A."},
            {"name": "frequency", "value": "50/60 Hz", "normalized_value": "50/60 Hz", "unit": "Hz", "confidence": 0.99, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 2, "snippet": "Rated frequency: 50 / 60 Hz."},
            {"name": "breaking_capacity", "value": "100 kA", "normalized_value": "100 kA", "unit": "kA", "confidence": 0.98, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 2, "snippet": "Rated ultimate short-circuit breaking capacity Icu at 400 V: 100 kA."},
            {"name": "poles", "value": "3P", "normalized_value": "3", "unit": None, "confidence": 0.99, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 2, "snippet": "Number of poles: 3."},
            {"name": "dimensions", "value": "45 x 90 x 86.75 mm", "normalized_value": "45x90x86.75 mm", "unit": "mm", "confidence": 0.97, "status": "VERIFIED", "source": "ABB Technical Data Sheet 1SBC100214C0202 (DEMO DATA)", "page": 3, "snippet": "Product Net Width: 45 mm, Height: 90 mm, Depth: 86.75 mm."},
        ],
        "conflicts": [],
    },
    # ── Product 3: Schneider Electric LC1D32BD (Verified - Published) ────────────
    {
        "id": "prod_demo_schneider_lc1d32",
        "part_number": "LC1D32BD",
        "brand": "Schneider Electric",
        "category": "TeSys D Contactors",
        "description": "TeSys Deca contactor, 3P(3 NO), AC-3/AC-3e, <= 440V 32A, 24V DC standard coil",
        "overall_quality_score": 96.0,
        "status": "PUBLISHED",
        "evidence_count": 3,
        "attributes": [
            {"name": "voltage", "value": "440 V AC", "normalized_value": "440 V", "unit": "V", "confidence": 0.98, "status": "VERIFIED", "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "page": 1, "snippet": "Rated operational voltage: Power circuit <= 690 V AC 25...400 Hz, <= 440 V AC-3."},
            {"name": "current", "value": "32 A", "normalized_value": "32 A", "unit": "A", "confidence": 0.99, "status": "VERIFIED", "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "page": 1, "snippet": "Rated operational current: 32 A (at <60 °C) at <= 440 V AC-3."},
            {"name": "coil_voltage", "value": "24 V DC", "normalized_value": "24 V", "unit": "V", "confidence": 0.99, "status": "VERIFIED", "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "page": 1, "snippet": "Control circuit voltage: 24 V DC standard with integral suppressor."},
            {"name": "power", "value": "15 kW", "normalized_value": "15 kW", "unit": "kW", "confidence": 0.97, "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "status": "VERIFIED", "page": 1, "snippet": "Motor power kW: 15 kW at 380...400 V AC 50/60 Hz."},
            {"name": "poles", "value": "3 NO", "normalized_value": "3", "unit": None, "confidence": 0.99, "status": "VERIFIED", "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "page": 1, "snippet": "Pole contact composition: 3 NO (Normally Open)."},
            {"name": "mounting", "value": "Plate / Rail", "normalized_value": "DIN rail 35 mm", "unit": None, "confidence": 0.95, "status": "VERIFIED", "source": "Schneider Electric TeSys Deca Datasheet (DEMO DATA)", "page": 2, "snippet": "Mounting support: Plate or 35 mm DIN rail."},
        ],
        "conflicts": [],
    },
    # ── Product 4: Eaton FAZ-C16/3 (Requires Review - Medium Confidence) ─────────
    {
        "id": "prod_demo_eaton_faz_c16",
        "part_number": "FAZ-C16/3",
        "brand": "Eaton",
        "category": "Miniature Circuit Breakers",
        "description": "xEffect Industrial Miniature Circuit Breaker, 3-pole, Curve C, 16 A, 15 kA breaking capacity",
        "overall_quality_score": 75.0,
        "status": "REQUIRES_REVIEW",
        "evidence_count": 2,
        "attributes": [
            {"name": "voltage", "value": "240/415 V AC", "normalized_value": "415 V", "unit": "V", "confidence": 0.95, "status": "VERIFIED", "source": "Eaton xEffect Technical Catalog (DEMO DATA)", "page": 5, "snippet": "Rated operational voltage: 240/415 V AC."},
            {"name": "current", "value": "16 A", "normalized_value": "16 A", "unit": "A", "confidence": 0.96, "status": "VERIFIED", "source": "Eaton xEffect Technical Catalog (DEMO DATA)", "page": 5, "snippet": "Rated current In: 16 A."},
            {"name": "curve", "value": "Characteristic C", "normalized_value": "C", "unit": None, "confidence": 0.72, "status": "REQUIRES_REVIEW", "source": "Distributor Spec Sheet (DEMO DATA)", "page": 1, "snippet": "Tripping characteristic C - medium inductive load protection."},
            {"name": "breaking_capacity", "value": "15 kA", "normalized_value": "15 kA", "unit": "kA", "confidence": 0.95, "status": "VERIFIED", "source": "Eaton xEffect Technical Catalog (DEMO DATA)", "page": 5, "snippet": "Rated switching capacity according to IEC/EN 60947-2: 15 kA."},
            {"name": "poles", "value": "3-pole", "normalized_value": "3", "unit": None, "confidence": 0.98, "status": "VERIFIED", "source": "Eaton xEffect Technical Catalog (DEMO DATA)", "page": 5, "snippet": "Number of poles: 3-pole."},
        ],
        "conflicts": [],
    },
    # ── Product 5: Phoenix Contact QUINT4-PS (Critical Conflict) ────────────────
    {
        "id": "prod_demo_phoenix_quint4",
        "part_number": "QUINT4-PS/1AC/24DC/20",
        "brand": "Phoenix Contact",
        "category": "Industrial Power Supplies",
        "description": "Primary-switched QUINT POWER power supply for DIN rail mounting with SFB Technology, 1-phase, 24 V DC / 20 A",
        "overall_quality_score": 62.5,
        "status": "CONFLICT",
        "evidence_count": 3,
        "attributes": [
            {"name": "input_voltage", "value": "100 - 240 V AC", "normalized_value": "240 V", "unit": "V", "confidence": 0.98, "status": "VERIFIED", "source": "Phoenix Contact Datasheet 1046805 (DEMO DATA)", "page": 1, "snippet": "Nominal input voltage range: 100 V AC ... 240 V AC."},
            {"name": "output_voltage", "value": "24 V DC", "normalized_value": "24 V", "unit": "V", "confidence": 0.50, "status": "CONFLICT", "source": "Phoenix Contact Datasheet 1046805 (DEMO DATA)", "page": 1, "snippet": "Nominal output voltage: 24 V DC (Setting range 24 V DC ... 29.5 V DC)."},
            {"name": "output_current", "value": "20 A", "normalized_value": "20 A", "unit": "A", "confidence": 0.98, "status": "VERIFIED", "source": "Phoenix Contact Datasheet 1046805 (DEMO DATA)", "page": 1, "snippet": "Nominal output current: 20 A (SFB Technology 120 A for 15 ms)."},
            {"name": "efficiency", "value": "94 %", "normalized_value": "94 %", "unit": "%", "confidence": 0.96, "status": "VERIFIED", "source": "Phoenix Contact Datasheet 1046805 (DEMO DATA)", "page": 2, "snippet": "Efficiency: > 94 % at 230 V AC."},
            {"name": "dimensions", "value": "70 x 130 x 125 mm", "normalized_value": "70x130x125 mm", "unit": "mm", "confidence": 0.97, "status": "VERIFIED", "source": "Phoenix Contact Datasheet 1046805 (DEMO DATA)", "page": 3, "snippet": "Dimensions: W / H / D: 70 mm / 130 mm / 125 mm."},
        ],
        "conflicts": [
            {
                "id": "conf_phoenix_voltage",
                "attribute": "output_voltage",
                "values": ["24 V DC", "48 V DC"],  # Intentional third-party discrepancy
                "severity": "CRITICAL",
                "status": "OPEN",
            }
        ],
    },
]


def seed_demo_products(db: Session) -> List[ProductTwin]:
    """
    Seeds the 5 realistic industrial demonstration products across diverse categories.
    Idempotent: removes previous demo records if present.
    """
    retriever = get_evidence_retriever()
    created_products: List[ProductTwin] = []

    # Clean existing demo records and cascade child tables cleanly
    demo_ids = [item["id"] for item in DEMO_PRODUCTS_DATA]
    try:
        existing = db.query(ProductTwin).filter(ProductTwin.id.in_(demo_ids)).all()
        for p in existing:
            db.delete(p)
        db.commit()
    except Exception:
        db.rollback()

    for item in DEMO_PRODUCTS_DATA:
        p_id = item["id"]

        # Realistic taxonomy mapping for demo products
        tax_map = {
            "Motor Protection Circuit Breakers": ("Electrical", "Motor Control", "Motor Protection"),
            "Manual Motor Starters": ("Electrical", "Motor Control", "Manual Motor Starters"),
            "TeSys D Contactors": ("Electrical", "Motor Control", "Contactors"),
            "Miniature Circuit Breakers": ("Electrical", "Power Distribution", "Miniature Circuit Breakers"),
            "Industrial Power Supplies": ("Electrical", "Power Supplies", "Industrial Power Supplies"),
        }
        dept, cls_n, fine = tax_map.get(item["category"], ("Electrical", "Industrial", item["category"]))
        classpath = f"{dept} > {cls_n} > {fine}"

        product = ProductTwin(
            id=p_id,
            part_number=item["part_number"],
            brand=item["brand"],
            manufacturer=item["brand"],
            description=item["description"],
            category=classpath,
            overall_quality_score=item["overall_quality_score"],
            status=item["status"],
            evidence_count=item["evidence_count"],
            taxonomy_dept=dept,
            taxonomy_class=cls_n,
            taxonomy_fine=fine,
            taxonomy_classpath=classpath,
            taxonomy_confidence=1.0,
            taxonomy_status="RESOLVED",
            desc_short=item["description"][:120],
            desc_long=item["description"],
            desc_retail=item["description"],
            desc_marketing=item["description"],
            desc_invoice=item["part_number"],
            desc_mobile=item["description"][:80],
            created_at=datetime.utcnow() - timedelta(days=2),
            updated_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.add(product)

        for attr_data in item["attributes"]:
            attr_id = f"attr_{uuid.uuid4().hex[:12]}"
            db_attr = ProductAttribute(
                id=attr_id,
                product_id=p_id,
                name=attr_data["name"],
                value=attr_data["value"],
                normalized_value=attr_data["normalized_value"],
                unit=attr_data.get("unit"),
                confidence=attr_data["confidence"],
                status=attr_data["status"],
            )

            # Create Evidence record
            ev_id = f"ev_{uuid.uuid4().hex[:12]}"
            db_ev = Evidence(
                id=ev_id,
                source_name=attr_data.get("source", "Datasheet (DEMO DATA)"),
                source_type="PDF",
                document_name=attr_data.get("source", "Datasheet (DEMO DATA)"),
                page_number=attr_data.get("page", 1),
                snippet=attr_data.get("snippet", "DEMO DATA synthetic snippet"),
                extracted_text=attr_data.get("snippet", "DEMO DATA synthetic snippet"),
                reliability_score=0.98,
            )
            db.add(db_ev)
            db_attr.evidence.append(db_ev)

            # Index in local vector retriever
            retriever.index_document(
                document_id=f"doc_{p_id}_{attr_data['name']}",
                document_name=attr_data.get("source", "Datasheet"),
                chunks=[{
                    "text": attr_data.get("snippet", ""),
                    "page_number": attr_data.get("page", 1),
                    "chunk_index": 0,
                }],
                product_id=p_id,
            )

            # Add Validation Result
            val_id = f"val_{uuid.uuid4().hex[:12]}"
            is_valid = attr_data["status"] != "CONFLICT"
            db_val = ValidationResult(
                id=val_id,
                attribute_id=attr_id,
                rule="bounds_and_format_check",
                passed=is_valid,
                message="Spec within certified tolerance" if is_valid else "Source discrepancy detected",
                severity="HIGH" if not is_valid else "INFO",
            )
            db.add(db_val)
            db_attr.validation_results.append(db_val)

            db.add(db_attr)

        # Add Conflicts
        for conf_data in item.get("conflicts", []):
            db_conf = Conflict(
                id=conf_data["id"],
                product_id=p_id,
                attribute=conf_data["attribute"],
                values=conf_data["values"],
                severity=conf_data["severity"],
                status=conf_data["status"],
            )
            db.add(db_conf)

        db.commit()
        db.refresh(product)
        created_products.append(product)

    return created_products
