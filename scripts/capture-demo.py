"""Capture a no-network API walkthrough from actual application responses."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from fastapi.testclient import TestClient
from travel_agent.main import create_app
from travel_agent.settings import Settings


def capture():
    settings = Settings(_env_file=None, data_mode='fixture', model_provider='disabled',
                        model_max_calls=0, hotel_max_calls=0)
    lines = ['# Captured fixture API walkthrough', '',
             f'Captured {datetime.now(timezone.utc).date()} with `scripts/capture-demo.py`.',
             'Actual in-process API responses; no model or travel network calls. All trip prices are synthetic.', '']
    with TestClient(create_app(settings)) as client:
        trip = client.post('/api/trips', json={'preferences': {
            'origin':'Chicago', 'dates':{'mode':'flexible'}, 'nights':2, 'adults':1,
            'budget':{'amount':'500','basis':'party','covers':['transport','stay','activities','food','gear','fees']},
            'controls':{'savings':100,'adventure':0,'transit_tolerance':100},
            'constraints':{'private_room':False,'shared_room_allowed':True,'camping_allowed':True,'overnight_transport_allowed':False},
        }}).json()
        url = f'/api/trips/{trip["id"]}'
        stages = [
            ('Cheap with basic stays and long travel accepted', {}),
            ('Adventure prioritized; saving priority reduced', {'controls':{'adventure':100,'savings':30}}),
            ('Private room required; adventure preserved', {'constraints':{'private_room':True}}),
            ('Less transit preferred; nights unchanged', {'controls':{'transit_tolerance':0}}),
            ('Zero budget: honest no-match', {'budget':{'amount':'0'}}),
        ]
        for title, changes in stages:
            if changes:
                reply = client.patch(url + '/preferences', json={'expected_revision':trip['revision'],'source':'form','changes':changes})
                reply.raise_for_status()
                trip = reply.json()
                assert trip['results_stale']
            reply = client.post(url + '/plan', json={'expected_revision':trip['revision']})
            reply.raise_for_status()
            trip = reply.json()
            result = trip['result']
            assert result['preference_revision'] == trip['revision'] and not trip['results_stale']
            if trip['preferences']['constraints']['private_room']:
                assert all(o['accommodation'] == 'private_room' for o in result['options'])
            lines.extend([f'## {title}', '', f'Revision {trip["revision"]}; result `{result["status"]}`; two nights, one adult.', '',
                          '| Option | Party total (USD) | Transit minutes | Accommodation |', '| --- | --- | --- | --- |'])
            for option in result['options']:
                lines.append(f'| {option["title"]} | {option["total_cost"]["total"]} | {option["transit_minutes"]} | {option["accommodation"]} |')
            if not result['options']:
                lines.append('| No feasible synthetic option | — | — | — |')
            lines.append('')
        assert trip['result']['status'] == 'no_match'
        # Restore a budget so independent activity evidence is visible.
        trip = client.patch(url + '/preferences', json={'expected_revision':trip['revision'],'source':'form','changes':{'budget':{'amount':'500'}}}).json()
        reply = client.post(url + '/refresh', json={'expected_revision':trip['revision'],'request_id':str(uuid4())})
        reply.raise_for_status()
        trip = reply.json()
        guide = trip['activity_result']
        lines.extend(['## Separate activity evidence', '', f'Guide status: `{guide["status"]}`. Published charges do not verify dates or availability.', ''])
        for option in guide['options']:
            evidence = option['costs'][0]['evidence']
            lines.append(f'- {option["title"]}: USD {option["activity_cost"]["known_subtotal"]} known activity charges; '
                         f'whole-trip total unknown. [Source]({evidence["url"]}); reviewed {evidence["retrieved_at"]}.')
        lines.extend(['', *guide['coverage_gaps'], '', 'Natural-language and authenticated hotel journeys remain unverified.'])
    (ROOT / 'docs' / 'demo-transcript.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Captured docs/demo-transcript.md; fixture and constraint assertions passed.')


if __name__ == '__main__':
    capture()
