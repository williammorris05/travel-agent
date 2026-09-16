import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from travel_agent.chat import Interpretation, apply_operations
from travel_agent.contracts import PreferenceUpdate, Preferences
from travel_agent.main import create_app
from travel_agent.providers.gemini_transport import GeminiTransport
from travel_agent.providers.openai_transport import ModelUnavailable, OpenAITransport
from travel_agent.sessions import SessionStore
from travel_agent.settings import Settings


def extraction(operations=(), clarify=(), intent="refine"):
    return json.dumps({"operations": list(operations), "clarify": list(clarify), "intent": intent})


def op(path, value, quote):
    return {"path": path, "value_json": json.dumps(value), "quote": quote}


class Stub:
    """Test-only extraction outputs, never selected by production settings."""
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.prompts = []

    async def complete_json(self, prompt, schema):
        self.prompts.append(prompt)
        return next(self.outputs)


def send(client, trip, text):
    return client.post(f'/api/trips/{trip["id"]}/messages', json={
        "expected_revision": trip["revision"], "expected_conversation_revision": trip["conversation_revision"], "message": text})


def test_multi_turn_intake_clarification_plan_correction_and_slider():
    app = create_app(Settings(_env_file=None))
    first = 'Chicago, 2 nights, flexible dates, one adult, USD 500. Dorms are fine.'
    app.state.chat_transport = stub = Stub([
        extraction([op("origin", "Chicago", "Chicago"), op("dates", {"mode": "flexible"}, "flexible dates"),
                    op("nights", 2, "2 nights"), op("adults", 1, "one adult"),
                    op("budget", {"amount": "500"}, "USD 500"), op("constraints.shared_room_allowed", True, "Dorms are fine")], intent="plan"),
        extraction([op("budget.basis", "party", "whole party"), op("budget.covers", ["transport", "stay", "activities", "food", "gear", "fees"], "all costs")], intent="plan"),
        extraction([op("dates", {"mode": "fixed", "start": "2027-06-01", "end": "2027-06-04"}, "June 1-4, 2027")]),
        extraction([op("controls.savings", 100, "cheaper")]),
    ])
    with TestClient(app) as client:
        trip = client.post('/api/trips', json={}).json()
        result = send(client, trip, first)
        assert result.status_code == 200
        trip = result.json()
        assert trip['preferences']['origin'] == 'Chicago'
        assert 'whole party or per person' in trip['messages'][-1]['text']
        assert trip['result'] is None
        trip = send(client, trip, 'For the whole party, including all costs.').json()
        assert trip['result']['status'] == 'options'
        assert '119.00' in trip['messages'][-1]['text']
        trip = send(client, trip, 'Change to June 1-4, 2027.').json()
        assert trip['preferences']['nights'] is None
        assert trip['result']['options'][0]['nights'] == 3
        assert trip['preferences']['constraints']['shared_room_allowed'] is True
        trip = client.patch(f'/api/trips/{trip["id"]}/preferences', json={"expected_revision": trip['revision'], "source": "slider", "changes": {"controls": {"adventure": 70}}}).json()
        trip = send(client, trip, 'Make it cheaper.').json()
        assert trip['preferences']['controls']['adventure'] == 70
        assert trip['preferences']['controls']['savings'] == 100
        assert trip['preferences']['budget']['amount'] == '500'
        assert trip['conversation_revision'] == 4
        assert 'For the whole party' in stub.prompts[-1]


@pytest.mark.parametrize('raw', ['broken', extraction([op('origin','Paris','not in message')]),
    extraction([op('adults',True,'yes')]), extraction([op('adults',3,'yes')]),
    extraction([op('budget.amount',0.1,'yes')]),
    extraction([op('origin','Chicago','yes'),op('origin','Boston','yes')]),
    extraction([op('budget',{'amount':'5'},'yes'),op('budget.amount','6','yes')])])
def test_invalid_model_output_saves_nothing(raw):
    app = create_app(Settings(_env_file=None))
    app.state.chat_transport = Stub([raw])
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={}).json()
        assert send(client,trip,'yes').status_code == 502
        assert client.get(f'/api/trips/{trip["id"]}').json() == trip


def test_concurrent_context_change_rejects_late_model_reply():
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={}).json()
        class RacingStub:
            async def complete_json(self, prompt, schema):
                app.state.trips.update(trip['id'], PreferenceUpdate(expected_revision=0, source='slider', changes={'controls':{'adventure':90}}))
                return extraction([op('origin','Chicago','Chicago')])
        app.state.chat_transport = RacingStub()
        assert send(client,trip,'Chicago').status_code == 409
        saved = app.state.trips.get(trip['id'])
        assert saved.messages == [] and saved.preferences.origin is None
        assert saved.preferences.controls.adventure == 90


def test_noop_conversation_revisions_reject_duplicate_submissions():
    app = create_app(Settings(_env_file=None))
    app.state.chat_transport = Stub([extraction(clarify=['meaning'])])
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={}).json()
        reply = send(client,trip,'hello').json()
        assert reply['revision'] == 0 and reply['conversation_revision'] == 1
        assert send(client,trip,'hello').status_code == 409


def test_unconfigured_live_and_empty_message_fail_without_model_calls():
    for mode in ['fixture','live']:
        app = create_app(Settings(_env_file=None,data_mode=mode))
        with TestClient(app) as client:
            trip = client.post('/api/trips',json={}).json()
            assert send(client,trip,'Find a trip').status_code == 503
            assert send(client,trip,' ').status_code == 422
            assert client.get('/api/health').json()['chat_available'] is False


@pytest.mark.parametrize('provider,transport_type', [('gemini',GeminiTransport),('openai',OpenAITransport)])
def test_transport_schema_credentials_limits_and_no_retry(provider,transport_type):
    async def exercise():
        requests=[]
        raw=extraction(clarify=['meaning'])
        def handler(request):
            requests.append(request)
            if provider == 'gemini':
                return httpx.Response(200,json={'status':'completed','steps':[{'type':'model_output','content':[{'type':'text','text':raw}]}]})
            return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':raw}]}]})
        settings=Settings(_env_file=None,model_provider=provider,model_name='test-model',model_max_calls=1,
                          gemini_api_key='test-not-real',openai_api_key='test-not-real')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter=transport_type(settings,client)
            assert await adapter.complete_json('test prompt',Interpretation.model_json_schema()) == raw
            with pytest.raises(ModelUnavailable):
                await adapter.complete_json('second',{})
        assert len(requests)==1
        body=json.loads(requests[0].content)
        assert body['store'] is False and 'tools' not in body
        assert 'test-not-real' not in str(requests[0].url)
        assert 'test-not-real' not in json.dumps(body)
    asyncio.run(exercise())


@pytest.mark.parametrize('body', [{'status':'incomplete'}, {'status':'completed','steps':[]}, {'status':'completed','steps':[{'type':'model_output','content':[{'type':'refusal'}]}]}])
def test_gemini_partial_or_refused_response_is_unavailable(body):
    async def exercise():
        settings=Settings(_env_file=None,model_provider='gemini',model_name='test',model_max_calls=1,gemini_api_key='test')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=body))) as client:
            with pytest.raises(ModelUnavailable):
                await GeminiTransport(settings,client).complete_json('test',{})
    asyncio.run(exercise())


def test_transport_provider_error_does_not_expose_response_body():
    async def exercise():
        settings=Settings(_env_file=None,model_provider='gemini',model_name='test',model_max_calls=1,gemini_api_key='test-secret')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(429,text='test-secret'))) as client:
            with pytest.raises(ModelUnavailable) as caught:
                await GeminiTransport(settings,client).complete_json('test',{})
            assert 'test-secret' not in str(caught.value)
    asyncio.run(exercise())
