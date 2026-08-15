import logging
from typing import List, Dict, Any, Optional
from app.validation.models import (
    ValidationResultItem,
    ValidationStatus,
    ValidationSeverity,
    ValidationReport,
    CrossSourceComparisonResult,
)
from app.validation.rules import (
    BaseValidationRule,
    RequiredAttributeRule,
    NumericFormatRule,
    UnitConsistencyRule,
    ImpossibleValueRule,
    DuplicateAttributeRule,
)
from app.validation.cross_source import CrossSourceValidator
from app.validation.ai_validator import AIAssistedValidator

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    ForgeIQ Multi-Tier Validation Engine.
    Combines:
    1. Deterministic Rules
    2. Cross-Source Comparison
    3. AI-Assisted Validation

    CRITICAL INVARIANT:
    Validation NEVER silently modifies an attribute. It only produces validation results.
    """

    def __init__(
        self,
        rules: Optional[List[BaseValidationRule]] = None,
        cross_source_validator: Optional[CrossSourceValidator] = None,
        ai_validator: Optional[AIAssistedValidator] = None,
    ):
        self.rules = rules if rules is not None else [
            RequiredAttributeRule(),
            NumericFormatRule(),
            UnitConsistencyRule(),
            ImpossibleValueRule(),
            DuplicateAttributeRule(),
        ]
        self.cross_source_validator = cross_source_validator or CrossSourceValidator()
        self.ai_validator = ai_validator or AIAssistedValidator()

    def validate_product(
        self,
        product_id: str,
        attributes: Dict[str, Any],
        multi_source_claims: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        evidence_text: Optional[str] = None,
        run_ai_validation: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """
        Execute full validation suite across all configured validation tiers.
        """
        all_results: List[ValidationResultItem] = []
        conflicts: List[CrossSourceComparisonResult] = []

        # 1. Run Deterministic Rules
        for rule in self.rules:
            try:
                rule_results = rule.validate(attributes=attributes, context=context)
                all_results.extend(rule_results)
            except Exception as e:
                logger.error(f"Error executing validation rule {rule.name}: {e}")
                all_results.append(
                    ValidationResultItem(
                        rule=rule.name,
                        passed=False,
                        status=ValidationStatus.FAILED,
                        severity=ValidationSeverity.HIGH,
                        message=f"Execution error in rule {rule.name}: {str(e)}"
                    )
                )

        # 2. Run Cross-Source Comparison (if multi-source claims exist)
        if multi_source_claims:
            for attr_name, claims in multi_source_claims.items():
                cmp_res = self.cross_source_validator.compare_sources(attr_name, claims)
                if cmp_res.is_conflict:
                    conflicts.append(cmp_res)

                sources = [c.get("source_name") for c in cmp_res.sources if c.get("source_name")]
                all_results.append(
                    ValidationResultItem(
                        rule="CrossSourceConsistencyCheck",
                        attribute_name=attr_name,
                        passed=not cmp_res.is_conflict,
                        status=cmp_res.status,
                        severity=cmp_res.severity,
                        message=cmp_res.message,
                        evidence_ids=cmp_res.evidence_ids,
                        sources=sources,
                        details={
                            "is_conflict": cmp_res.is_conflict,
                            "conflicting_values": cmp_res.conflicting_values
                        }
                    )
                )

        # 3. Run AI-Assisted Validation (if requested and evidence text provided)
        if run_ai_validation and evidence_text:
            ai_results = self.ai_validator.validate_semantic_attributes(attributes, evidence_text)
            all_results.extend(ai_results)

        # Aggregate report statistics
        passed_count = sum(1 for r in all_results if r.passed)
        failed_count = sum(1 for r in all_results if not r.passed and r.status != ValidationStatus.CONFLICT)
        conflict_count = len(conflicts)

        # Overall status
        if conflict_count > 0 or any(r.severity in (ValidationSeverity.HIGH, ValidationSeverity.CRITICAL) and not r.passed for r in all_results):
            overall_status = "REQUIRES_REVIEW"
            overall_passed = False
        elif failed_count > 0:
            overall_status = "FAILED"
            overall_passed = False
        else:
            overall_status = "VERIFIED"
            overall_passed = True

        return ValidationReport(
            product_id=product_id,
            passed=overall_passed,
            status=overall_status,
            total_rules_checked=len(all_results),
            passed_count=passed_count,
            failed_count=failed_count,
            conflict_count=conflict_count,
            results=all_results,
            conflicts=conflicts,
        )


_default_validation_engine: Optional[ValidationEngine] = None


def get_validation_engine() -> ValidationEngine:
    global _default_validation_engine
    if _default_validation_engine is None:
        _default_validation_engine = ValidationEngine()
    return _default_validation_engine
