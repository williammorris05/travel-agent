from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from travel_agent.contracts import Cost, Dates, Evidence, PreferenceUpdate, Preferences, ResultSnapshot, summarize_costs
from travel_agent.main import create_app
from travel_agent.sessions import RevisionConflict, SessionStore


def valid_preferences():
    return {"origin": "Chicago", "dates": {"mode": "fixed", "start": "2027-06-01", "end": "2027-06-04"},
            "adults": 2, "budget": {"amount": "500.00", "basis": "party", "covers": ["transport", "stay", "activities"]},
            "constraints": {"private_room": True}, "controls": {"adventure": 80}}


def test_api_intake_correction_slider_and_conflict():
    app = create_app()
    with TestClient(app) as client:
        created = client.post("/api/trips", json={"preferences": valid_preferences()})
        assert created.status_code == 201
        trip = created.json()
        assert trip["status"] == "ready"
        path = f'/api/trips/{trip["id"]}'
        app.state.trips.publish(trip["id"], ResultSnapshot(preference_revision=0, created_at=datetime.now(timezone.utc), status="unavailable"))
        changed = client.patch(path + "/preferences", json={"expected_revision": 0, "source": "chat", "changes": {"dates": {"end": "2027-06-05"}}}).json()
        assert changed["preferences"]["dates"]["start"] == "2027-06-01"
        assert changed["results_stale"] and changed["revision"] == 1
        slider = client.patch(path + "/preferences", json={"expected_revision": 1, "source": "slider", "changes": {"controls": {"savings": 100}}}).json()
        assert slider["preferences"]["constraints"]["private_room"] is True
        assert slider["preferences"]["controls"] == {"adventure": 80, "savings": 100, "transit_tolerance": None}
        assert slider["preferences"]["budget"]["amount"] == "500.00"
        assert client.patch(path + "/preferences", json={"expected_revision": 1, "source": "chat", "changes": {"origin": "Boston"}}).status_code == 409
        assert client.get(path).json()["preferences"]["origin"] == "Chicago"


def test_api_ambiguous_budget_and_explicit_flexibility():
    with TestClient(create_app()) as client:
        trip = client.post("/api/trips", json={"preferences": {"budget": {"amount": "300"}}}).json()
        assert {"origin", "dates", "adults", "budget.basis", "budget.covers"} <= set(trip["missing_fields"])
        path = f'/api/trips/{trip["id"]}/preferences'
        changed = client.patch(path, json={"expected_revision": 0, "source": "form", "changes": {"dates": {"mode": "flexible"}, "nights": 3}}).json()
        assert changed["preferences"]["dates"]["mode"] == "flexible"
        assert "dates" not in changed["missing_fields"]
        cleared = client.patch(path, json={"expected_revision": 1, "source": "chat", "changes": {"dates": None}}).json()
        assert "dates" in cleared["missing_fields"]


@pytest.mark.parametrize("changes", [{"dates": {"end": "2027-05-01"}}, {"budget": {"basis": "night"}}, {"controls": {"savings": 101}}, {"adults": True}, {"invented": 1}, {"budget": {"amount": 0.1}}])
def test_invalid_merge_is_atomic(changes):
    with TestClient(create_app()) as client:
        trip = client.post("/api/trips", json={"preferences": valid_preferences()}).json()
        path = f'/api/trips/{trip["id"]}'
        result = client.patch(path + "/preferences", json={"expected_revision": 0, "source": "chat", "changes": changes})
        assert result.status_code == 422
        assert client.get(path).json() == trip


def test_slider_cannot_change_constraints_and_unknown_trip():
    with TestClient(create_app()) as client:
        assert client.patch("/api/trips/missing/preferences", json={"expected_revision": 0, "source": "slider", "changes": {"constraints": {"private_room": False}}}).status_code == 422
        assert client.get("/api/trips/missing").status_code == 404


def test_stale_publish_noop_and_concurrent_writers():
    store = SessionStore()
    trip = store.create(Preferences(origin="Chicago"))
    same = store.update(trip.id, PreferenceUpdate(expected_revision=0, source="chat", changes={"origin": "Chicago"}))
    assert same.revision == 0
    def change(origin):
        try:
            return store.update(trip.id, PreferenceUpdate(expected_revision=0, source="chat", changes={"origin": origin})).revision
        except RevisionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(change, ["Boston", "Denver"])) == {1, "conflict"}
    with pytest.raises(RevisionConflict):
        store.publish(trip.id, ResultSnapshot(preference_revision=0, created_at=datetime.now(timezone.utc), status="no_match"))
    copy = store.get(trip.id)
    copy.preferences.origin = "Changed outside store"
    assert store.get(trip.id).preferences.origin != copy.preferences.origin


def evidence():
    return Evidence(kind="demo", provider="synthetic", retrieved_at=datetime.now(timezone.utc), explanation="Test fixture")


def test_decimal_totals_and_unknown_or_omitted_costs():
    cost = Cost(category="stay", amount="10.10", basis="per_room_night", quantity=3, evidence=evidence())
    assert summarize_costs([cost], {"stay"}).total == Decimal("30.30")
    assert summarize_costs([cost], {"stay", "transport"}).total is None
    unknown = Cost(category="transport", amount=None, basis="party_total", quantity=1, evidence=evidence(), unknown_reason="Fare missing")
    summary = summarize_costs([cost, unknown], {"stay", "transport"})
    assert summary.total is None and summary.known_subtotal == Decimal("30.30")
    assert summary.missing_categories == ["transport"]


@pytest.mark.parametrize("overrides", [{"amount": -1}, {"amount": 0.1}, {"amount": "NaN"}, {"amount": "1.001"}, {"amount": None}, {"basis": "unknown"}, {"quantity": 0}, {"quantity": 2}, {"currency": "EUR"}])
def test_invalid_prices(overrides):
    args = dict(category="stay", amount="10", basis="party_total", quantity=1, evidence=evidence())
    with pytest.raises(ValidationError):
        Cost(**(args | overrides))


@pytest.mark.parametrize("dates", [{"mode": "fixed"}, {"mode": "fixed", "start": "2027-06-01", "end": "2027-06-01"}, {"mode": "flexible", "start": 1800000000}])
def test_invalid_dates(dates):
    with pytest.raises(ValidationError):
        Dates(**dates)


def test_published_evidence_requires_context():
    data = evidence().model_dump() | {"kind": "observed_search_price"}
    with pytest.raises(ValidationError):
        Evidence(**data)
    data.update(url="https://example.com/price", search_dates=valid_preferences()["dates"], adults=2)
    assert Evidence(**data).kind == "observed_search_price"
    with pytest.raises(ValidationError):
        ResultSnapshot(preference_revision=0, created_at=datetime.now(timezone.utc), status="options")
