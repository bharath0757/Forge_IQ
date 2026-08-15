import logging
from typing import List, Dict, Any, Optional
from app.validation.models import (
    ValidationResultItem,
    ValidationStatus,
    ValidationSeverity,
    CrossSourceComparisonResult,
)
from app.normalization.service import get_normalization_service

logger = logging.getLogger(__name__)


class CrossSourceValidator:
    """
    Compares attribute values extracted or supported across multiple documents and sources.
    Identifies reinforced matches vs conflicting source claims.
    """

    def __init__(self):
        self.normalizer = get_normalization_service()

    def compare_sources(
        self,
        attribute_name: str,
        source_claims: List[Dict[str, Any]]
    ) -> CrossSourceComparisonResult:
        """
        Compare claims from multiple sources for a single attribute.

        Args:
            attribute_name: Name of the attribute (e.g., "current", "voltage").
            source_claims: List of dicts, each containing:
                - "source_name": str (e.g., "Manufacturer Datasheet.pdf")
                - "value": Any (e.g., "10 A", "12 A")
                - "evidence_id": Optional[str]

        Returns:
            CrossSourceComparisonResult with match/conflict details.
        """
        if not source_claims:
            return CrossSourceComparisonResult(
                attribute_name=attribute_name,
                is_conflict=False,
                status=ValidationStatus.PASSED,
                severity=ValidationSeverity.LOW,
                sources=[],
                conflicting_values=[],
                message=f"No multi-source claims provided for '{attribute_name}'."
            )

        if len(source_claims) == 1:
            claim = source_claims[0]
            return CrossSourceComparisonResult(
                attribute_name=attribute_name,
                is_conflict=False,
                status=ValidationStatus.PASSED,
                severity=ValidationSeverity.LOW,
                sources=source_claims,
                conflicting_values=[],
                message=f"Single source '{claim.get('source_name', 'Doc')}' supports '{attribute_name}' with value '{claim.get('value')}'.",
                evidence_ids=[claim.get("evidence_id")] if claim.get("evidence_id") else []
            )

        # Normalize all values to prevent false conflicts due to formatting differences
        normalized_claims = []
        for c in source_claims:
            raw_val = c.get("value")
            norm_res = self.normalizer.normalize_attribute(attribute_name, raw_val)
            norm_val = norm_res.normalized_value or str(raw_val).strip()
            normalized_claims.append({
                "source_name": c.get("source_name", "Unknown Source"),
                "raw_value": raw_val,
                "normalized_value": norm_val,
                "evidence_id": c.get("evidence_id"),
            })

        # Group distinct canonical values
        distinct_values = {}
        all_evidence_ids = []
        for item in normalized_claims:
            n_val = item["normalized_value"]
            distinct_values.setdefault(n_val, []).append(item)
            if item.get("evidence_id"):
                all_evidence_ids.append(item["evidence_id"])

        if len(distinct_values) == 1:
            # All sources agree!
            matched_val = list(distinct_values.keys())[0]
            sources_list = [c["source_name"] for c in normalized_claims]
            return CrossSourceComparisonResult(
                attribute_name=attribute_name,
                is_conflict=False,
                status=ValidationStatus.PASSED,
                severity=ValidationSeverity.LOW,
                sources=normalized_claims,
                conflicting_values=[],
                message=f"Value '{matched_val}' consistently verified across {len(sources_list)} sources ({', '.join(sources_list)}).",
                evidence_ids=all_evidence_ids
            )
        else:
            # Sources disagree! Conflict detected
            conflicting_list = list(distinct_values.keys())
            breakdown_parts = []
            for val, claims in distinct_values.items():
                src_names = ", ".join(c["source_name"] for c in claims)
                breakdown_parts.append(f"'{val}' ({src_names})")

            breakdown_str = " vs ".join(breakdown_parts)
            msg = f"Conflicting values detected for '{attribute_name}' across sources: {breakdown_str}."

            return CrossSourceComparisonResult(
                attribute_name=attribute_name,
                is_conflict=True,
                status=ValidationStatus.CONFLICT,
                severity=ValidationSeverity.HIGH,
                sources=normalized_claims,
                conflicting_values=conflicting_list,
                message=msg,
                evidence_ids=all_evidence_ids
            )

    def validate_all(
        self,
        multi_source_attributes: Dict[str, List[Dict[str, Any]]]
    ) -> List[ValidationResultItem]:
        """
        Run cross-source validation across all multi-source attribute mappings.
        """
        results = []
        for attr_name, claims in multi_source_attributes.items():
            cmp_result = self.compare_sources(attr_name, claims)
            sources = [c.get("source_name") for c in cmp_result.sources if c.get("source_name")]

            results.append(
                ValidationResultItem(
                    rule="CrossSourceConsistencyCheck",
                    attribute_name=attr_name,
                    passed=not cmp_result.is_conflict,
                    status=cmp_result.status,
                    severity=cmp_result.severity,
                    message=cmp_result.message,
                    evidence_ids=cmp_result.evidence_ids,
                    sources=sources,
                    details={
                        "is_conflict": cmp_result.is_conflict,
                        "conflicting_values": cmp_result.conflicting_values,
                    }
                )
            )
        return results
