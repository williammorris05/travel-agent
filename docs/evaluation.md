# Evaluation report — September 18, 2026

**Local fixture reproduction passed. Full live release gate remains open.**
These results describe the working tree containing L8/L9 changes on top of
`0820605`; they do not claim a published release or verified provider access.

## Reproduction evidence

On Windows with Python 3.12.14, Node 24.19.0 and pnpm 11.19.0, copied source into an
isolated directory excluding `.env`, existing environments, node_modules, build
outputs and caches. Created a fresh Python venv, installed requirements.lock and
installed frontend dependencies with `--frozen-lockfile`. Registry access was
needed; offline caches were insufficient. No dependency versions were upgraded.

In that isolated copy:

- **123 backend tests passed** in 5.14 seconds of pytest execution.
- **Eight frontend tests passed**; TypeScript checking and Vite production build passed.
- `pip check` reported no broken requirements.
- Uvicorn started and served fixture health over HTTP with chat disabled.
- The no-network [capture script](../scripts/capture-demo.py) reproduced
  [the comparison transcript](demo-transcript.md), including constraint assertions.

This was a fresh dependency environment and source copy, not a fresh remote clone.
The main working environment also passed 123 backend tests and dependency checks.
Two upstream FastAPI/Starlette test-client deprecation warnings remain.

## Scenario evidence

The IDs correspond to the vault evaluation plan. “Controlled” means deterministic
domain/API tests or synthetic provider/model responses, not live model evaluation.

| Scenario | Result | Evidence |
| --- | --- | --- |
| E01 multi-fact intake | Controlled pass; real model pending | test_chat.py multi-turn intake |
| E02 missing essentials/budget basis | Controlled pass | test_contracts.py ambiguous budget; test_chat.py clarification |
| E03 date correction | Controlled pass; real extraction pending | test_planning.py duration/pricing; test_hotels.py queried dates; frontend commands tests |
| E04 chat/slider consistency | Controlled pass; UI refinement checked | test_chat.py multi-turn; test_contracts.py revisions |
| E05 cheap dorm/long journey | Fixture pass | test_planning.py E05–E09; captured USD 119 winner |
| E06 full cost vs cheap room | Fixture pass | test_planning.py remote-room complete costs |
| E07 adventure with private room | Fixture pass; UI checked | test_planning.py; replay USD 338 private-room winner |
| E08 camping gear | Fixture pass | test_planning.py included gear/unknown-cost cases |
| E09 short stay/long transit | Fixture pass | test_planning.py impossible timing |
| E10 no feasible candidate | Controlled pass | test_planning.py no-match; replay zero budget |
| E11 activity price semantics | Controlled pass; schedules pending | test_activities.py; source-reviewed cards explicitly lack slots |
| E12 unknown fees | Controlled pass | test_contracts.py, test_planning.py, test_hotels.py missing costs |
| E13 source/quota failure | Controlled pass; live gate pending | test_hotels.py and test_l8.py partial failures, restart, process contention |
| E14 malicious retrieved text | Controlled boundary pass | test_hardening.py source prose exclusion; hotel card escaping |
| E15 late result | Controlled pass | contract/chat/hotel/L8 revision tests |
| E16 repeated sliders | Controlled pass; L3 pointer check | test_l8.py no provider calls; keyboard save/stale rechecked in L9 |
| E17 cheap/low exertion | Fixture and guide pass | test_planning.py E17; test_activities.py low exertion |
| E18 keyboard interaction | L3 manual journey; L9 targeted recheck | Enter command, arrow/Tab slider save, focus retention, evidence disclosure |

Test modules live in `backend/tests`; frontend checks are in `frontend/tests`.
L9 browser checks at localhost:5173 confirmed `/private yes` marked results stale,
`/plan` returned only private-room options, keyboard slider changes preserved that
constraint, and combined refresh displayed separate source-reviewed activity cards.
The official-source disclosure retained its September 15 review date and missing
costs. A screenshot was captured in the task; the durable text/API demo is in the repo.
L3 recorded desktop and 390px checks; L9 did not repeat a full responsive/accessibility audit.

## Limits and release decision

No real model/provider calls occurred. No live latency, token usage, authenticated
hotel-price correspondence, activity schedule access, recommendation quality or
user-satisfaction measurement is available. Test-suite execution time is not user
request latency. Controlled injection checks are not proof against every attack.

The fixture demonstration is reproducible and ready for local portfolio review.
The full L9 live gate requires the pending L4/L5 conversation checks, L6 hotel/source
comparison, L7 automated schedules and combined L8 live journey. Hosting also needs
authentication and shared session design. No deployment or GitHub push was performed.
