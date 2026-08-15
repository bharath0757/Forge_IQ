import logging
from typing import List, Dict, Any, Optional
from app.validation.models import ValidationResultItem, ValidationStatus, ValidationSeverity
from app.ai.provider import AIProvider, LangchainOpenAIProvider

logger = logging.getLogger(__name__)


class AIAssistedValidator:
    """
    Performs AI-assisted validation for complex, qualitative, or semi-structured attributes
    (such as application suitability, standard conformity, or textual claims).
    """

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider or LangchainOpenAIProvider()

    def validate_semantic_attributes(
        self,
        attributes: Dict[str, Any],
        evidence_text: str
    ) -> List[ValidationResultItem]:
        """
        Validates qualitative attributes against evidence using the AI provider.
        """
        results = []
        semantic_keys = ["application", "standards", "material"]

        for key in semantic_keys:
            if key not in attributes:
                continue

            attr_data = attributes[key]
            val = getattr(attr_data, "value", None) if hasattr(attr_data, "value") else attr_data.get("value")
            evidence_ids = getattr(attr_data, "evidence_ids", []) if hasattr(attr_data, "evidence_ids") else attr_data.get("evidence_ids", [])

            if not val or str(val).upper() == "UNKNOWN":
                continue

            try:
                is_valid = self.ai_provider.validate_attribute(
                    attribute_name=key,
                    attribute_value=val,
                    evidence=evidence_text
                )

                if is_valid:
                    results.append(
                        ValidationResultItem(
                            rule="AIAssistedSemanticValidation",
                            attribute_name=key,
                            passed=True,
                            status=ValidationStatus.PASSED,
                            severity=ValidationSeverity.LOW,
                            message=f"AI verified that '{key}' specification '{val}' is grounded in evidence.",
                            evidence_ids=evidence_ids
                        )
                    )
                else:
                    results.append(
                        ValidationResultItem(
                            rule="AIAssistedSemanticValidation",
                            attribute_name=key,
                            passed=False,
                            status=ValidationStatus.WARNING,
                            severity=ValidationSeverity.MEDIUM,
                            message=f"AI could not confirm evidence support for '{key}' value '{val}'.",
                            evidence_ids=evidence_ids
                        )
                    )
            except Exception as e:
                logger.warning(f"AI assisted validation error on '{key}': {e}")

        return results
