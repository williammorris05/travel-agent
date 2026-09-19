# Three-minute fixture walkthrough

Follow [setup](development.md), keeping fixture mode, model provider disabled and
both allowances zero. No API key is required.

1. Select **Cheap weekend**: Chicago, two nights, one adult, USD 500 party cap for
   all costs. The leading synthetic Milwaukee dorm/bus trip costs USD 119 with ten
   hours round-trip transit. Expand **Cost breakdown & evidence** to see its basis.
2. Raise **Adventure**, release it, then **Update options**. Saved preferences
   change before results refresh. Compare exertion, accommodation and destination
   time. The budget cap and comfort requirements remain intact.
3. Send `/private yes`, then `/plan`. All returned cards must respect a private
   room. Compare with the original cheap dorm trip. **Adventure + private room**
   is a full preset demonstrating the same constraint.
4. Move **Travel time** toward less transit and refresh. This changes tolerance,
   not vacation length. Send `/dates 2027-06-01 2027-06-04` to demonstrate date
   correction: the separate night count clears and old results become stale.
5. Select **Refresh options + activity guide**. Trip and activity prices remain
   separate. Expand **Sources, equipment & limits** for official links, source
   timestamps and missing costs. The guide expires 30 days after review; a refresh
   does not recheck websites or renew its timestamp.
6. Send `/budget 0` and `/plan`: expect no feasible trip, with exclusions rather
   than invented bargains. Load a sample to recover.

Keyboard: Tab to controls, use arrows to adjust sliders, Tab away to save. Enter
sends commands; Shift+Enter inserts a newline. Evidence disclosures and source links
are focusable. Intermediate drag events do not call providers.

This demonstrates structured commands, not natural-language AI. Real chat requires
[model setup](model-setup.md); hotels require [hotel setup](hotel-setup.md). Their
live gates remain pending. Automated activity schedules are unimplemented.

The [captured API replay](demo-transcript.md) records actual deterministic results,
prices and revisions. It can be regenerated with `scripts/capture-demo.py` using
the project Python environment; it makes no external calls.
