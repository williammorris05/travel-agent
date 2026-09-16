from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from test_chat import Stub, extraction, send
from travel_agent import activities
from travel_agent.contracts import Preferences, PreferenceUpdate
from travel_agent.main import create_app
from travel_agent.sessions import SessionStore, RevisionConflict
from travel_agent.settings import Settings


@pytest.fixture(autouse=True)
def current_review(monkeypatch):
    monkeypatch.setattr(activities, 'REVIEWED', datetime.now(timezone.utc))


@pytest.mark.parametrize('adults,amount', [(1,35),(2,65)])
def test_published_party_charge_and_unknown_costs(adults, amount):
    result = activities.activity_guide(Preferences(adults=adults),0)
    walk, paddle = result.options
    assert walk.activity_cost.total == 0
    assert paddle.activity_cost.total == Decimal(amount)
    assert paddle.costs[0].quantity == 1
    assert paddle.total_cost.total is None
    assert {'gear','transport','fees'} <= set(paddle.total_cost.missing_categories)
    assert paddle.costs[0].evidence.kind == 'published_price'
    assert paddle.costs[0].evidence.search_dates is None
    assert paddle.supporting_evidence[0].url.host == 'milwaukeekayak.com'


def test_low_exertion_excludes_paddle_without_relaxing_room_requirement():
    p = Preferences(adults=1, controls={'adventure':100}, constraints={'max_exertion':'low','private_room':True})
    result = activities.activity_guide(p,4)
    assert [o.id for o in result.options] == ['riverwalk-self-guided']
    assert p.constraints.private_room and result.exclusions[0].candidate_id == 'kayak-rental'


def test_accessibility_unknown_is_not_accepted_as_satisfied():
    result = activities.activity_guide(Preferences(adults=1, constraints={'accessibility':['step-free route']}),0)
    assert result.status == 'no_match' and len(result.exclusions) == 2


def test_budget_filters_only_when_activity_is_in_scope():
    p = Preferences(adults=2,budget={'amount':'30','basis':'per_person','covers':['activities']})
    assert len(activities.activity_guide(p,0).options) == 1  # 65 exceeds party cap of 60.
    p.budget.covers = ['stay']
    assert len(activities.activity_guide(p,0).options) == 2


def test_price_and_adventure_order_is_separate_from_complete_budget_fit():
    p = Preferences(adults=1, controls={'adventure':100,'savings':0})
    assert activities.activity_guide(p,0).options[0].id == 'kayak-rental'
    p.controls.savings = 100
    result = activities.activity_guide(p,0)
    assert result.options[0].id == 'riverwalk-self-guided'
    assert all(o.budget_cost is None and o.total_cost.total is None for o in result.options)


def test_expired_source_review_is_not_refreshed_by_request(monkeypatch):
    monkeypatch.setattr(activities, 'REVIEWED', datetime.now(timezone.utc)-timedelta(days=31))
    result = activities.activity_guide(Preferences(adults=1),0)
    assert result.status == 'unavailable' and result.options == []


def test_missing_party_returns_clarification_without_prices():
    assert activities.activity_guide(Preferences(),0).status == 'unavailable'


def test_api_activity_snapshot_is_separate_and_stale_after_correction():
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={'preferences':{'adults':1}}).json()
        url = f'/api/trips/{trip["id"]}'
        trip = client.post(url+'/activities',json={'expected_revision':0}).json()
        assert trip['result'] is None and trip['activity_result']['options']
        trip = client.patch(url+'/preferences',json={'expected_revision':0,'source':'slider','changes':{'controls':{'savings':100}}}).json()
        assert trip['activities_stale']
        assert client.post(url+'/activities',json={'expected_revision':0}).status_code == 409
        trip = client.post(url+'/activities',json={'expected_revision':1}).json()
        assert not trip['activities_stale']


def test_natural_language_activity_intent_does_not_call_hotel_provider():
    app = create_app(Settings(_env_file=None,data_mode='live'))
    app.state.chat_transport = Stub([extraction(intent='activities')])
    with TestClient(app) as client:
        p = {'adults':1}  # Published listings do not require dates or a full-trip intake.
        trip = client.post('/api/trips',json={'preferences':p}).json()
        reply = send(client,trip,'What activities can I do?')
        assert reply.status_code == 200
        assert reply.json()['activity_result']['options']
        assert reply.json()['result'] is None and app.state.hotels.calls == 0


def test_late_activity_publication_rejected():
    store = SessionStore()
    trip = store.create(Preferences(adults=1))
    result = activities.activity_guide(trip.preferences,0)
    store.update(trip.id,PreferenceUpdate(expected_revision=0,source='form',changes={'adults':2}))
    with pytest.raises(RevisionConflict):
        store.publish(trip.id,result,activities=True)
    assert store.get(trip.id).activity_result is None
