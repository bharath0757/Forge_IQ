import logging
from typing import List, Dict, Any, Optional
from app.scoring.models import (
    ConfidenceBand,
    ConfidenceScoreBreakdown,
    ProductConfidenceSummary,
)

logger = logging.getLogger(__name__)


class ConfidenceScoringEngine:
    """
    Deterministic confidence scoring engine for ForgeIQ.
    Calculates multi-signal confidence for technical attributes without blindly trusting LLM numbers.
    """

    SOURCE_WEIGHTS = {
        "datasheet": 1.00,
        "manufacturer": 1.00,
        "spec": 0.98,
        "catalog": 0.95,
        "manual": 0.90,
        "website": 0.80,
        "distributor": 0.80,
        "general": 0.75,
    }

    def calculate_attribute_confidence(
        self,
        attribute_name: str,
        attribute_value: Any,
        status: str,
        evidence_list: Optional[List[Any]] = None,
        agreeing_sources_count: int = 1,
        validation_results: Optional[List[Any]] = None,
        has_open_conflict: bool = False,
        is_ambiguous_normalization: bool = False,
    ) -> ConfidenceScoreBreakdown:
        """
        Calculate deterministic confidence score for a single product attribute.
        """
        if attribute_value is None or str(status).upper() == "UNKNOWN":
            return ConfidenceScoreBreakdown(
                attribute_name=attribute_name,
                confidence_score=0.0,
                confidence_band=ConfidenceBand.LOW,
                source_reliability=0.0,
                evidence_strength=0.0,
                agreement_score=0.0,
                extraction_quality=0.0,
                validation_factor=1.0,
                conflict_factor=1.0,
                is_blocked_by_conflict=False,
                explanation=f"Attribute '{attribute_name}' is missing or marked UNKNOWN.",
            )

        evidence_list = evidence_list or []

        # 1. Calculate Source Reliability
        source_rel = self._calculate_source_reliability(evidence_list)

        # 2. Calculate Evidence Strength (based on retrieval scores and snippet presence)
        evidence_str = self._calculate_evidence_strength(evidence_list)

        # 3. Calculate Agreement Score
        agreement = self._calculate_agreement_score(agreeing_sources_count, len(evidence_list))

        # 4. Calculate Extraction Quality
        extraction_q = 0.80 if is_ambiguous_normalization else (1.00 if evidence_list else 0.50)

        # 5. Calculate Validation Factor
        val_factor = self._calculate_validation_factor(validation_results)

        # 6. Calculate Conflict Factor
        conflict_factor = 0.50 if has_open_conflict else 1.00

        # Compute raw product
        raw_product = (
            source_rel
            * evidence_str
            * agreement
            * extraction_q
            * val_factor
            * conflict_factor
        )

        final_score = round(min(100.0, max(0.0, raw_product * 100.0)), 1)

        # Determine confidence band
        if final_score >= 90.0:
            band = ConfidenceBand.HIGH
        elif final_score >= 70.0:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        # Critical conflict blocks automatic approval regardless of score
        is_blocked = has_open_conflict or (val_factor <= 0.2)

        explanation = (
            f"Score: {final_score}% ({band.value}) | "
            f"Source Rel: {source_rel:.2f}, Evidence Str: {evidence_str:.2f}, "
            f"Agreement: {agreement:.2f}, Extraction: {extraction_q:.2f}, "
            f"Validation: {val_factor:.2f}, Conflict: {conflict_factor:.2f}"
        )
        if is_blocked:
            explanation += " [BLOCKED: Open conflict or critical validation failure prevents auto-approval]"

        return ConfidenceScoreBreakdown(
            attribute_name=attribute_name,
            confidence_score=final_score,
            confidence_band=band,
            source_reliability=round(source_rel, 2),
            evidence_strength=round(evidence_str, 2),
            agreement_score=round(agreement, 2),
            extraction_quality=round(extraction_q, 2),
            validation_factor=round(val_factor, 2),
            conflict_factor=round(conflict_factor, 2),
            is_blocked_by_conflict=is_blocked,
            explanation=explanation,
            details={
                "evidence_count": len(evidence_list),
                "agreeing_sources": agreeing_sources_count,
            }
        )

    def calculate_product_confidence(
        self,
        product_id: str,
        attribute_scores: List[ConfidenceScoreBreakdown]
    ) -> ProductConfidenceSummary:
        """
        Aggregate confidence score breakdowns across all product attributes.
        """
        if not attribute_scores:
            return ProductConfidenceSummary(
                product_id=product_id,
                overall_confidence_score=0.0,
                overall_confidence_band=ConfidenceBand.LOW,
                high_confidence_attributes=0,
                medium_confidence_attributes=0,
                low_confidence_attributes=0,
                has_blocking_conflicts=False,
                attributes=[]
            )

        total_score = sum(a.confidence_score for a in attribute_scores)
        overall_avg = round(total_score / len(attribute_scores), 1)

        high_count = sum(1 for a in attribute_scores if a.confidence_band == ConfidenceBand.HIGH)
        med_count = sum(1 for a in attribute_scores if a.confidence_band == ConfidenceBand.MEDIUM)
        low_count = sum(1 for a in attribute_scores if a.confidence_band == ConfidenceBand.LOW)
        has_blocking = any(a.is_blocked_by_conflict for a in attribute_scores)

        if overall_avg >= 90.0 and not has_blocking:
            overall_band = ConfidenceBand.HIGH
        elif overall_avg >= 70.0:
            overall_band = ConfidenceBand.MEDIUM
        else:
            overall_band = ConfidenceBand.LOW

        return ProductConfidenceSummary(
            product_id=product_id,
            overall_confidence_score=overall_avg,
            overall_confidence_band=overall_band,
            high_confidence_attributes=high_count,
            medium_confidence_attributes=med_count,
            low_confidence_attributes=low_count,
            has_blocking_conflicts=has_blocking,
            attributes=attribute_scores
        )

    def _calculate_source_reliability(self, evidence_list: List[Any]) -> float:
        if not evidence_list:
            return 0.75

        scores = []
        for ev in evidence_list:
            name = (
                getattr(ev, "document_name", "") or
                getattr(ev, "source_name", "") or
                (ev.get("document_name") if isinstance(ev, dict) else "") or
                ""
            ).lower()

            matched = False
            for k, weight in self.SOURCE_WEIGHTS.items():
                if k in name:
                    scores.append(weight)
                    matched = True
                    break
            if not matched:
                scores.append(0.85)

        return max(scores) if scores else 0.85

    def _calculate_evidence_strength(self, evidence_list: List[Any]) -> float:
        if not evidence_list:
            return 0.50

        sim_scores = []
        for ev in evidence_list:
            score = getattr(ev, "reliability_score", None) or getattr(ev, "similarity_score", None)
            if score is None and isinstance(ev, dict):
                score = ev.get("reliability_score") or ev.get("similarity_score")
            
            if score is not None:
                sim_scores.append(float(score))

        if sim_scores:
            avg_sim = sum(sim_scores) / len(sim_scores)
            if avg_sim >= 0.80:
                return min(1.00, round(avg_sim, 2))
            rescaled = 0.80 + (avg_sim * 0.25)
            return max(0.80, min(1.00, round(rescaled, 2)))
        return 0.95

    def _calculate_agreement_score(self, agreeing_sources: int, evidence_count: int) -> float:
        if agreeing_sources >= 3:
            return 1.15
        elif agreeing_sources >= 2:
            return 1.05
        elif agreeing_sources == 1 or evidence_count >= 1:
            return 1.00
        return 0.80

    def _calculate_validation_factor(self, validation_results: Optional[List[Any]]) -> float:
        if not validation_results:
            return 1.00

        has_critical = False
        has_failed = False
        has_warning = False

        for vr in validation_results:
            passed = getattr(vr, "passed", True) if hasattr(vr, "passed") else vr.get("passed", True)
            severity = getattr(vr, "severity", "") if hasattr(vr, "severity") else vr.get("severity", "")
            sev_str = severity.value if hasattr(severity, "value") else str(severity).upper()

            if not passed:
                if sev_str == "CRITICAL":
                    has_critical = True
                elif sev_str == "HIGH":
                    has_failed = True
                else:
                    has_warning = True

        if has_critical:
            return 0.10
        elif has_failed:
            return 0.50
        elif has_warning:
            return 0.85
        return 1.00


_default_confidence_engine: Optional[ConfidenceScoringEngine] = None


def get_confidence_scoring_engine() -> ConfidenceScoringEngine:
    global _default_confidence_engine
    if _default_confidence_engine is None:
        _default_confidence_engine = ConfidenceScoringEngine()
    return _default_confidence_engine
