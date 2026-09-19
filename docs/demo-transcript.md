# Captured fixture API walkthrough

Captured 2026-09-18 with `scripts/capture-demo.py`.
Actual in-process API responses; no model or travel network calls. All trip prices are synthetic.

## Cheap with basic stays and long travel accepted

Revision 0; result `options`; two nights, one adult.

| Option | Party total (USD) | Transit minutes | Accommodation |
| --- | --- | --- | --- |
| Slow bus and self-guided city exploration | 119.00 | 600 | dorm |
| Dunes camping and self-guided hiking | 263.00 | 360 | camping |
| Dunes trails with a private room | 338.00 | 300 | private_room |

## Adventure prioritized; saving priority reduced

Revision 1; result `options`; two nights, one adult.

| Option | Party total (USD) | Transit minutes | Accommodation |
| --- | --- | --- | --- |
| Dunes camping and self-guided hiking | 263.00 | 360 | camping |
| Remote bargain room with costly transfers | 478.00 | 540 | private_room |
| Slow bus and self-guided city exploration | 119.00 | 600 | dorm |

## Private room required; adventure preserved

Revision 2; result `options`; two nights, one adult.

| Option | Party total (USD) | Transit minutes | Accommodation |
| --- | --- | --- | --- |
| Dunes trails with a private room | 338.00 | 300 | private_room |
| Remote bargain room with costly transfers | 478.00 | 540 | private_room |
| Fast train and private city stay | 433.00 | 180 | private_room |

## Less transit preferred; nights unchanged

Revision 3; result `options`; two nights, one adult.

| Option | Party total (USD) | Transit minutes | Accommodation |
| --- | --- | --- | --- |
| Dunes trails with a private room | 338.00 | 300 | private_room |
| Remote bargain room with costly transfers | 478.00 | 540 | private_room |
| Fast train and private city stay | 433.00 | 180 | private_room |

## Zero budget: honest no-match

Revision 4; result `no_match`; two nights, one adult.

| Option | Party total (USD) | Transit minutes | Accommodation |
| --- | --- | --- | --- |
| No feasible synthetic option | — | — | — |

## Separate activity evidence

Guide status: `options`. Published charges do not verify dates or availability.

- Two-hour river paddle: USD 35.00 known activity charges; whole-trip total unknown. [Source](https://milwaukeekayak.com/reservations-rates/); reviewed 2026-09-15T00:00:00Z.
- Self-guided RiverWalk exploration: USD 0.00 known activity charges; whole-trip total unknown. [Source](https://city.milwaukee.gov/DCD/Projects/RiverWalk); reviewed 2026-09-15T00:00:00Z.

Researched Milwaukee activity guide; source review date is not a fresh availability check.
Admission/rental amounts only. Access transport, personal equipment, fees and whole-trip budget fit remain unknown.
No date-specific booking slots, closures, weather or accessibility checks have been performed.

Natural-language and authenticated hotel journeys remain unverified.
