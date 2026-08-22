import json

import httpx
from pydantic import BaseModel

from app.ai.provider import NVIDIAProvider


class Extraction(BaseModel):
    value: str


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_nvidia_structured_generation_validates_response(monkeypatch):
    monkeypatch.setattr("app.config.settings.nvidia_api_key", "test-key")

    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"value": "400 V"})}}]},
        )

    provider = NVIDIAProvider(client=make_client(handler))
    result = provider.generate_structured("Return JSON", Extraction)

    assert result == Extraction(value="400 V")


def test_nvidia_retries_transient_failure_and_embeds(monkeypatch):
    monkeypatch.setattr("app.config.settings.nvidia_api_key", "test-key")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    provider = NVIDIAProvider(client=make_client(handler))

    assert provider.embed("industrial motor") == [0.1, 0.2]
    assert calls == 2


def test_nvidia_failure_uses_deterministic_structured_fallback(monkeypatch, caplog):
    secret = "test-key-that-must-not-be-logged"
    monkeypatch.setattr("app.config.settings.nvidia_api_key", secret)

    def handler(request):
        raise httpx.ConnectError("connection unavailable", request=request)

    provider = NVIDIAProvider(client=make_client(handler))
    result = provider.generate_structured("Return JSON", Extraction, fallback=lambda: Extraction(value="fallback"))

    assert result == Extraction(value="fallback")
    assert secret not in caplog.text