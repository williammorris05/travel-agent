from typing import Literal
import logging
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from travel_agent.contracts import Contract, PreferenceUpdate, Preferences
from travel_agent.sessions import RefreshLimit, RevisionConflict, Session, SessionStore
from travel_agent.planning import plan
from travel_agent.chat import converse
from travel_agent.providers.openai_transport import ModelUnavailable
from travel_agent.providers.serpapi_hotels import HotelUnavailable
from travel_agent.activities import activity_guide
from travel_agent.freshness import evidence_expired

logger = logging.getLogger("travel_agent.chat")


class CreateTrip(Contract):
    preferences: Preferences = Field(default_factory=Preferences)


class TripResponse(Session):
    missing_fields: list[str]
    status: Literal["needs_clarification", "ready"]
    results_stale: bool
    activities_stale: bool
    planning_available: bool = False


class ErrorDetail(Contract):
    code: str
    message: str


class ErrorResponse(Contract):
    error: ErrorDetail


def response(session: Session, planning_available: bool = False) -> TripResponse:
    missing = session.preferences.missing()
    return TripResponse(**session.model_dump(), missing_fields=missing, planning_available=planning_available,
                        activities_stale=session.activity_result is not None and (session.activity_result.preference_revision != session.revision or evidence_expired(session.activity_result) or 'activities' in session.source_issues),
                        status="needs_clarification" if missing else "ready",
                        results_stale=session.result is not None and (session.result.preference_revision != session.revision or evidence_expired(session.result) or 'hotels' in session.source_issues))


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump())


def available(request: Request) -> bool:
    settings = request.app.state.settings
    return settings.data_mode == "fixture" or settings.hotels_available


router = APIRouter(prefix="/api/trips", responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})


@router.post("", response_model=TripResponse, status_code=201)
def create(body: CreateTrip, request: Request):
    return response(request.app.state.trips.create(body.preferences), available(request))


@router.get("/{trip_id}", response_model=TripResponse)
def get(trip_id: str, request: Request):
    try:
        return response(request.app.state.trips.get(trip_id), available(request))
    except KeyError:
        return error(404, "trip_not_found", "This trip does not exist or the server restarted.")


@router.patch("/{trip_id}/preferences", response_model=TripResponse)
def update(trip_id: str, body: PreferenceUpdate, request: Request):
    store: SessionStore = request.app.state.trips
    try:
        return response(store.update(trip_id, body), available(request))
    except KeyError:
        return error(404, "trip_not_found", "This trip does not exist or the server restarted.")
    except RevisionConflict:
        return error(409, "revision_conflict", "Reload the trip before applying this update.")
    except ValidationError:
        return error(422, "invalid_preferences", "The merged preferences are invalid; no changes were saved.")


class PlanRequest(Contract):
    expected_revision: int = Field(strict=True, ge=0)


class ChatRequest(PlanRequest):
    expected_conversation_revision: int = Field(strict=True, ge=0)
    message: str = Field(min_length=1, max_length=3000)


class RefreshRequest(PlanRequest):
    request_id: UUID


@router.post("/{trip_id}/refresh", response_model=TripResponse)
async def refresh(trip_id: str, body: RefreshRequest, request: Request):
    store = request.app.state.trips
    try:
        with store.chat_turn(trip_id):
            previous = store.get(trip_id)
            if previous.revision != body.expected_revision:
                raise RevisionConflict()
            if store.refresh_seen(trip_id, str(body.request_id)):
                return response(previous, available(request))
            guide = activity_guide(previous.preferences, previous.revision)
            result, issues = None, {}
            if guide.status == 'unavailable':
                issues['activities'] = 'Activity guide unavailable; review the coverage details.'
            if previous.preferences.missing():
                issues['hotels'] = 'Complete trip preferences before requesting trip or hotel results.'
            else:
                try:
                    result = (await request.app.state.hotels.search(previous.preferences, previous.revision)
                              if request.app.state.settings.data_mode == 'live' else plan(previous.preferences, previous.revision))
                except HotelUnavailable:
                    issues['hotels'] = 'Hotel search unavailable or allowance exhausted. Previous hotel results were retained; no fixtures substituted.'
            return response(store.publish_bundle(previous, result, guide, issues, str(body.request_id)), available(request))
    except KeyError:
        return error(404, 'trip_not_found', 'This trip no longer exists.')
    except RevisionConflict:
        return error(409, 'revision_conflict', 'A search is running or preferences changed. Reload before retrying.')
    except RefreshLimit:
        return error(429, 'refresh_limit', 'This trip reached its 100-refresh limit. Start a new trip; provider allowances remain shared.')


@router.post("/{trip_id}/activities", response_model=TripResponse)
def activities(trip_id: str, body: PlanRequest, request: Request):
    store = request.app.state.trips
    try:
        with store.chat_turn(trip_id):
            session = store.get(trip_id)
            if session.revision != body.expected_revision:
                raise RevisionConflict()
            return response(store.publish(trip_id, activity_guide(session.preferences, session.revision), activities=True), available(request))
    except KeyError:
        return error(404, "trip_not_found", "This trip no longer exists.")
    except RevisionConflict:
        return error(409, "revision_conflict", "Trip changed; reload before comparing activities.")


@router.post("/{trip_id}/messages", response_model=TripResponse, responses={503: {"model": ErrorResponse}, 502: {"model": ErrorResponse}})
async def message(trip_id: str, body: ChatRequest, request: Request):
    store = request.app.state.trips
    try:
        previous = store.get(trip_id)
        if previous.revision != body.expected_revision or previous.conversation_revision != body.expected_conversation_revision:
            raise RevisionConflict()
        if not body.message.strip():
            return error(422, "empty_message", "Please enter a travel message.")
        if request.app.state.chat_transport is None:
            return error(503, "model_unavailable", "Natural-language chat needs a configured model. Demo commands still work.")
        with store.chat_turn(trip_id):
            started = monotonic()
            outcome = "rejected"
            try:
                next_state = await converse(store, previous, body.message, request.app.state.chat_transport,
                                            request.app.state.hotels if request.app.state.settings.data_mode == "live" else None)
                outcome = "committed"
            finally:
                # No identifiers, prompts, preferences, keys or exception bodies.
                logger.info("chat_turn outcome=%s elapsed_ms=%d", outcome, round((monotonic() - started) * 1000))
        return response(next_state, available(request))
    except KeyError:
        return error(404, "trip_not_found", "This trip no longer exists. Start a new trip.")
    except RevisionConflict:
        return error(409, "revision_conflict", "Trip or conversation changed. Reload before sending again.")
    except ModelUnavailable:
        return error(503, "model_unavailable", "The model is unavailable or its call allowance is exhausted. No changes were saved.")
    except HotelUnavailable:
        return error(503, "hotel_unavailable", "Hotel search is unavailable or its allowance is exhausted. No changes were saved; no fixtures were substituted.")
    except (ValueError, TimeoutError):
        return error(502, "invalid_model_response", "The message could not be interpreted safely. No changes were saved; try rephrasing.")


@router.post("/{trip_id}/plan", response_model=TripResponse, responses={503: {"model": ErrorResponse}})
async def generate(trip_id: str, body: PlanRequest, request: Request):
    store: SessionStore = request.app.state.trips
    try:
        session = store.get(trip_id)
        if session.revision != body.expected_revision:
            raise RevisionConflict()
        if not available(request):
            store.record_issue(session, 'hotels', 'Hotel search is not configured. Previous results are unrefreshed.')
            return error(503, "live_unavailable", "Live adapters are not configured; no fixtures were substituted.")
        if session.preferences.missing():
            return response(session, True)
        with store.chat_turn(trip_id):
            result = (await request.app.state.hotels.search(session.preferences, session.revision)
                      if request.app.state.settings.data_mode == "live" else plan(session.preferences, session.revision))
            return response(store.publish(trip_id, result), True)
    except HotelUnavailable:
        store.record_issue(session, 'hotels', 'Hotel search unavailable; previous results are unrefreshed.')
        return error(503, "hotel_unavailable", "Hotel search failed or its allowance is exhausted. Previous results are retained; no fixtures were substituted.")
    except KeyError:
        return error(404, "trip_not_found", "This trip does not exist or the server restarted.")
    except RevisionConflict:
        return error(409, "revision_conflict", "Trip changed; reload before requesting options.")
