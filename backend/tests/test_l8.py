"""Controlled reliability checks. No external calls or live-access claims."""
import asyncio
import sqlite3
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from test_chat import Stub, extraction, op, send
from test_hotels import prefs, payload, settings
from travel_agent.activities import activity_guide
from travel_agent.contracts import Preferences
from travel_agent.freshness import evidence_expired
from travel_agent.main import create_app
from travel_agent.providers.serpapi_hotels import HotelUnavailable, normalize
from travel_agent.providers.openai_transport import ModelUnavailable
from travel_agent.settings import Settings
from travel_agent.trips_api import response
from travel_agent.usage import UsageLedger


def guide_prefs():
    return Preferences.model_validate({**prefs().model_dump(), 'constraints': {}})


@pytest.fixture(autouse=True)
def current_test_guide(monkeypatch):
    # Controlled review time keeps reliability tests independent of real-source expiry.
    monkeypatch.setattr('travel_agent.activities.REVIEWED', datetime.now(timezone.utc) - timedelta(days=1))


def test_atomic_ledger_across_threads_reopen_and_processes(tmp_path):
    path = tmp_path / 'usage.sqlite3'
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: UsageLedger(path).reserve('hotels', 10), range(40)))
    assert sum(results) == UsageLedger(path).used('hotels') == 10
    code = 'from pathlib import Path; from travel_agent.usage import UsageLedger; import sys; print(UsageLedger(Path(sys.argv[1])).reserve("model", 3))'
    processes = [subprocess.Popen([sys.executable, '-c', code, str(path)], cwd=Path(__file__).parents[1] / 'src', stdout=subprocess.PIPE, text=True) for _ in range(8)]
    outputs = [process.communicate(timeout=15)[0].strip() for process in processes]
    assert all(process.returncode == 0 for process in processes)
    assert outputs.count('True') == UsageLedger(path).used('model') == 3
    assert not UsageLedger(path).reserve('hotels', 10)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM usage ORDER BY bucket').fetchall() == [('hotels', 10), ('model', 3)]


def test_unavailable_or_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / 'bad.sqlite3'
    path.write_text('not a database')
    ledger = UsageLedger(path)
    assert not ledger.reserve('hotels', 1) and ledger.used('hotels') is None
    assert not UsageLedger(path / 'child').reserve('model', 1)
    assert not ledger.reserve('secret-or-trip-data', 100)


def test_app_restart_preserves_failed_attempts_and_model_bucket(tmp_path):
    async def run():
        config = settings(usage_db=tmp_path / 'usage.sqlite3', model_provider='openai', model_name='test',
                          model_max_calls=1, openai_api_key='test')
        requests = []
        def fail(request):
            requests.append(request)
            return httpx.Response(429)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            first = create_app(config)
            first.state.hotels.client = client
            first.state.chat_transport.client = client
            with pytest.raises(HotelUnavailable):
                await first.state.hotels.search(prefs(), 0)
            with pytest.raises(ModelUnavailable):
                await first.state.chat_transport.complete_json('synthetic', {})
            restarted = create_app(config)
            restarted.state.hotels.client = client
            with pytest.raises(HotelUnavailable):
                await restarted.state.hotels.search(prefs(), 0)
            with pytest.raises(HotelUnavailable):
                await restarted.state.hotels.search(prefs(), 0)
            switched = create_app(config.model_copy(update={'model_provider':'gemini', 'gemini_api_key':config.openai_api_key}))
            switched.state.chat_transport.client = client
            with pytest.raises(ModelUnavailable):
                await switched.state.chat_transport.complete_json('synthetic', {})
        assert len(requests) == 3  # Two failed hotels + one failed model, no retries.
        assert restarted.state.usage.used('hotels') == 2
        assert switched.state.usage.used('model') == 1
    asyncio.run(run())


def test_partial_refresh_dedup_and_preference_change(tmp_path):
    app = create_app(settings(usage_db=tmp_path / 'usage.sqlite3'))
    class Hotels:
        calls = 0
        async def search(self, p, revision):
            self.calls += 1
            raise HotelUnavailable()
    app.state.hotels = hotels = Hotels()
    with TestClient(app) as client:
        trip = client.post('/api/trips', json={'preferences':guide_prefs().model_dump(mode='json')}).json()
        old = normalize(payload(guide_prefs()), guide_prefs(), 0)
        app.state.trips.publish(trip['id'], old)
        url = f'/api/trips/{trip["id"]}'
        a = {'expected_revision':0, 'request_id':str(uuid4())}
        result = client.post(url + '/refresh', json=a)
        assert result.status_code == 200
        data = result.json()
        assert data['result'] == old.model_dump(mode='json') and data['results_stale']
        assert data['activity_result']['status'] == 'options' and not data['activities_stale']
        assert 'hotels' in data['source_issues']
        client.post(url + '/refresh', json={'expected_revision':0, 'request_id':str(uuid4())})
        assert client.post(url + '/refresh', json=a).status_code == 200
        assert hotels.calls == 2  # Older completed IDs also deduplicate.
        for revision in range(5):
            patch = client.patch(url + '/preferences', json={'expected_revision':revision, 'source':'slider', 'changes':{'controls':{'adventure':revision + 1}}})
            assert patch.status_code == 200
        assert hotels.calls == 2
        assert client.post(url + '/refresh', json=a).status_code == 409


def test_direct_failed_plan_stays_stale_after_reload(tmp_path):
    app = create_app(settings(usage_db=tmp_path / 'usage.sqlite3'))
    class Hotels:
        async def search(self, p, revision):
            raise HotelUnavailable()
    app.state.hotels = Hotels()
    with TestClient(app) as client:
        p = guide_prefs()
        trip = client.post('/api/trips', json={'preferences':p.model_dump(mode='json')}).json()
        app.state.trips.publish(trip['id'], normalize(payload(p), p, 0))
        url = f'/api/trips/{trip["id"]}'
        assert client.post(url + '/plan', json={'expected_revision':0}).status_code == 503
        reloaded = client.get(url).json()
        assert reloaded['results_stale'] and 'hotels' in reloaded['source_issues']


def test_refresh_limit_keeps_dedup_history():
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        trip = client.post('/api/trips', json={'preferences':{'adults':1}}).json()
        url = f'/api/trips/{trip["id"]}/refresh'
        first = None
        for _ in range(100):
            body = {'expected_revision':0, 'request_id':str(uuid4())}
            first = first or body
            assert client.post(url, json=body).status_code == 200
        assert client.post(url, json={'expected_revision':0,'request_id':str(uuid4())}).status_code == 429
        assert client.post(url, json=first).status_code == 200


def test_concurrent_refresh_and_late_results(tmp_path):
    async def run():
        app = create_app(settings(usage_db=tmp_path / 'usage.sqlite3'))
        started, release = asyncio.Event(), asyncio.Event()
        class Hotels:
            calls = 0
            async def search(self, p, revision):
                self.calls += 1
                started.set()
                await release.wait()
                return normalize(payload(p), p, revision)
        app.state.hotels = hotels = Hotels()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            trip = (await client.post('/api/trips', json={'preferences':guide_prefs().model_dump(mode='json')})).json()
            url = f'/api/trips/{trip["id"]}'
            body = {'expected_revision':0, 'request_id':str(uuid4())}
            task = asyncio.create_task(client.post(url + '/refresh', json=body))
            await asyncio.wait_for(started.wait(), 2)
            assert (await client.post(url + '/refresh', json=body)).status_code == 409
            assert (await client.post(url + '/activities', json={'expected_revision':0})).status_code == 409
            await client.patch(url + '/preferences', json={'expected_revision':0,'source':'slider','changes':{'controls':{'savings':99}}})
            release.set()
            assert (await task).status_code == 409
            data = (await client.get(url)).json()
            assert data['result'] is None and data['activity_result'] is None
            assert hotels.calls == 1
            # Guard is released; revised preferences can refresh.
            assert (await client.post(url + '/refresh', json={**body, 'expected_revision':1})).status_code == 200
    asyncio.run(run())


def test_expired_guide_does_not_block_hotels(tmp_path, monkeypatch):
    import travel_agent.activities as activities
    monkeypatch.setattr(activities, 'REVIEWED', datetime.now(timezone.utc) - timedelta(days=31))
    app = create_app(settings(usage_db=tmp_path / 'usage.sqlite3'))
    class Hotels:
        async def search(self, p, revision):
            return normalize(payload(p), p, revision)
    app.state.hotels = Hotels()
    with TestClient(app) as client:
        trip = client.post('/api/trips', json={'preferences':guide_prefs().model_dump(mode='json')}).json()
        data = client.post(f'/api/trips/{trip["id"]}/refresh', json={'expected_revision':0, 'request_id':str(uuid4())}).json()
        assert data['result']['status'] == 'options' and not data['results_stale']
        assert data['activity_result']['status'] == 'unavailable' and 'activities' in data['source_issues']


def test_chat_hotel_failure_saves_valid_refinement_and_does_not_reuse_failed_source(tmp_path):
    app = create_app(settings(usage_db=tmp_path / 'usage.sqlite3'))
    app.state.chat_transport = Stub([extraction([op('controls.adventure', 90, 'adventure')]), extraction()])
    class Hotels:
        calls = 0
        async def search(self, p, revision):
            self.calls += 1
            raise HotelUnavailable()
    app.state.hotels = hotels = Hotels()
    with TestClient(app) as client:
        trip = client.post('/api/trips', json={'preferences':guide_prefs().model_dump(mode='json')}).json()
        result = send(client, trip, 'more adventure')
        assert result.status_code == 200
        trip = result.json()
        assert trip['preferences']['controls']['adventure'] == 90 and trip['result'] is None
        assert trip['activity_result']['status'] == 'options' and 'hotels' in trip['source_issues']
        # Model failure remains atomic, but hotel failure preserves valid extracted preferences.
        previous = app.state.trips.get(trip['id'])
        old = normalize(payload(previous.preferences), previous.preferences, previous.revision)
        app.state.trips.commit_chat(previous, previous.preferences, old, 'test', 'test', source_issues={'hotels':'failed'})
        trip = client.get(f'/api/trips/{trip["id"]}').json()
        assert send(client, trip, 'compare again').status_code == 200
        assert hotels.calls == 2


def test_server_freshness_uses_evidence_age_not_snapshot_creation():
    p = guide_prefs()
    snapshot = normalize(payload(p), p, 0)
    snapshot.options[0].costs[0].evidence.retrieved_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    assert evidence_expired(snapshot)
    app = create_app(Settings(_env_file=None))
    session = app.state.trips.create(p)
    assert response(app.state.trips.publish(session.id, snapshot)).results_stale
    guide = activity_guide(p, 0)
    guide.options[0].costs[0].evidence.retrieved_at = datetime.now(timezone.utc) - timedelta(days=31)
    assert evidence_expired(guide)
