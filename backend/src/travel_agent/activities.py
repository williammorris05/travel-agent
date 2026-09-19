"""Manually reviewed public listings, never date-specific inventory or fixtures."""

from datetime import datetime, timezone

from travel_agent.contracts import Cost, Evidence, Exclusion, Option, Preferences, ResultSnapshot, summarize_costs


REVIEWED = datetime(2026, 9, 15, tzinfo=timezone.utc)
RIVER = "https://city.milwaukee.gov/DCD/Projects/RiverWalk"
RATES = "https://milwaukeekayak.com/reservations-rates/"
RULES = "https://milwaukeekayak.com/faqs/"
REQUIRED = {"activities", "transport", "stay", "food", "gear", "fees"}


def evidence(url: str, provider: str, explanation: str) -> Evidence:
    return Evidence(kind="published_price", provider=provider, retrieved_at=REVIEWED,
                    url=url, explanation=explanation)


def activity_guide(preferences: Preferences, revision: int) -> ResultSnapshot:
    now = datetime.now(timezone.utc)
    gaps = ["Researched Milwaukee activity guide; source review date is not a fresh availability check.",
            "Admission/rental amounts only. Access transport, personal equipment, fees and whole-trip budget fit remain unknown.",
            "No date-specific booking slots, closures, weather or accessibility checks have been performed."]
    if preferences.adults is None:
        return ResultSnapshot(preference_revision=revision, created_at=now, status="unavailable",
                              coverage_gaps=["Set one or two adults before comparing activity costs."])
    if not 0 <= (now - REVIEWED).total_seconds() <= 30 * 86400:
        return ResultSnapshot(preference_revision=revision, created_at=now, status="unavailable",
                              coverage_gaps=["Activity source review has expired. Recheck the official rates before showing prices."])
    adults = preferences.adults
    river = Cost(label="RiverWalk public access", category="activities", amount="0.00", basis="party_total", quantity=1,
                 evidence=evidence(RIVER, "City of Milwaukee", "City lists public RiverWalk access as free, open around the clock. This does not include travel, purchases or paid venues."))
    free = Option(kind="activity", id="riverwalk-self-guided", title="Self-guided RiverWalk exploration", destination="Milwaukee",
                  costs=[river], adults=adults, activity_cost=summarize_costs([river], {"activities"}), total_cost=summarize_costs([river], REQUIRED),
                  activity_schedule="Published public access: 24 hours daily; local closures are not checked.",
                  tradeoffs=["Explore independently; choose your own distance. No guide or transport is included."],
                  assumptions=["A short walking segment is an application-proposed low-exertion variant, not a verified accessible itinerary."])
    kayak = Cost(label="Two-hour kayak rental", category="activities", amount="35.00" if adults == 1 else "65.00", basis="party_total", quantity=1,
                 evidence=evidence(RATES, "Milwaukee Kayak Company", "Published two-hour rental rate: one single kayak for one adult, or one tandem for two. Taxes and booking extras are unverified."))
    paddle = Option(kind="activity", id="kayak-rental", title="Two-hour river paddle", destination="Milwaukee",
                    adults=adults, costs=[kayak], activity_cost=summarize_costs([kayak], {"activities"}), total_cost=summarize_costs([kayak], REQUIRED),
                    activity_schedule="Two-hour rental duration; seasonal opening dates and bookable start times are not checked.",
                    supporting_evidence=[evidence(RULES, "Milwaukee Kayak Company", "Operator includes a paddle and life jacket, requires the jacket to be worn, and requires launch/return at its dock. River conditions and participant suitability need confirmation.")],
                    tradeoffs=["Self-propelled paddling requires more effort than a short walk. This is a rental, not a guided tour."],
                    assumptions=["Moderate exertion is an application screening assumption. Check operator requirements, weather and river conditions.",
                                 "Included paddle/life jacket do not establish that all personal gear costs are zero."])
    options, exclusions = [free], []
    if preferences.constraints.max_exertion == "low":
        exclusions.append(Exclusion(candidate_id=paddle.id, reasons=["Paddling is excluded under the conservative low-exertion screen."]))
    else:
        options.append(paddle)
    if preferences.constraints.accessibility:
        exclusions.extend(Exclusion(candidate_id=o.id, reasons=["The saved accessibility requirements cannot be verified from these listings."]) for o in options)
        options = []
    # Compare partial activity charges only; never claim complete trip savings.
    if preferences.budget and preferences.budget.basis and preferences.budget.covers and "activities" in preferences.budget.covers:
        cap = preferences.budget.amount * (adults if preferences.budget.basis == "per_person" else 1)
        retained = []
        for option in options:
            if option.activity_cost.total > cap:
                exclusions.append(Exclusion(candidate_id=option.id, reasons=["The published activity charge alone exceeds the selected budget cap."]))
            else:
                retained.append(option)
        options = retained
    if (preferences.controls.adventure or 0) > (preferences.controls.savings or 0):
        options.sort(key=lambda o: o.id != "kayak-rental")
    return ResultSnapshot(preference_revision=revision, created_at=now, status="options" if options else "no_match",
                          options=options, exclusions=exclusions, coverage_gaps=gaps)
