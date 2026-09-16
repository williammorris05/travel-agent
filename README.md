# Travel Agent

A portfolio project that turns vacation preferences into a small, explainable shortlist of travel options and helps a traveler refine their choices.

**Status:** Working fixture demo with chat commands, synchronized sliders and comparison cards, plus a separately sourced Milwaukee activity guide. Model and hotel adapters are implemented and tested offline; authenticated live validation remains pending. Choose Cheap weekend, try `/budget 200`, then select Update options. Trip comparison prices are synthetic; activity cards explicitly label published source-reviewed charges. See [API examples](docs/api.md).

Core strengths: adventurous trips and very cheap trips, including options that trade comfort or speed for lower cost or a more adventurous experience, according to the traveler's preferences.

## Proposed first experience

1. Describe the vacation you want in chat. The agent extracts preferences and asks focused follow-up questions about missing essentials.
2. Answer a clarification when essential information is missing.
3. Compare up to three destination options with reasons they fit, estimated cost breakdowns, tradeoffs, a sample itinerary, and sources where available.
4. Refine the shortlist with requests such as “less flying,” “more nature,” or “reduce the budget.”

Start with clearly labeled demo data to validate the experience. Live prices and availability require a later, verified data integration. Booking and payments are outside the first version.

## Project documents

- [Product plan](docs/product-plan.md): scope, workflow, and acceptance criteria.
- [Architecture](docs/architecture.md): proposed components and data contracts.
- [Roadmap](docs/roadmap.md): milestones and first implementation tasks.
- [Live integrations](docs/integrations.md): provider access research and sourced prices and options.
- [Adventure and budget](docs/adventure-and-budget.md): travel styles, accepted tradeoffs, and ranking behavior.
- [Preference controls](docs/preference-controls.md): sliders above chat and shared preference behavior.

The Obsidian vault under `2. Projects/Travel Agent` is the primary source of truth for planning, architecture, backlog, and decisions. The links above are navigation pointers. Begin with the [project hub](<../../../Obsidian Vault/2. Projects/Travel Agent/Travel Agent.md>) and [master plan](<../../../Obsidian Vault/2. Projects/Travel Agent/Travel Agent - Planning.md>). [AGENTS.md](AGENTS.md) defines the reference and update workflow for every implementation session.

## Development

Python/FastAPI/Pydantic backend with a React/TypeScript/Vite interface. Start with [setup, run commands, modes, and verification](docs/development.md). Pinned dependencies are included. Fixture configuration requires no paid services or credentials.

The provisional synthetic demo scope is Chicago to Milwaukee, Indiana Dunes, or Starved Rock, for one or two adults in USD. It contains no verified travel offers yet.


## Natural-language integration

L4 adapters and UI routing are implemented and tested with controlled responses. Actual model evaluation is pending a key. See [Gemini free-tier setup](docs/model-setup.md).

## Hotel integration

L6 adds a bounded SerpApi hotel adapter and hotel-only comparison cards, tested with synthetic provider responses. Live verification is pending; no real hotel search has been performed. See [hotel setup and limits](docs/hotel-setup.md). The current suite passes 102 backend tests, seven frontend tests, and the production build.

## Researched activity guide
Use Explore Milwaukee activities or /activities after setting adults. Official-source RiverWalk access and kayak rental charges are shown separately from trip totals. Source review: September 15, 2026; date-specific availability and automated activity discovery remain pending. 113 backend tests pass; the guide was checked in the browser. Planning: vault Travel Agent - L7 Activities.
