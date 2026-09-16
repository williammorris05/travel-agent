# Travel Agent build workflow

The user requires most planning to live in the vault and be frequently referenced while building.

Vault project: `C:/Users/willi/OneDrive/Documents/Obsidian Vault/2. Projects/Travel Agent`

## Every implementation session

Read `Travel Agent.md`, `Travel Agent - Planning.md`, `Travel Agent - Build Backlog.md`, `Travel Agent - Decision Log.md`, and the latest `Travel Agent - Build Log.md` handoff. Before implementing a feature, read its relevant specification in the same folder. Revisit it when behavior, contracts, scope, or provider assumptions change.

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

Current phase: L3 connected demo interface complete, L4 next. Read `Travel Agent - L3 Interface.md` for UI behavior and evidence. Read `Travel Agent - L2 Fixture Ranking.md` for scoring, constraints and evidence, `Travel Agent - L1 Contracts.md` for state semantics, and `Travel Agent - L0 Scaffold.md` for setup. A real model and live travel integrations are not configured.


L4 update: integration is now built; real-model validation is pending. Read Travel Agent - L4 Chat Integration.md and Travel Agent - Free Model APIs.md. Do not mark L4 complete without the real conversation gate.

L5 update: read Travel Agent - L5 Hardening.md. Deterministic reliability hardening passes 80 backend tests; L4/L5 real-model gates remain pending.

L6 update: read Travel Agent - L6 Hotel Integration.md. Hotel adapter and UI pass 102 backend/seven frontend tests; user deferred key setup. Live gate remains pending. Preserve separate hotel-only evidence and whole-trip unknowns.

L7 update: read Travel Agent - L7 Activities.md. Source-reviewed guide passes 113 backend tests; automated activity schedules remain pending. Never refresh REVIEWED without rechecking official sources.
