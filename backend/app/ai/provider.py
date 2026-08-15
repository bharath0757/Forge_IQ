import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional
from pydantic import BaseModel, ValidationError

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.ai.prompts import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

class AIProvider(ABC):
    @abstractmethod
    def extract_product_attributes(self, product_info: str, evidence: str, schema: Type[BaseModel]) -> BaseModel:
        """Extracts attributes into a strict structured JSON."""
        pass

    @abstractmethod
    def classify_product(self, product_info: str) -> str:
        """Classifies the product into a specific category."""
        pass

    @abstractmethod
    def validate_attribute(self, attribute_name: str, attribute_value: Any, evidence: str) -> bool:
        """Validates if the extracted attribute is supported by the evidence."""
        pass


class LangchainOpenAIProvider(AIProvider):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0, api_key: Optional[str] = None):
        import os
        from app.config import settings
        resolved_key = api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or "mock-key"
        self.llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=resolved_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ValidationError, ValueError)),
        reraise=True
    )
    def extract_product_attributes(self, product_info: str, evidence: str, schema: Type[BaseModel]) -> BaseModel:
        try:
            # Bind the LLM to output the exact schema
            structured_llm = self.llm.with_structured_output(schema, strict=True)
            
            # Format the prompt
            messages = EXTRACTION_PROMPT.format_messages(
                product_info=product_info,
                evidence_text=evidence
            )
            
            # Invoke the model
            result = structured_llm.invoke(messages)
            return result
        except ValidationError as e:
            logger.error(f"Validation Error during extraction: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during extraction: {e}")
            # Reraising the exception to trigger the retry logic if appropriate
            # We only retry on ValidationError/ValueError based on the decorator
            raise

    def classify_product(self, product_info: str) -> str:
        # Implementation for classification
        # Placeholder for this demo
        return "Motor Protection Circuit Breaker"

    def validate_attribute(self, attribute_name: str, attribute_value: Any, evidence: str) -> bool:
        # Placeholder logic for verifying specific attributes
        return True


class DeterministicAIProvider(AIProvider):
    """
    Deterministic rule-based AI provider for offline demo mode and fallback execution.
    Extracts structured technical attributes from evidence chunks without external network calls.
    """

    def extract_product_attributes(self, product_info: str, evidence: str, schema: Type[BaseModel]) -> BaseModel:
        from app.normalization.service import get_normalization_service
        normalizer = get_normalization_service()

        extracted_attrs = []
        ev_lower = evidence.lower()

        # Voltage
        if "400 v" in ev_lower or "400v" in ev_lower or "400 volt" in ev_lower:
            norm = normalizer.normalize_attribute("voltage", "400 V AC")
            extracted_attrs.append({"name": "voltage", "value": "400 V AC", "normalized_value": norm.normalized_value, "unit": norm.unit, "confidence": 0.98, "status": "VERIFIED"})

        # Current
        if "12 a" in ev_lower:
            norm = normalizer.normalize_attribute("current", "12 A")
            extracted_attrs.append({"name": "current", "value": "12 A", "normalized_value": norm.normalized_value, "unit": norm.unit, "confidence": 0.65, "status": "CONFLICT"})
        elif "10 a" in ev_lower or "10 amp" in ev_lower:
            norm = normalizer.normalize_attribute("current", "10 A")
            extracted_attrs.append({"name": "current", "value": "10 A", "normalized_value": norm.normalized_value, "unit": norm.unit, "confidence": 0.98, "status": "VERIFIED"})

        # Frequency
        if "50/60 hz" in ev_lower or "50 - 60 hz" in ev_lower or "50 - 60 hertz" in ev_lower:
            norm = normalizer.normalize_attribute("frequency", "50/60 Hz")
            extracted_attrs.append({"name": "frequency", "value": "50/60 Hz", "normalized_value": norm.normalized_value, "unit": norm.unit, "confidence": 0.99, "status": "VERIFIED"})

        # Build instance of schema
        try:
            return schema(attributes=extracted_attrs, raw_extraction={"source": "deterministic_rules"})
        except Exception:
            return schema.model_construct(attributes=extracted_attrs)

    def classify_product(self, product_info: str) -> str:
        info = product_info.lower()
        if "motor" in info or "circuit breaker" in info or "3rv" in info:
            return "Motor Protection Circuit Breakers"
        elif "contactor" in info or "lc1d" in info:
            return "Contactors"
        elif "power supply" in info or "quint" in info:
            return "Industrial Power Supplies"
        return "Industrial Automation"

    def validate_attribute(self, attribute_name: str, attribute_value: Any, evidence: str) -> bool:
        return bool(str(attribute_value).lower() in evidence.lower())
