"""
Content Guidelines Reference Interface.
"""
from typing import Dict, Any

class ContentRulesEngine:
    def __init__(self):
        # TODO: Load UNILOG_INTERNAL_CONTENT_GUIDELINES.docx logic
        pass

    def construct_description(self, description_type: str, facts: Dict[str, Any]) -> str:
        """
        Constructs a description (Invoice, Mobile, Short, Long, Retail, Marketing)
        based on canonical facts using formula and rules.
        """
        raise NotImplementedError("Reference data unavailable (UNILOG_INTERNAL_CONTENT_GUIDELINES.docx missing)")

    def validate_description(self, description_type: str, description_text: str) -> bool:
        """
        Validates character limit, casing, and required terms for a specific description type.
        """
        raise NotImplementedError("Reference data unavailable (UNILOG_INTERNAL_CONTENT_GUIDELINES.docx missing)")

_engine = None
def get_content_rules_engine() -> ContentRulesEngine:
    global _engine
    if _engine is None:
        _engine = ContentRulesEngine()
    return _engine
