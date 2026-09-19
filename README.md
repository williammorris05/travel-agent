# Travel Agent

A Python travel-planning demo that makes cheap, adventurous tradeoffs visible.
Accept a dorm and a long bus ride, prioritize exploration, or require a private
room: the shortlist changes while your hard constraints remain intact.

**Try it without keys:** [install and run](docs/development.md), then follow the
[three-minute demo](docs/demo.md). Requires Python 3.12, Node 24 and pnpm 11.19.0.

## What works

| Capability | Evidence and scope |
| --- | --- |
| Trip comparison | Eight synthetic candidates; Chicago to Milwaukee, Indiana Dunes or Starved Rock; one/two adults, USD |
| Commands and sliders | No model needed; adventure, savings and transit tolerance share versioned backend state |
| Natural-language interpretation | Gemini/OpenAI adapters tested with controlled responses; real-model validation pending |
| Hotel search | SerpApi integration tested with synthetic payloads; authenticated price verification pending |
| Activity guide | Milwaukee RiverWalk and kayak rental reviewed September 15, 2026; published charges, not inventory; expires after 30 days |
| Reliability | Persistent attempt limits, revision checks, refresh deduplication, partial results and stale-evidence warnings |

Default **fixture mode** uses invented trip prices and routes. The separate activity
guide contains sourced facts but does not check dates, closures or bookable slots.
There is no booking, payment, account system or global route engine. This is a local
demo, not a deployed travel service.

## Engineering focus

FastAPI and Pydantic validate partial updates; Python owns money arithmetic,
constraint filtering and ranking. A model proposes typed preference changes but
cannot write prices or invoke arbitrary tools. React displays the saved state used
by the planner. SQLite stores provider attempt counts; sessions remain in memory.

- [Implementation architecture](docs/implementation.md)
- [Evaluation report and remaining gates](docs/evaluation.md)
- [Portfolio case study](docs/case-study.md)
- [API reference](docs/api.md)
- [Model setup](docs/model-setup.md), [hotel setup](docs/hotel-setup.md), [limits and freshness](docs/reliability.md)

Product planning and decisions live in a separate Obsidian vault. These repository
docs provide a self-contained setup and implementation reference; the vault is not
required to run the demo. Contributors with vault access should follow [AGENTS.md](AGENTS.md).
