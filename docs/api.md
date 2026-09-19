# Trip API

Interactive contracts: http://127.0.0.1:8000/docs. All routes use JSON.

- `POST /api/trips` with `{ "preferences": {} }` creates a trip (201).
- `GET /api/trips/{id}` reads authoritative preferences and revision.
- `PATCH /api/trips/{id}/preferences` applies a validated partial update.

Example patch:

```json
{
  "expected_revision": 0,
  "source": "slider",
  "changes": { "controls": { "savings": 90 } }
}
```

Omitted fields survive, including nested fields. Explicit null clears nullable
values; empty lists clear lists. To replace a fixed window with unrestricted
flexibility, set dates to `{"mode":"flexible","start":null,"end":null}`.
Fixed dates use ISO calendar dates; explicit nights must match their span.
Money is a decimal string (or integer), serialized as a string; floats are rejected.
The demo accepts USD and one or two adults. Budget basis is `party` or
`per_person`; omitted basis or covered categories requires clarification.
Controls range from 0 to 100, initially null (unknown). They cannot modify hard
constraints. `chat` is a structured update source, not a natural-language endpoint.

Successful changes increment the revision; a no-op does not. Stale writers
receive 409 and should GET the trip before reconciling. Invalid requests/merged
preferences return 422 without saving anything. Missing sessions return 404.
Errors have `error.code` and `error.message`. Responses expose `missing_fields`,
`status` (`needs_clarification` or `ready`), and `results_stale`.
Ready means intake is complete; `planning_available` is true in fixture mode.

The internal result publisher rejects obsolete preference revisions. Existing
results remain visible with `results_stale=true` after preference changes.
There is no public endpoint for clients to supply prices/results.

Cost quantity is the total number of units of the stated basis (e.g. two people
for three nights = six person-nights). Party totals use quantity one. The cost
summary requires the caller's required category set; omitted or unknown costs
leave total null and expose a known subtotal. The fixture planner derives quantities
from adults/nights and requires transport, stay, activities, food, gear and fees.

Sessions live in process memory and disappear on restart. Use a single local
worker. Storage is unbounded and has no authentication or durable persistence;
hosting requires storage/lifecycle and access-control work. No model or travel
provider is called by these endpoints.

## Generate fixture options

`POST /api/trips/{id}/plan` with `{"expected_revision":0}` calculates and stores
up to three options for the current trip. Missing essentials return the trip's
clarification fields without pricing. Unsupported origins return a result with
`status=unavailable`; impossible constraints return `no_match` with exclusions.
Live mode returns 503 `live_unavailable`, with no fixture fallback.

Example creation body for the cheapest accepted two-night solo fixture:

```json
{
  "preferences": {
    "origin": "Chicago",
    "dates": {"mode": "flexible"},
    "nights": 2,
    "adults": 1,
    "budget": {
      "amount": "1000", "basis": "party",
      "covers": ["transport", "stay", "activities", "food", "gear", "fees"]
    },
    "constraints": {"shared_room_allowed": true, "camping_allowed": true},
    "controls": {"savings": 100, "adventure": 0, "transit_tolerance": 100}
  }
}
```

The first result is the synthetic Milwaukee dorm/bus option at USD 119 total.
The response includes itemized costs, all-category total, separate budget-covered
total/cap/categories, transit and remaining destination minutes, assumptions,
tradeoffs, sample itinerary, fit reasons, exclusions, and coverage gaps.
Amounts are party totals. `max_exertion` accepts low/moderate/high. Dorms, camping
and overnight transport require explicit acceptance; unsupported accessibility
requirements exclude candidates with an explanation.

PATCH changes state only; call `/plan` explicitly to refresh. All costs in the
current catalog have `evidence.kind=demo`. No authentic accommodation, fare,
permit, access, or activity availability is represented by the fixture catalog.
The connected UI supports commands, sliders and opt-in configured chat.


## Natural-language messages

POST /api/trips/{id}/messages takes message, expected_revision and expected_conversation_revision. Returns messages and conversation_revision alongside state. Model errors save nothing; 409 requires reload. 503 indicates unavailable model/allowance or live mode. Health chat_available reports configuration only. [Model setup](model-setup.md); real-model validation pending.

L5: concurrent messages for one session return 409 before a second model call. Ambiguous interpretations retain all saved preferences and return clarification. Invalid/duplicate-key model JSON returns 502 without a state change.

L6: configured live mode routes POST /trips/{id}/plan and model-driven planning to SerpApi. Results may contain kind=hotel with hotel_cost; total_cost.total remains null and missing categories stay explicit. Health hotel_search_configured indicates configuration only. Provider failures return 503 hotel_unavailable, retain previous results and never substitute fixtures. See docs/hotel-setup.md.

L7: POST /trips/{id}/activities takes expected_revision and returns a separate activity_result plus activities_stale. Party size is required. Published source-reviewed listings are available independently of fixture/live trip search and never replace failed hotel results. Model intent activities and /activities route to this guide. Source facts expire for new generation after 30 days; no automated external fetch occurs.

L8: POST /trips/{id}/refresh takes expected_revision and request_id (UUID). It returns independently usable trip/hotel and activity results, with source_issues for partial failure. Completed request IDs deduplicate external work for the session; concurrent requests return 409. The per-trip 100-refresh bound returns 429. results_stale and activities_stale include evidence age and failed-refresh notices, not just preference revisions. A hotel failure during chat now returns partial state with validated preferences saved; model failures remain atomic. See [reliability](reliability.md).
