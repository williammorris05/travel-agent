import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from travel_agent.main import create_app
from travel_agent.providers.structured_output import validated_output
from travel_agent.settings import Settings


@pytest.mark.parametrize(
    ("mode", "status"),
    [("fixture", "fixtures_ready"), ("live", "live_adapters_unavailable")],
)
def test_health_reports_fixture_capability_and_live_limit(mode, status):
    client = TestClient(create_app(Settings(_env_file=None, data_mode=mode)))
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == mode
    assert body["travel_status"] == status
    assert body["planning_available"] is (mode == "fixture")
    assert body["model_status"] == "not_configured"
    assert body["demo_scope"]["evidence"] == "synthetic_scope_only"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, data_mode="liv")


class SpikeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str
    adults: int = Field(ge=1, le=2)


class StubTransport:
    """Canned test response. Does not interpret the prompt or call a model."""

    def __init__(self, response: str):
        self.response = response
        self.schema = None

    async def complete_json(self, prompt: str, schema: dict) -> str:
        self.schema = schema
        return self.response


def test_structured_output_spike_passes_schema_and_validates_response():
    transport = StubTransport('{"origin":"Chicago","adults":2}')
    result = asyncio.run(validated_output(transport, "synthetic request", SpikeOutput))
    assert result.adults == 2
    assert "origin" in transport.schema["required"]


@pytest.mark.parametrize(
    "raw",
    ["not JSON", '{"origin":"Chicago"}', '{"origin":"Chicago","adults":0}',
     '{"origin":"Chicago","adults":"2"}',
     '{"origin":"Chicago","adults":2,"invented_price":100}'],
)
def test_structured_output_spike_rejects_invalid_output(raw):
    with pytest.raises(ValidationError):
        asyncio.run(validated_output(StubTransport(raw), "request", SpikeOutput))


def test_structured_output_spike_does_not_hide_provider_failure():
    class FailedTransport:
        async def complete_json(self, prompt: str, schema: dict) -> str:
            raise TimeoutError("synthetic timeout")

    with pytest.raises(TimeoutError):
        asyncio.run(validated_output(FailedTransport(), "request", SpikeOutput))
