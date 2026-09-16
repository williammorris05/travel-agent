"""Deterministic fixture pricing, hard filtering, ranking and diversity."""

from datetime import datetime, timezone
from travel_agent.catalog import Candidate, catalog
from travel_agent.contracts import Exclusion, Option, Preferences, ResultSnapshot, summarize_costs

REQUIRED_CATEGORIES = {"transport", "stay", "activities", "food", "gear", "fees"}
EXERTION = {"low": 0, "moderate": 1, "high": 2}


def plan(preferences: Preferences, revision: int, *, candidates: list[Candidate] | None = None) -> ResultSnapshot:
    now = datetime.now(timezone.utc)
    if preferences.missing():
        return ResultSnapshot(preference_revision=revision, created_at=now, status="unavailable",
                              coverage_gaps=["Missing preferences: " + ", ".join(preferences.missing())])
    if preferences.origin.casefold().strip() not in {"chicago", "chicago, illinois", "chicago, il"}:
        return ResultSnapshot(preference_revision=revision, created_at=now, status="unavailable",
                              coverage_gaps=["Synthetic routes only support departure from Chicago."])

    nights = preferences.nights or (preferences.dates.end - preferences.dates.start).days
    adults = preferences.adults
    cap = preferences.budget.amount * (adults if preferences.budget.basis == "per_person" else 1)
    covered = set(preferences.budget.covers)
    constraints = preferences.constraints
    exclusions = []
    ranked = []
    gaps = ["All options use invented fixture prices and schedules, not bookable offers."]
    for candidate in catalog() if candidates is None else candidates:
        reasons = []
        if constraints.private_room is True and candidate.accommodation != "private_room":
            reasons.append("Requires a private room.")
        if candidate.accommodation == "dorm" and constraints.shared_room_allowed is not True:
            reasons.append("Shared-room accommodation has not been accepted.")
        if candidate.accommodation == "camping" and constraints.camping_allowed is not True:
            reasons.append("Camping has not been accepted.")
        if candidate.overnight_transport and constraints.overnight_transport_allowed is not True:
            reasons.append("Overnight transport has not been accepted.")
        if constraints.max_exertion and EXERTION[candidate.exertion] > EXERTION[constraints.max_exertion]:
            reasons.append("Activity exceeds the maximum accepted exertion.")
        excluded_modes = {mode.strip().casefold() for mode in constraints.excluded_transport}
        if excluded_modes.intersection(candidate.transport):
            reasons.append("Uses an excluded transport mode.")
        unsupported = {item.strip().casefold() for item in constraints.accessibility} - set(candidate.accessibility)
        if unsupported:
            reasons.append("Accessibility requirements unverified: " + ", ".join(sorted(unsupported)))
        remaining = nights * 24 * 60 - candidate.round_trip_minutes
        if not candidate.feasible or remaining < nights * 8 * 60 + 4 * 60:
            reasons.append("Route cannot fit transit, eight hours of rest per night and four hours of exploration.")

        costs = candidate.costs(adults, nights)
        total = summarize_costs(costs, REQUIRED_CATEGORIES)
        budget_cost = summarize_costs([cost for cost in costs if cost.category in covered], covered)
        if total.total is None:
            gap = f"{candidate.id}: unknown required costs: {', '.join(total.missing_categories)}."
            gaps.append(gap)
            reasons.append(gap)
        if budget_cost.total is not None and budget_cost.total > cap:
            reasons.append(f"Covered costs {budget_cost.total:.2f} USD exceed the party cap {cap:.2f} USD.")
        if reasons:
            exclusions.append(Exclusion(candidate_id=candidate.id, reasons=reasons))
            continue

        controls = preferences.controls
        # Unknown controls remain null in state; provisional scoring is explicit below.
        savings = (controls.savings if controls.savings is not None else 50) / 100
        adventure = (controls.adventure if controls.adventure is not None else 0) / 100
        speed = (100 - controls.transit_tolerance) / 100 if controls.transit_tolerance is not None else 0
        cost_fit = 1 - float(budget_cost.total / cap) if cap else 1
        interest_matches = sorted({item.casefold().strip() for item in preferences.interests}.intersection(candidate.interests))
        interest_fit = len(interest_matches) / len(set(preferences.interests)) if preferences.interests else 0
        adventure_fit = candidate.adventure / 100
        time_fit = remaining / (nights * 24 * 60)
        score = savings * cost_fit + adventure * adventure_fit + speed * time_fit + 0.25 * interest_fit
        fit = [f"Covered fixture costs {budget_cost.total:.2f} USD fit the {cap:.2f} USD party cap."]
        if adventure:
            fit.append(f"Exploration interests: {', '.join(candidate.interests)}; {candidate.exertion} exertion in this synthetic scenario.")
        if interest_matches:
            fit.append("Matching interests: " + ", ".join(interest_matches))
        ranked.append(Option(
            id=candidate.id, title=candidate.title, destination=candidate.destination, costs=costs,
            total_cost=total, budget_cost=budget_cost, budget_cap=cap, budget_categories=sorted(covered),
            nights=nights, adults=adults, transit_minutes=candidate.round_trip_minutes,
            destination_minutes=remaining, adventure_score=candidate.adventure,
            exertion=candidate.exertion, accommodation=candidate.accommodation, score=round(score, 6),
            fit_reasons=fit, tradeoffs=candidate.tradeoffs,
            assumptions=["Synthetic rates apply uniformly to the supplied dates; availability is not checked.",
                         "Trip window is nights × 24 hours; remaining destination time includes sleep.",
                         "One room/site houses the party; dorm beds are priced per person.",
                         "Food is budgeted for nights + 1 days; gear and fees are explicit fixture allowances.",
                         "Unset scoring controls use savings=50, adventure=0, no speed preference; stored values remain unknown."],
            itinerary=candidate.itinerary))

    ranked.sort(key=lambda option: (-option.score, option.budget_cost.total, option.id))
    # Preserve the strongest match, then diversify destinations unless the request is cost-only.
    cost_only = preferences.controls.savings == 100 and preferences.controls.adventure in (None, 0)
    chosen = ranked[:1]
    if not cost_only:
        for option in ranked[1:]:
            if len(chosen) < 3 and option.destination not in {item.destination for item in chosen}:
                chosen.append(option)
    for option in ranked:
        if len(chosen) < 3 and option.id not in {item.id for item in chosen}:
            chosen.append(option)
    if not chosen:
        gaps.append("No supported fixture meets this request. Review exclusion reasons; change only constraints you wish to relax.")
    return ResultSnapshot(preference_revision=revision, created_at=now,
                          status="options" if chosen else "no_match", options=chosen,
                          exclusions=exclusions, coverage_gaps=gaps)
