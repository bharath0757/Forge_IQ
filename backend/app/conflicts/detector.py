import uuid
import logging
from typing import List, Dict, Any, Optional
from app.conflicts.models import ConflictDetail, ConflictStatus
from app.schemas.product import SeverityLevel
from app.normalization.service import get_normalization_service

logger = logging.getLogger(__name__)


class ConflictDetector:
    """
    Detects true technical specification conflicts across multiple data sources.
    Uses canonical normalization to prevent false positives from formatting or unit differences.
    """

    def __init__(self):
        self.normalizer = get_normalization_service()

    def check_attribute_conflict(
        self,
        attribute_name: str,
        claims: List[Dict[str, Any]],
        product_id: Optional[str] = None,
    ) -> Optional[ConflictDetail]:
        """
        Compare claims across sources for a single attribute.
        Returns a ConflictDetail if a true discrepancy exists, or None if all sources agree.
        """
        if not claims or len(claims) <= 1:
            return None

        # Normalize all claims to canonical values
        normalized_map: Dict[str, List[Dict[str, Any]]] = {}
        all_evidence_ids = []
        all_sources = []

        for claim in claims:
            raw_val = claim.get("value")
            src_name = claim.get("source_name", "Unknown Source")
            eid = claim.get("evidence_id")

            if raw_val is None or str(raw_val).strip() == "" or str(raw_val).upper() == "UNKNOWN":
                continue

            all_sources.append(src_name)
            if eid:
                all_evidence_ids.append(eid)

            norm_res = self.normalizer.normalize_attribute(attribute_name, raw_val)
            # Use canonical normalized_value if available, else stripped raw string
            canonical_key = str(norm_res.normalized_value or str(raw_val).strip())

            normalized_map.setdefault(canonical_key, []).append({
                "source_name": src_name,
                "raw_value": raw_val,
                "normalized_value": canonical_key,
                "evidence_id": eid,
            })

        # If 0 or 1 distinct canonical values exist, there is NO conflict!
        if len(normalized_map) <= 1:
            return None

        # True conflict: multiple distinct canonical values found across sources!
        distinct_raw_values = []
        for canonical_k, claim_list in normalized_map.items():
            distinct_raw_values.append(claim_list[0]["raw_value"])

        conflict_id = f"conf_{uuid.uuid4().hex[:12]}"
        
        # Severity calculation based on attribute importance
        sev = SeverityLevel.HIGH
        if attribute_name.lower() in ("voltage", "current", "poles"):
            sev = SeverityLevel.HIGH
        else:
            sev = SeverityLevel.MEDIUM

        return ConflictDetail(
            id=conflict_id,
            product_id=product_id,
            attribute=attribute_name,
            values=distinct_raw_values,
            sources=list(set(all_sources)),
            severity=sev,
            status=ConflictStatus.OPEN,
            evidence_ids=list(set(all_evidence_ids)),
        )

    def detect_all_conflicts(
        self,
        multi_source_claims: Dict[str, List[Dict[str, Any]]],
        product_id: Optional[str] = None,
    ) -> List[ConflictDetail]:
        """
        Detect conflicts across all attributes for a product.
        """
        conflicts = []
        for attr_name, claims in multi_source_claims.items():
            conflict = self.check_attribute_conflict(attr_name, claims, product_id)
            if conflict:
                conflicts.append(conflict)
        return conflicts


_default_conflict_detector: Optional[ConflictDetector] = None


def get_conflict_detector() -> ConflictDetector:
    global _default_conflict_detector
    if _default_conflict_detector is None:
        _default_conflict_detector = ConflictDetector()
    return _default_conflict_detector
