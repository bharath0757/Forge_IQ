import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Type, Optional, Union
import httpx
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
        resolved_key = api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or ""
        if not resolved_key:
            raise ValueError(
                "OpenAI API key is required when using the OpenAI provider. "
                "Set OPENAI_API_KEY environment variable or use ai_provider='deterministic'."
            )
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


class NVIDIAProvider(AIProvider):
    """NVIDIA NIM provider with deterministic recovery for offline operation."""

    base_url = "https://integrate.api.nvidia.com/v1"

    def __init__(
        self,
        model_name: Optional[str] = None,
        embed_model_name: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ):
        from app.config import settings

        self.model_name = model_name or settings.nvidia_model
        self.embed_model_name = embed_model_name or settings.nvidia_embed_model
        self.api_key = settings.nvidia_api_key
        self.timeout = timeout
        self._client = client
        self._fallback = DeterministicAIProvider()

    def _request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is not configured")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        client = self._client or httpx.Client(timeout=self.timeout)
        close_client = self._client is None
        try:
            response = client.post(
                f"{self.base_url}/{endpoint}",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                client.close()

    def _safe_request(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for attempt in range(3):
            try:
                return self._request(endpoint, payload)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                transient = isinstance(exc, (httpx.TimeoutException, httpx.TransportError)) or status_code == 408 or status_code == 429 or (status_code is not None and status_code >= 500)
                if not transient or attempt == 2:
                    logger.warning("NVIDIA provider request failed (%s): %s", endpoint, type(exc).__name__)
                    return None
                time.sleep(0.1 * (2 ** attempt))
            except (ValueError, RuntimeError) as exc:
                logger.warning("NVIDIA provider request failed (%s): %s", endpoint, type(exc).__name__)
                return None
        return None

    def generate_text(self, prompt: str) -> str:
        response = self._safe_request(
            "chat/completions",
            {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            },
        )
        if not response:
            return ""
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("NVIDIA provider returned an invalid text response: %s", type(exc).__name__)
            return ""

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        fallback: Optional[Callable[[], BaseModel]] = None,
    ) -> BaseModel:
        response = self._safe_request(
            "chat/completions",
            {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            },
        )
        if response:
            try:
                content = response["choices"][0]["message"]["content"]
                parsed = json.loads(content) if isinstance(content, str) else content
                return schema.model_validate(parsed)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                logger.warning("NVIDIA provider returned invalid structured output: %s", type(exc).__name__)

        if fallback:
            return fallback()
        return schema.model_construct()

    def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        inputs = [text] if isinstance(text, str) else text
        response = self._safe_request(
            "embeddings",
            {"model": self.embed_model_name, "input": inputs, "input_type": "passage"},
        )
        if response:
            try:
                vectors = [item["embedding"] for item in sorted(response["data"], key=lambda item: item["index"])]
                return vectors[0] if isinstance(text, str) else vectors
            except (KeyError, TypeError, IndexError) as exc:
                logger.warning("NVIDIA provider returned invalid embedding output: %s", type(exc).__name__)

        fallback_vectors = self._fallback_embedding(text)
        return fallback_vectors

    def _fallback_embedding(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        from app.retrieval.embeddings import DeterministicEmbeddingProvider

        fallback = DeterministicEmbeddingProvider()
        if isinstance(text, str):
            return fallback.embed_query(text)
        return fallback.embed_documents(text)

    def extract_product_attributes(self, product_info: str, evidence: str, schema: Type[BaseModel]) -> BaseModel:
        prompt = EXTRACTION_PROMPT.format(product_info=product_info, evidence_text=evidence).to_string()
        return self.generate_structured(
            prompt,
            schema,
            fallback=lambda: self._fallback.extract_product_attributes(product_info, evidence, schema),
        )

    def classify_product(self, product_info: str) -> str:
        return self._fallback.classify_product(product_info)

    def validate_attribute(self, attribute_name: str, attribute_value: Any, evidence: str) -> bool:
        return self._fallback.validate_attribute(attribute_name, attribute_value, evidence)


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

def get_ai_provider() -> AIProvider:
    """Factory to get the configured AI provider."""
    from app.config import settings
    if settings.ai_provider == "deterministic":
        return DeterministicAIProvider()
    if settings.ai_provider == "nvidia":
        return NVIDIAProvider()
    return LangchainOpenAIProvider()
