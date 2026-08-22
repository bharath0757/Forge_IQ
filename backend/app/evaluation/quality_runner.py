"""
Comprehensive quality evaluation for the 1000-row Unihack dataset.
Reports all metrics separately with numerators/denominators.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.delivery.descriptions import DescriptionEngine
from app.delivery.exporter import export_to_csv
from app.delivery.mapper import map_product_to_delivery_record
from app.normalization.entity_resolution import EntityResolutionStatus, MatchType
from app.services.pipeline_runner import PipelineRunner
from app.taxonomy.engine import TaxonomyStatus

logging.basicConfig(level=logging.WARNING)

INPUT_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "Unihack_ Sample Dataset - Input.csv")
)
OUTPUT_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "evaluated_delivery.csv")
)
METRICS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "quality_metrics.json")
)

PLACEHOLDERS = {
    "-- unbranded --", "-- no unilog brand --", "-- no dib brand --",
    "-- no brand --", "-- no manufacturer --", "n/a", "na", "none",
    "unknown", "tbd", "not specified", "unspecified", "not available",
    "null", "-", "--", ".",
}

CATEGORY_KEYWORDS = {
    "abrasives": ["sanding belt", "cut-off disc", "cut off disc", "stikit", "abrasive", "disc/box", "hiolit", "abranet"],
    "appliances": ["dishwasher", "refrigerator", "range", "oven", "washer", "dryer"],
    "decking_building": ["decking", "deck board", "post trim", "composite", "pvc decking", "trex", "timbertech", "azek"],
    "electrical": ["dimmer", "box cover", "switch", "outlet", "breaker", "conduit", "wire", "leviton"],
    "lighting": ["wall light", "luminaire", "lamp", "fixture", "chandelier", "sconce", "led", "kichler", "lithonia"],
}


def clean_value(val: Optional[str]) -> str:
    if val is None:
        return ""
    v = val.strip()
    return "" if v.lower() in PLACEHOLDERS else v


def is_canonical_resolved(val: Optional[str]) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("", "none", "unknown", "unclassified", "n/a", "not available", "null"):
            return False
    return True


def classify_input_category(desc: str, brand: str) -> str:
    text = f"{desc} {brand}".lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "other"


def classify_manufacturer_failure(raw_mfg: str, resolved_status: str, match_type: str) -> str:
    if not raw_mfg or raw_mfg.strip() in ("", "-", "--"):
        return "missing manufacturer"
    if raw_mfg.strip().lower() in PLACEHOLDERS:
        return "placeholder manufacturer"
    if re.search(r'[^\w\s\(\)\-\.,&\']', raw_mfg):
        return "malformed manufacturer strings"
    if resolved_status == EntityResolutionStatus.REVIEW_REQUIRED.value:
        return "ambiguous manufacturer"
    if match_type == MatchType.UNRESOLVED.value and resolved_status != EntityResolutionStatus.RESOLVED.value:
        return "unknown manufacturer"
    return "parsing failure"


def classify_taxonomy(taxonomy_status: Optional[str], taxonomy_class: Optional[str]) -> str:
    status = (taxonomy_status or "").upper()
    cls = (taxonomy_class or "").strip()
    if status == TaxonomyStatus.RESOLVED.value and cls and cls.lower() != "unclassified":
        return "correct_confident"
    if status == TaxonomyStatus.HEURISTIC.value:
        return "heuristic"
    if status == TaxonomyStatus.LOW_CONFIDENCE.value:
        return "ambiguous"
    return "unresolved"


def score_description(desc: str, brand: str, mpn: str) -> Dict[str, Any]:
    issues = []
    if not desc or not desc.strip():
        issues.append("empty")
    lower = (desc or "").lower()
    for bad in ("none", "unclassified", "unknown"):
        if re.search(rf"\b{bad}\b", lower):
            issues.append(f"contains_{bad}")
    if brand and brand.lower() in lower and mpn and mpn.lower() in lower:
        if lower.count(brand.lower()) > 2:
            issues.append("duplicate_brand")
    return {"valid": len(issues) == 0, "issues": issues}


@dataclass
class QualityMetrics:
    processed: int = 0
    failed: int = 0
    manufacturer_resolved: int = 0
    brand_resolved: int = 0
    identity_resolved: int = 0
    taxonomy_resolved: int = 0
    total_attributes: int = 0
    total_evidence: int = 0
    total_confidence: float = 0.0
    desc_generated: int = 0
    desc_valid: int = 0
    review_required: int = 0
    unresolved: int = 0
    evidence_input_derived: int = 0
    evidence_local_doc: int = 0
    evidence_manufacturer: int = 0
    manufacturer_failures: Counter = field(default_factory=Counter)
    taxonomy_breakdown: Counter = field(default_factory=Counter)
    category_stats: Dict[str, Dict[str, Any]] = field(default_factory=lambda: defaultdict(dict))
    description_samples: List[Dict[str, Any]] = field(default_factory=list)
    product_type_detected: int = 0

    def to_summary(self) -> Dict[str, Any]:
        n = max(1, self.processed)
        return {
            "processed": self.processed,
            "failed": self.failed,
            "manufacturer_resolution": f"{self.manufacturer_resolved}/{self.processed}",
            "brand_resolution": f"{self.brand_resolved}/{self.processed}",
            "identity_resolution": f"{self.identity_resolved}/{self.processed}",
            "taxonomy_resolution": f"{self.taxonomy_resolved}/{self.processed}",
            "attributes_per_product": round(self.total_attributes / n, 2),
            "evidence_per_product": round(self.total_evidence / n, 2),
            "confidence_average": round(self.total_confidence / n, 2),
            "description_generation": f"{self.desc_generated}/{self.processed}",
            "description_valid_rate": f"{self.desc_valid}/{self.processed}",
            "review_required_rate": f"{self.review_required}/{self.processed}",
            "unresolved_rate": f"{self.unresolved}/{self.processed}",
            "evidence_input_derived": self.evidence_input_derived,
            "evidence_local_doc": self.evidence_local_doc,
            "evidence_manufacturer": self.evidence_manufacturer,
            "product_type_detected": f"{self.product_type_detected}/{self.processed}",
            "manufacturer_failures": dict(self.manufacturer_failures),
            "taxonomy_breakdown": dict(self.taxonomy_breakdown),
            "category_stats": dict(self.category_stats),
            "description_samples": self.description_samples[:25],
        }


def run_quality_evaluation(
    db: Session,
    runner: PipelineRunner,
    limit: Optional[int] = None,
    export_csv: bool = True,
) -> QualityMetrics:
    metrics = QualityMetrics()
    job_id = str(uuid.uuid4())
    delivery_records = []
    category_buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0, "mfg_resolved": 0, "brand_resolved": 0,
            "taxonomy_resolved": 0, "attributes": 0, "desc_valid": 0,
        }
    )

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break

            part_number = clean_value(row.get("Mfg_Part_Num", ""))
            desc = clean_value(row.get("Part_Desc", ""))
            brands = [
                clean_value(row.get("E1_Brand", "")),
                clean_value(row.get("Unilog_Brand", "")),
                clean_value(row.get("DIB_Brand", "")),
            ]
            brands = [b for b in brands if b]
            brand = brands[0] if brands else ""
            manufacturer = clean_value(row.get("Part_Manuf", ""))
            product_id = f"eval_{i}"
            input_cat = classify_input_category(desc, brand)

            try:
                product = runner.run_pipeline(
                    db=db,
                    job_id=job_id,
                    product_id=product_id,
                    part_number=part_number,
                    brand=brand,
                    manufacturer=manufacturer,
                    description=desc,
                    category="",
                )
                metrics.processed += 1

                mfg_status = getattr(product, "manufacturer_status", None) or ""
                brand_status = getattr(product, "brand_status", None) or ""
                mfg_resolved = mfg_status == EntityResolutionStatus.RESOLVED.value or (
                    getattr(product, "manufacturer_match_type", None) in (
                        MatchType.EXACT.value, MatchType.NORMALIZED.value, MatchType.FUZZY.value
                    ) and is_canonical_resolved(product.manufacturer)
                )
                brand_resolved = brand_status == EntityResolutionStatus.RESOLVED.value or (
                    getattr(product, "brand_match_type", None) in (
                        MatchType.EXACT.value, MatchType.NORMALIZED.value
                    ) and is_canonical_resolved(product.brand)
                )
                # Fallback for pre-enhancement pipeline: use attribute-based brand
                if not brand_resolved:
                    for attr in product.attributes:
                        if attr.name.lower() == "brand" and is_canonical_resolved(
                            attr.normalized_value or attr.value
                        ):
                            brand_resolved = True
                            break

                if not mfg_resolved and is_canonical_resolved(product.manufacturer):
                    # Legacy: title-cased unresolved still present
                    mfg_resolved = getattr(product, "manufacturer_match_type", None) in (
                        MatchType.EXACT.value, MatchType.NORMALIZED.value
                    )

                if mfg_resolved:
                    metrics.manufacturer_resolved += 1
                else:
                    fail_type = classify_manufacturer_failure(
                        manufacturer,
                        mfg_status or EntityResolutionStatus.UNRESOLVED.value,
                        getattr(product, "manufacturer_match_type", MatchType.UNRESOLVED.value),
                    )
                    metrics.manufacturer_failures[fail_type] += 1

                if brand_resolved:
                    metrics.brand_resolved += 1
                if mfg_resolved and brand_resolved:
                    metrics.identity_resolved += 1

                tax_status = getattr(product, "taxonomy_status", None) or ""
                tax_class = product.taxonomy_class or product.category or ""
                tax_resolved = (
                    tax_status in (TaxonomyStatus.RESOLVED.value, TaxonomyStatus.HEURISTIC.value)
                    and is_canonical_resolved(tax_class)
                    and tax_class.lower() != "unclassified"
                )
                if tax_resolved:
                    metrics.taxonomy_resolved += 1
                metrics.taxonomy_breakdown[classify_taxonomy(tax_status, tax_class)] += 1

                attr_count = len(product.attributes)
                metrics.total_attributes += attr_count

                for attr in product.attributes:
                    if attr.name.lower() in ("product_type", "candidate_type"):
                        metrics.product_type_detected += 1
                        break

                ev_input = ev_doc = ev_mfg = 0
                for attr in product.attributes:
                    for ev in attr.evidence:
                        st = (ev.source_type or "").upper()
                        sn = (ev.source_name or "").lower()
                        if st == "INPUT_DESCRIPTION" or "description" in sn:
                            ev_input += 1
                        elif st in ("PDF", "DOCUMENT"):
                            ev_doc += 1
                        elif "manufacturer" in sn:
                            ev_mfg += 1
                        else:
                            ev_input += 1
                metrics.evidence_input_derived += ev_input
                metrics.evidence_local_doc += ev_doc
                metrics.evidence_manufacturer += ev_mfg
                metrics.total_evidence += product.evidence_count

                conf = product.overall_quality_score or 0.0
                metrics.total_confidence += conf

                desc_engine = DescriptionEngine(product)
                short_desc = desc_engine.build_short_description()
                desc_quality = score_description(short_desc, product.brand or "", product.part_number or "")
                if is_canonical_resolved(short_desc):
                    metrics.desc_generated += 1
                if desc_quality["valid"]:
                    metrics.desc_valid += 1

                if len(metrics.description_samples) < 25:
                    metrics.description_samples.append({
                        "mpn": product.part_number,
                        "brand": product.brand,
                        "manufacturer": product.manufacturer,
                        "short_desc": short_desc,
                        "issues": desc_quality["issues"],
                        "attributes": [a.name for a in product.attributes],
                    })

                if product.status == "REQUIRES_REVIEW":
                    metrics.review_required += 1
                if product.status == "UNRESOLVED":
                    metrics.unresolved += 1

                bucket = category_buckets[input_cat]
                bucket["rows"] += 1
                if mfg_resolved:
                    bucket["mfg_resolved"] += 1
                if brand_resolved:
                    bucket["brand_resolved"] += 1
                if tax_resolved:
                    bucket["taxonomy_resolved"] += 1
                bucket["attributes"] += attr_count
                if desc_quality["valid"]:
                    bucket["desc_valid"] += 1

                if export_csv:
                    delivery_records.append(map_product_to_delivery_record(product))

            except Exception:
                metrics.failed += 1

            if i % 100 == 0 and i > 0:
                print(f"Processed {i} rows...", flush=True)

    for cat, bucket in category_buckets.items():
        rows = max(1, bucket["rows"])
        metrics.category_stats[cat] = {
            "rows": bucket["rows"],
            "manufacturer_resolution": f"{bucket['mfg_resolved']}/{bucket['rows']}",
            "brand_resolution": f"{bucket['brand_resolved']}/{bucket['rows']}",
            "taxonomy_resolution": f"{bucket['taxonomy_resolved']}/{bucket['rows']}",
            "attributes_per_product": round(bucket["attributes"] / rows, 2),
            "description_valid_rate": f"{bucket['desc_valid']}/{bucket['rows']}",
        }

    if export_csv and delivery_records:
        csv_str = export_to_csv(delivery_records)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
            out.write(csv_str)

    return metrics


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run ForgeIQ quality evaluation")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--label", type=str, default="evaluation")
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    runner = PipelineRunner()
    metrics = run_quality_evaluation(db, runner, limit=args.limit, export_csv=not args.no_export)
    summary = metrics.to_summary()
    summary["label"] = args.label

    print(f"\nFORGEIQ QUALITY EVALUATION — {args.label.upper()}")
    for key, val in summary.items():
        if key not in ("manufacturer_failures", "taxonomy_breakdown", "category_stats", "description_samples"):
            print(f"{key}: {val}")
    print("\nMANUFACTURER FAILURES:")
    for k, v in summary["manufacturer_failures"].items():
        print(f"  {k}: {v}")
    print("\nTAXONOMY BREAKDOWN:")
    for k, v in summary["taxonomy_breakdown"].items():
        print(f"  {k}: {v}")

    existing = {}
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, "r", encoding="utf-8") as mf:
            existing = json.load(mf)
    existing[args.label] = summary
    with open(METRICS_FILE, "w", encoding="utf-8") as mf:
        json.dump(existing, mf, indent=2)
    print(f"\nMetrics saved to {METRICS_FILE}")


if __name__ == "__main__":
    main()
