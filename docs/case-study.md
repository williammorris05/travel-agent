# Travel Agent: exposing the cost of comfort and speed

## Problem

A travel planner should not assume faster journeys or more comfortable rooms are
always better. Accepting a dorm and a long bus ride can make a cheap trip possible.
Adventure is independent: raising it must not remove a private-room requirement.

## Approach

This Python-first prototype joins chat, commands and sliders through one versioned
preference model. Python filters hard constraints, computes decimal costs and ranks
explicit candidates. A bounded model adapter extracts changes; it cannot invent
totals or invoke arbitrary tools.

The synthetic catalog includes basic stays, slow journeys, camping, missing costs
and impossible timing. The cheap preset favors a USD 119 dorm/bus trip; requiring a
private room rules it out. These reproducible examples are not current travel offers.

The hotel adapter preserves observed whole-stay prices while marking other trip
costs unknown. A separate reviewed guide includes a free walk and kayak rental.
Neither published charges nor observed rates imply confirmed availability. Their
evidence remains separate from synthetic trip totals.

## Engineering decisions

- Typed partial updates and revision checks synchronize chat and sliders.
- Application code owns cost arithmetic, with explicit unknowns.
- SQLite attempt reservations survive restart and contention; failed calls count.
- Source failures return partial results, not fabricated replacements.
- A compact explicit workflow makes orchestration inspectable.

## Results and limits

See the [evaluation report](evaluation.md), [architecture](implementation.md) and
[demo](demo.md). Controlled checks demonstrate backend and agent engineering, not
verified real-world recommendation quality. Real-model and authenticated hotel
checks remain pending; activity schedules are not automated and no user study ran.

Next steps are a bounded real conversation and hotel query, source-price comparison,
and a permitted activity schedule source. Hosting also needs authentication and
durable shared sessions. The dependable fixture path remains useful for reviewers
without provider accounts.
