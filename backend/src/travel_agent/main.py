"""Application boundary for shared state and explicit fixture planning."""

from typing import Literal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from travel_agent.settings import Settings
from travel_agent.usage import UsageLedger
from travel_agent.providers.serpapi_hotels import SerpApiHotels
from travel_agent.sessions import SessionStore
from travel_agent.trips_api import router, error
from travel_agent.providers.openai_transport import OpenAITransport
from travel_agent.providers.gemini_transport import GeminiTransport


class DemoScope(BaseModel):
    origin: str = "Chicago, Illinois"
    destinations: tuple[str, ...] = (
        "Milwaukee, Wisconsin",
        "Indiana Dunes, Indiana",
        "Starved Rock, Illinois",
    )
    currency: Literal["USD"] = "USD"
    adults: tuple[int, ...] = (1, 2)
    evidence: Literal["synthetic_scope_only"] = "synthetic_scope_only"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
    data_mode: Literal["fixture", "live"]
    planning_available: bool = False
    model_status: Literal["not_configured", "configured"] = "not_configured"
    chat_available: bool = False
    travel_status: Literal["fixtures_ready", "live_adapters_unavailable", "hotel_search_configured"]
    demo_scope: DemoScope = DemoScope()


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    application = FastAPI(title="Travel Agent", version="0.1.0")
    application.state.trips = SessionStore()
    application.state.settings = configuration
    application.state.usage = UsageLedger(configuration.usage_db)
    application.state.hotels = SerpApiHotels(configuration, ledger=application.state.usage)
    application.state.chat_transport = (
        (GeminiTransport(configuration, ledger=application.state.usage) if configuration.model_provider == "gemini" else OpenAITransport(configuration, ledger=application.state.usage))
        if configuration.chat_available else None)
    application.include_router(router)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, exception):
        return error(422, "invalid_request", "Request does not match the API contract.")

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            data_mode=configuration.data_mode,
            chat_available=configuration.chat_available,
            model_status="configured" if configuration.chat_available else "not_configured",
            planning_available=configuration.data_mode == "fixture" or configuration.hotels_available,
            travel_status=(
                "fixtures_ready"
                if configuration.data_mode == "fixture"
                else "hotel_search_configured" if configuration.hotels_available else "live_adapters_unavailable"
            ),
        )

    return application


app = create_app()
