from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from travel_agent.catalog import catalog
from travel_agent.contracts import Preferences, summarize_costs
from travel_agent.main import create_app
from travel_agent.planning import REQUIRED_CATEGORIES, plan
from travel_agent.settings import Settings


def prefs(**overrides):
    values = dict(origin="Chicago", dates={"mode": "flexible"}, nights=2, adults=1,
                  budget={"amount": "1000", "basis": "party", "covers": sorted(REQUIRED_CATEGORIES)},
                  constraints={"shared_room_allowed": True, "camping_allowed": True, "overnight_transport_allowed": True},
                  controls={"savings": 100, "adventure": 0, "transit_tolerance": 100})
    values.update(overrides)
    return Preferences(**values)


def by_id(id):
    return next(item for item in catalog() if item.id == id)


def test_e05_cheap_slow_dorm_can_win():
    result = plan(prefs(), 0)
    assert result.options[0].id == "milwaukee-bus-dorm"
    assert result.options[0].total_cost.total == Decimal("119")  # 30 + 36 + 45 + 8
    assert result.options[0].transit_minutes == 600
    assert all(cost.evidence.kind == "demo" for option in result.options for cost in option.costs)


def test_e06_remote_room_is_not_ranked_by_room_price():
    result = plan(prefs(), 0, candidates=[by_id("starved-remote"), by_id("dunes-private")])
    assert result.options[0].id == "dunes-private"
    assert result.options[0].total_cost.total == Decimal("338")
    assert result.options[1].total_cost.total == Decimal("478")


def test_e07_adventure_preserves_private_room():
    p = prefs(constraints={"private_room": True, "camping_allowed": True, "shared_room_allowed": True},
              controls={"adventure": 100, "savings": 0, "transit_tolerance": 100})
    result = plan(p, 0)
    assert result.options[0].id == "starved-remote"
    assert all(option.accommodation == "private_room" for option in result.options)


def test_e08_camping_includes_rental_gear_for_whole_party():
    result = plan(prefs(adults=2), 0, candidates=[by_id("dunes-camping")])
    option = result.options[0]
    assert option.total_cost.total == Decimal("358")  # 70 fare + 35 access + 50 site + 120 food + 75 gear + 8 fees
    assert next(cost for cost in option.costs if cost.category == "gear").quantity == 1


def test_e09_time_includes_rest_and_rejects_impossible_connections():
    result = plan(prefs(nights=1), 0)
    exclusions = {item.candidate_id: item.reasons for item in result.exclusions}
    assert "milwaukee-overnight" in exclusions and "starved-impossible" in exclusions
    assert result.options[0].destination_minutes == 840


def test_e10_no_match_explains_constraints_without_relaxation():
    p = prefs(budget={"amount": "1", "basis": "party", "covers": sorted(REQUIRED_CATEGORIES)})
    result = plan(p, 0)
    assert result.status == "no_match" and result.options == []
    assert any("exceed" in reason for item in result.exclusions for reason in item.reasons)
    assert p.budget.amount == 1


def test_e12_missing_fees_and_omitted_components_never_win():
    unknown = by_id("starved-missing-fee")
    omitted = by_id("milwaukee-bus-dorm")
    omitted.rates = [rate for rate in omitted.rates if rate.category != "fees"]
    result = plan(prefs(), 0, candidates=[unknown, omitted])
    assert result.status == "no_match"
    assert len(result.exclusions) == 2
    assert any("unknown required costs: fees" in gap for gap in result.coverage_gaps)


def test_e17_cheap_low_exertion_does_not_imply_strenuous_activity():
    result = plan(prefs(constraints={"max_exertion": "low", "shared_room_allowed": True},
                        controls={"savings": 100, "adventure": 100}), 0)
    assert result.options[0].id == "milwaukee-bus-dorm"
    assert all(option.exertion == "low" for option in result.options)


def test_controls_change_winner_independently():
    candidates = [by_id("milwaukee-bus-dorm"), by_id("milwaukee-train-hotel"), by_id("dunes-camping")]
    assert plan(prefs(), 0, candidates=candidates).options[0].id == "milwaukee-bus-dorm"
    assert plan(prefs(controls={"savings": 0, "adventure": 100, "transit_tolerance": 100}), 0, candidates=candidates).options[0].id == "dunes-camping"
    assert plan(prefs(controls={"savings": 0, "adventure": 0, "transit_tolerance": 0}), 0, candidates=candidates).options[0].id == "milwaukee-train-hotel"


def test_diversity_preserves_winner_and_uses_three_destinations():
    result = plan(prefs(controls={"savings": 50, "adventure": 100}), 0)
    assert result.options[0].id == "dunes-camping"
    assert len({option.destination for option in result.options}) == 3


def test_budget_basis_scope_and_quantity_scaling():
    p = prefs(adults=2, budget={"amount": "40", "basis": "per_person", "covers": ["transport"]})
    option = plan(p, 0, candidates=[by_id("milwaukee-bus-dorm")]).options[0]
    assert option.budget_cap == 80 and option.budget_cost.total == 60
    assert option.total_cost.total == 230  # fare60 + beds72 + food90 + fees8
    assert option.budget_categories == ["transport"]
    assert summarize_costs(option.costs, REQUIRED_CATEGORIES) == option.total_cost


@pytest.mark.parametrize("constraint", [{"accessibility": ["step-free"]}, {"excluded_transport": [" BUS "]}, {"shared_room_allowed": False}, {}])
def test_unknown_or_forbidden_constraints_are_not_assumed_satisfied(constraint):
    assert plan(prefs(constraints=constraint), 0, candidates=[by_id("milwaukee-bus-dorm")]).status == "no_match"


def test_dates_recalculate_duration_and_prices():
    p = prefs(nights=None, dates={"mode": "fixed", "start": "2027-06-01", "end": "2027-06-04"})
    option = plan(p, 4, candidates=[by_id("milwaukee-bus-dorm")]).options[0]
    assert option.nights == 3 and option.total_cost.total == 152


def test_origin_scope_and_incomplete_intake():
    assert plan(prefs(origin="Boston"), 0).status == "unavailable"
    assert plan(Preferences(), 0).status == "unavailable"


def test_large_per_person_cap_and_zero_budget_are_valid_requests():
    p = prefs(adults=2, budget={"amount": "9999999999.99", "basis": "per_person", "covers": sorted(REQUIRED_CATEGORIES)})
    assert plan(p, 0).options[0].budget_cap == Decimal("19999999999.98")
    p = prefs(budget={"amount": "0", "basis": "party", "covers": sorted(REQUIRED_CATEGORIES)})
    assert plan(p, 0).status == "no_match"


def test_late_api_planning_result_cannot_overwrite_correction(monkeypatch):
    import travel_agent.trips_api as api
    from travel_agent.contracts import PreferenceUpdate
    app = create_app()
    original = api.plan
    with TestClient(app) as client:
        trip = client.post("/api/trips", json={"preferences": prefs().model_dump(mode="json")}).json()
        def delayed(preferences, revision):
            result = original(preferences, revision)
            app.state.trips.update(trip["id"], PreferenceUpdate(expected_revision=0, source="chat", changes={"nights": 3}))
            return result
        monkeypatch.setattr(api, "plan", delayed)
        assert client.post(f'/api/trips/{trip["id"]}/plan', json={"expected_revision": 0}).status_code == 409
        state = client.get(f'/api/trips/{trip["id"]}').json()
        assert state["revision"] == 1 and state["result"] is None


def test_api_plan_refinement_and_revision_conflict():
    with TestClient(create_app(Settings(_env_file=None, data_mode="fixture"))) as client:
        trip = client.post("/api/trips", json={"preferences": prefs().model_dump(mode="json")}).json()
        path = f'/api/trips/{trip["id"]}'
        result = client.post(path + "/plan", json={"expected_revision": 0})
        assert result.status_code == 200
        assert result.json()["result"]["options"][0]["id"] == "milwaukee-bus-dorm"
        changed = client.patch(path + "/preferences", json={"expected_revision": 0, "source": "slider", "changes": {"controls": {"adventure": 100, "savings": 0}}}).json()
        assert changed["results_stale"]
        assert client.post(path + "/plan", json={"expected_revision": 0}).status_code == 409
        refreshed = client.post(path + "/plan", json={"expected_revision": 1}).json()
        assert refreshed["result"]["options"][0]["id"] == "dunes-camping"
        assert not refreshed["results_stale"] and refreshed["result"]["preference_revision"] == 1
        assert client.post("/api/trips/missing/plan", json={"expected_revision": 0}).status_code == 404


def test_api_live_never_substitutes_fixtures_and_intake_clarifies():
    with TestClient(create_app(Settings(_env_file=None, data_mode="live"))) as client:
        trip = client.post("/api/trips", json={"preferences": prefs().model_dump(mode="json")}).json()
        result = client.post(f'/api/trips/{trip["id"]}/plan', json={"expected_revision": 0})
        assert result.status_code == 503 and result.json()["error"]["code"] == "live_unavailable"
    with TestClient(create_app()) as client:
        trip = client.post("/api/trips", json={}).json()
        result = client.post(f'/api/trips/{trip["id"]}/plan', json={"expected_revision": 0}).json()
        assert result["status"] == "needs_clarification" and result["result"] is None
