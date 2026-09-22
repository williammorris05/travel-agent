# Travel Agent build workflow

The user requires most planning to live in the vault and be frequently referenced while building.

Vault project: `C:/Users/willi/OneDrive/Documents/Obsidian Vault/2. Projects/Portfolio/Travel Agent`

## Every implementation session

Read `Travel Agent.md`, `Notes/Travel Agent - Planning.md`, `Notes/Travel Agent - Build Backlog.md`, `Notes/Travel Agent - Decision Log.md`, and the latest `Dev Log/Travel Agent - Build Log.md` handoff. Before implementing a feature, read its relevant specification in the project’s Specs folder. Revisit it when behavior, contracts, scope, or provider assumptions change.

Select a concrete backlog item and mark it in progress. At meaningful checkpoints and session end, update its status and the Build Log with changes, validation evidence, limitations, and the next step. Record material decisions in the Decision Log and update the hub's current focus when it changes. Reference the relevant vault note in implementation handoffs.

The vault is the primary planning source of truth. Repository docs are navigation pointers, not competing specifications. Keep actual code reference, setup commands, and public project overview in the repository. If the vault is unavailable, report it rather than silently relying on outdated assumptions.

## Implementation principles

- Emphasize Python/backend and agent engineering, as requested by the user.
- Distinguish accepted decisions, proposed defaults, fixture behavior, and verified live behavior.
- Preserve hard constraints and synchronize chat/sliders through shared state.
- Keep price arithmetic and constraint checks in application code; ground explanations in evidence.
- Verify provider access and free quotas with project accounts before claiming an integration works.
- Do not commit credentials, personal travel data, or sensitive provider responses.
- Use meaningful checks appropriate to the change. Do not mark a work item complete on scaffolding alone.
- Continue routine authorized reversible work without adding approval steps. These instructions require reference and documentation, not user confirmation for each item.

Current phase: L9 fixture reproduction and presentation delivered; full live release pending. Start with `Notes/Travel Agent - L9 Demo Release.md`. Read `Notes/Travel Agent - L3 Interface.md` for UI behavior, `Notes/Travel Agent - L2 Fixture Ranking.md` for scoring, and `Notes/Travel Agent - L1 Contracts.md` for state semantics. Model/hotel adapters are implemented but authenticated validation remains pending; automated activity schedules are unimplemented.


L4 update: integration is now built; real-model validation is pending. Read Travel Agent - L4 Chat Integration.md and Travel Agent - Free Model APIs.md. Do not mark L4 complete without the real conversation gate.

L5 update: read Travel Agent - L5 Hardening.md. Deterministic reliability hardening passes 80 backend tests; L4/L5 real-model gates remain pending.

L6 update: read Travel Agent - L6 Hotel Integration.md. Hotel adapter and UI pass 102 backend/seven frontend tests; user deferred key setup. Live gate remains pending. Preserve separate hotel-only evidence and whole-trip unknowns.

L7 update: read Travel Agent - L7 Activities.md. Source-reviewed guide passes 113 backend tests; automated activity schedules remain pending. Never refresh REVIEWED without rechecking official sources.

L8 update: read Travel Agent - L8 Reliability.md before changing quotas, freshness or refresh flows. SQLite counts persist across restarts; sessions remain single-worker and ephemeral. Combined live validation remains pending. See docs/reliability.md for actual operation and API semantics.

L9 update: read Travel Agent - L9 Demo Release.md for reproduction evidence and remaining gates. Public setup, architecture, evaluation, demo transcript and case study are in docs. The isolated fixture install passes 123 backend/eight frontend tests. Full live release remains pending; do not erase these boundaries when presenting the project.
