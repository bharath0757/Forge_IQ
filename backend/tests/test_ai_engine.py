import pytest
import os
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

# Requires OPENAI_API_KEY for tests
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI API key required to run AI Engine tests"
)

from app.ai.provider import LangchainOpenAIProvider
from app.ai.schemas import MotorProtectionCircuitBreakerAttributes, ExtractedAttribute

@pytest.fixture
def provider():
    with patch("app.ai.provider.ChatOpenAI") as mock_chat:
        yield LangchainOpenAIProvider(model_name="test-model")

def test_extract_valid_response(provider):
    mock_runnable = MagicMock()
    mock_runnable.invoke.return_value = MotorProtectionCircuitBreakerAttributes(
        voltage=ExtractedAttribute(value="400V", status="EXTRACTED", evidence_ids=["ev-1"]),
        current=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        frequency=ExtractedAttribute(value="50Hz", status="EXTRACTED", evidence_ids=["ev-2"]),
        dimensions=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        material=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        poles=ExtractedAttribute(value=3, status="EXTRACTED", evidence_ids=["ev-1"]),
        trip_class=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        mounting=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        application=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
        standards=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[])
    )
    provider.llm.with_structured_output.return_value = mock_runnable
    
    result = provider.extract_product_attributes(
        product_info="Product A", 
        evidence="Evidence doc", 
        schema=MotorProtectionCircuitBreakerAttributes
    )
    
    assert result.voltage.value == "400V"
    assert result.voltage.status == "EXTRACTED"
    assert result.voltage.evidence_ids == ["ev-1"]
    
    # Verify missing attributes are null and UNKNOWN
    assert result.current.value is None
    assert result.current.status == "UNKNOWN"

def test_extract_retry_on_validation_error(provider):
    mock_runnable = MagicMock()
    
    # First call raises ValueError (simulating a validation failure from Langchain parsing)
    # Second call succeeds
    mock_runnable.invoke.side_effect = [
        ValueError("Simulated validation error"),
        MotorProtectionCircuitBreakerAttributes(
            voltage=ExtractedAttribute(value="230V", status="EXTRACTED", evidence_ids=["ev-3"]),
            current=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            frequency=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            dimensions=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            material=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            poles=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            trip_class=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            mounting=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            application=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[]),
            standards=ExtractedAttribute(value=None, status="UNKNOWN", evidence_ids=[])
        )
    ]
    
    provider.llm.with_structured_output.return_value = mock_runnable
    
    result = provider.extract_product_attributes(
        product_info="Product B", 
        evidence="Evidence doc B", 
        schema=MotorProtectionCircuitBreakerAttributes
    )
    
    # Ensure it retried and called invoke twice
    assert mock_runnable.invoke.call_count == 2
    assert result.voltage.value == "230V"
