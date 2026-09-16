"""Synthetic provider payloads: these tests do not establish live access."""
import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from test_chat import Stub, extraction, op, send
from travel_agent.contracts import Preferences, PreferenceUpdate
from travel_agent.main import create_app
from travel_agent.providers.serpapi_hotels import HotelUnavailable, SerpApiHotels, normalize
from travel_agent.settings import Settings


def prefs():
    start = date.today() + timedelta(days=30)
    return Preferences(origin='Chicago', dates={'mode':'fixed', 'start':str(start), 'end':str(start + timedelta(days=2))}, adults=2,
                       budget={'amount':'500', 'basis':'party', 'covers':['stay','transport','food','activities','gear','fees']},
                       constraints={'private_room':True, 'accessibility':['step free']})


def payload(preferences=None):
    p = preferences or prefs()
    return {'search_metadata': {'status':'Success'}, 'search_parameters':{
        'engine':'google_hotels', 'q':'Hotels in Milwaukee Wisconsin', 'currency':'USD',
        'check_in_date':str(p.dates.start), 'check_out_date':str(p.dates.end), 'adults':p.adults, 'children':0},
        'properties':[{'name':'Synthetic test hotel', 'property_token':'test-hotel', 'link':'https://example.com/hotel',
                       'total_rate':{'extracted_lowest':240}, 'rate_per_night':{'extracted_lowest':99}}]}


def settings(**changes):
    return Settings(_env_file=None, data_mode='live', serpapi_api_key='test-secret', hotel_max_calls=2, **changes)


def test_whole_stay_basis_provenance_unknown_fees_and_constraints():
    p = prefs()
    snapshot = normalize(payload(p), p, 4)
    offer = snapshot.options[0]
    assert offer.kind == 'hotel' and offer.hotel_cost.total == Decimal('240')
    assert offer.costs[0].quantity == 1  # Not doubled for two adults or two nights.
    assert offer.total_cost.total is None and 'fees' in offer.total_cost.missing_categories
    assert offer.budget_cost is None and offer.score is None
    assert offer.costs[0].evidence.search_dates == p.dates
    assert offer.costs[0].evidence.kind == 'observed_search_price'
    assert p.constraints.private_room is True and p.constraints.accessibility == ['step free']


@pytest.mark.parametrize('change', [
    {'total_rate':{}}, {'total_rate':{'extracted_lowest':True}}, {'total_rate':{'extracted_lowest':-1}},
    {'total_rate':{'extracted_lowest':Decimal('1.123')}}, {'total_rate':{'extracted_lowest':Decimal('NaN')}},
    {'link':'javascript:alert(1)'}, {'link':'https://serpapi.com/search?api_key=secret'},
    {'link':'https://user:secret@example.com'}, {'property_token':None},
])
def test_missing_price_or_invalid_source_omitted_without_invented_total(change):
    body = payload()
    body['properties'][0].update(change)
    result = normalize(body, prefs(), 0)
    assert result.status == 'no_match' and result.options == []
    assert any('omitted' in gap for gap in result.coverage_gaps)


@pytest.mark.parametrize('field,value', [('currency','EUR'), ('adults',1), ('check_in_date','2020-01-01')])
def test_mismatched_query_context_rejected(field, value):
    body = payload()
    body['search_parameters'][field] = value
    with pytest.raises(ValueError):
        normalize(body, prefs(), 0)


def test_empty_results_and_cheapest_three_unique_observed_stays():
    body = payload()
    template = body['properties'][0]
    body['properties'] = [{**template, 'property_token':str(i), 'total_rate':{'extracted_lowest':i*10}} for i in [4,3,2,1]]
    result = normalize(body, prefs(), 0)
    assert [o.hotel_cost.total for o in result.options] == [10,20,30]
    body['properties'] = []
    assert normalize(body, prefs(), 0).status == 'no_match'


def test_transport_bounds_decimal_precision_and_secret_redaction(caplog):
    async def run():
        requests = []
        def handler(request):
            requests.append(request)
            body = payload()
            body['properties'][0]['total_rate']['extracted_lowest'] = 123.45
            return httpx.Response(200, json=body)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = SerpApiHotels(settings(), client)
            results = await asyncio.gather(provider.search(prefs(),0), provider.search(prefs(),1), provider.search(prefs(),2), return_exceptions=True)
            assert sum(isinstance(r, HotelUnavailable) for r in results) == 1
            assert len(requests) == provider.calls == 2
            assert results[0].options[0].hotel_cost.total == Decimal('123.45')
            assert 'test-secret' not in results[0].model_dump_json()
            assert requests[0].url.params['adults'] == '2'
            assert 'next_page_token' not in requests[0].url.params
    with caplog.at_level(logging.DEBUG):
        asyncio.run(run())
    assert 'test-secret' not in caplog.text


@pytest.mark.parametrize('status,body', [(429,{}),(500,{}),(200,{'error':'test-secret'}),(200,[])])
def test_failures_spend_one_attempt_no_retry_no_sensitive_error(status, body):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(status,json=body))) as client:
            provider = SerpApiHotels(settings(),client)
            with pytest.raises(HotelUnavailable) as caught:
                await provider.search(prefs(),0)
            assert provider.calls == 1 and 'test-secret' not in str(caught.value)
    asyncio.run(run())


def test_timeout_and_flexible_dates_do_not_invent_prices():
    async def run():
        def timeout(request):
            raise httpx.ReadTimeout('secret response')
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            provider = SerpApiHotels(settings(),client)
            p = prefs()
            p.dates = {'mode':'flexible'}
            result = await provider.search(p,0)
            assert result.status == 'unavailable' and provider.calls == 0
            with pytest.raises(HotelUnavailable):
                await provider.search(prefs(),0)
            assert provider.calls == 1
    asyncio.run(run())


def test_api_search_date_correction_stale_results_and_chat():
    app = create_app(settings())
    queried = []
    class Provider:
        async def search(self, preferences, revision):
            queried.append(preferences.model_copy(deep=True))
            return normalize(payload(preferences), preferences, revision)
    app.state.hotels = Provider()
    app.state.chat_transport = Stub([extraction([op('controls.savings',100,'cheaper')]), extraction(intent='explain')])
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={'preferences':prefs().model_dump(mode='json')}).json()
        trip = client.post(f'/api/trips/{trip["id"]}/plan',json={'expected_revision':0}).json()
        assert trip['result']['options'][0]['kind'] == 'hotel'
        changed = client.patch(f'/api/trips/{trip["id"]}/preferences',json={
            'expected_revision':0,'source':'form','changes':{'adults':1}}).json()
        assert changed['results_stale'] and len(queried) == 1
        trip = send(client,changed,'cheaper').json()
        assert queried[-1].adults == 1 and not trip['results_stale']
        assert 'hotel leads' in trip['messages'][-1]['text']
        assert 'synthetic' not in trip['messages'][-1]['text']
        assert trip['preferences']['constraints']['private_room']
        trip = send(client, trip, 'Explain these hotels').json()
        assert len(queried) == 2  # Same dates/party reuse recent session evidence.
        start = date.today() + timedelta(days=60)
        trip = client.patch(f'/api/trips/{trip["id"]}/preferences', json={'expected_revision':trip['revision'],
                            'source':'form','changes':{'dates':{'mode':'fixed','start':str(start),'end':str(start+timedelta(days=2))}}}).json()
        trip = client.post(f'/api/trips/{trip["id"]}/plan',json={'expected_revision':trip['revision']}).json()
        assert queried[-1].dates.start == start and len(queried) == 3


def test_late_hotel_search_rejected_after_slider_update():
    app = create_app(settings())
    with TestClient(app) as client:
        trip = client.post('/api/trips',json={'preferences':prefs().model_dump(mode='json')}).json()
        class Racing:
            async def search(self, preferences, revision):
                app.state.trips.update(trip['id'], PreferenceUpdate(expected_revision=0,source='slider',changes={'controls':{'adventure':80}}))
                return normalize(payload(preferences), preferences, revision)
        app.state.hotels = Racing()
        assert client.post(f'/api/trips/{trip["id"]}/plan',json={'expected_revision':0}).status_code == 409
        saved = app.state.trips.get(trip['id'])
        assert saved.result is None and saved.preferences.controls.adventure == 80
