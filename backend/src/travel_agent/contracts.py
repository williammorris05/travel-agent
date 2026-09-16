"""Validated domain boundaries shared by API, future agent, and ranking."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def decimal_input(value):
    if isinstance(value, (float, bool)):
        raise ValueError("Money must be a decimal string or integer, never a float")
    return value


Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
AggregateMoney = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
Priority = Annotated[int, Field(strict=True, ge=0, le=100)]


class Dates(Contract):
    mode: Literal["fixed", "flexible"]
    start: date | None = None
    end: date | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if value is not None and not (type(value) is date or isinstance(value, str) and len(value) == 10):
            raise ValueError("Use YYYY-MM-DD calendar dates")
        return value

    @model_validator(mode="after")
    def valid_window(self):
        if self.mode == "fixed" and (self.start is None or self.end is None):
            raise ValueError("Fixed dates need both start and end")
        if (self.start is None) != (self.end is None):
            raise ValueError("A date window needs both endpoints")
        if self.start and self.end <= self.start:
            raise ValueError("End date must follow start date")
        return self


class Budget(Contract):
    amount: Money
    currency: Literal["USD"] = "USD"
    basis: Literal["party", "per_person"] | None = None
    covers: list[Literal["transport", "stay", "activities", "food", "gear", "fees"]] | None = None
    _money = field_validator("amount", mode="before")(decimal_input)


class Controls(Contract):
    adventure: Priority | None = None
    savings: Priority | None = None
    transit_tolerance: Priority | None = None


class Constraints(Contract):
    shared_room_allowed: bool | None = Field(default=None, strict=True)
    max_exertion: Literal["low", "moderate", "high"] | None = None
    private_room: bool | None = Field(default=None, strict=True)
    camping_allowed: bool | None = Field(default=None, strict=True)
    overnight_transport_allowed: bool | None = Field(default=None, strict=True)
    accessibility: list[str] = Field(default_factory=list)
    excluded_transport: list[str] = Field(default_factory=list)


class Preferences(Contract):
    origin: str | None = Field(default=None, min_length=1, max_length=200)
    dates: Dates | None = None
    nights: int | None = Field(default=None, strict=True, ge=1, le=60)
    adults: int | None = Field(default=None, strict=True, ge=1, le=2)
    budget: Budget | None = None
    interests: list[str] = Field(default_factory=list)
    controls: Controls = Field(default_factory=Controls)
    constraints: Constraints = Field(default_factory=Constraints)

    @field_validator("origin")
    @classmethod
    def meaningful_origin(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Origin cannot be blank")
        return value.strip() if value else value

    @model_validator(mode="after")
    def consistent_nights(self):
        if self.dates and self.dates.start and self.nights:
            span = (self.dates.end - self.dates.start).days
            if self.nights > span or self.dates.mode == "fixed" and self.nights != span:
                raise ValueError("Nights must agree with the date window")
        return self

    def missing(self) -> list[str]:
        fields = [name for name in ("origin", "dates", "adults", "budget") if getattr(self, name) is None]
        if self.dates and self.dates.mode == "flexible" and self.nights is None:
            fields.append("nights")
        if self.budget:
            if self.budget.basis is None:
                fields.append("budget.basis")
            if not self.budget.covers:
                fields.append("budget.covers")
        return fields


class DatesPatch(Contract):
    mode: Literal["fixed", "flexible"] | None = None
    start: date | None = None
    end: date | None = None
    _dates = field_validator("start", "end", mode="before")(Dates.calendar_date.__func__)


class BudgetPatch(Contract):
    amount: Money | None = None
    currency: Literal["USD"] | None = None
    basis: Literal["party", "per_person"] | None = None
    covers: list[Literal["transport", "stay", "activities", "food", "gear", "fees"]] | None = None
    _money = field_validator("amount", mode="before")(decimal_input)


class PreferencesPatch(Contract):
    origin: str | None = None
    dates: DatesPatch | None = None
    nights: int | None = Field(default=None, strict=True, ge=1, le=60)
    adults: int | None = Field(default=None, strict=True, ge=1, le=2)
    budget: BudgetPatch | None = None
    interests: list[str] | None = None
    controls: Controls | None = None
    constraints: Constraints | None = None


class PreferenceUpdate(Contract):
    expected_revision: int = Field(strict=True, ge=0)
    source: Literal["chat", "slider", "form"]
    changes: PreferencesPatch

    @model_validator(mode="after")
    def slider_scope(self):
        if not self.changes.model_fields_set:
            raise ValueError("Supply at least one changed field")
        if self.source == "slider" and self.changes.model_fields_set != {"controls"}:
            raise ValueError("Sliders may only update controls")
        return self


class Evidence(Contract):
    kind: Literal["demo", "estimate", "published_price", "starting_price", "scheduled_price", "observed_search_price", "verified_quote"]
    provider: str = Field(min_length=1)
    retrieved_at: datetime
    url: HttpUrl | None = None
    explanation: str = Field(min_length=1)
    search_dates: Dates | None = None
    adults: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def provenance(self):
        if self.retrieved_at.tzinfo is None:
            raise ValueError("Evidence timestamps need a timezone")
        if self.kind not in ("demo", "estimate") and self.url is None:
            raise ValueError("Published prices need a source URL")
        if self.kind in ("observed_search_price", "verified_quote"):
            if not self.search_dates or self.search_dates.mode != "fixed" or self.adults is None:
                raise ValueError("Observed prices need fixed dates and party size")
        return self


class Cost(Contract):
    label: str = Field(default="Cost component", min_length=1)
    category: Literal["transport", "stay", "activities", "food", "gear", "fees"]
    amount: Money | None
    currency: Literal["USD"] = "USD"
    basis: Literal["party_total", "per_person", "per_room_night", "per_person_night"]
    quantity: int = Field(strict=True, ge=1)
    evidence: Evidence
    unknown_reason: str | None = Field(default=None, min_length=1)
    _money = field_validator("amount", mode="before")(decimal_input)

    @model_validator(mode="after")
    def price_semantics(self):
        if self.amount is None and self.unknown_reason is None:
            raise ValueError("Missing prices require an explanation")
        if self.amount is not None and self.unknown_reason is not None:
            raise ValueError("A known price cannot have an unknown reason")
        if self.basis == "party_total" and self.quantity != 1:
            raise ValueError("Party totals must have quantity 1")
        return self


class CostSummary(Contract):
    known_subtotal: AggregateMoney
    total: AggregateMoney | None
    currency: Literal["USD"] = "USD"
    missing_categories: list[str]


def summarize_costs(costs: list[Cost], required: set[str]) -> CostSummary:
    missing = required - {cost.category for cost in costs}
    missing.update(cost.category for cost in costs if cost.amount is None)
    subtotal = sum((cost.amount * cost.quantity for cost in costs if cost.amount is not None), Decimal("0.00"))
    return CostSummary(known_subtotal=subtotal, total=None if missing else subtotal, missing_categories=sorted(missing))


class Option(Contract):
    kind: Literal["trip", "hotel", "activity"] = "trip"
    activity_cost: CostSummary | None = None
    activity_schedule: str | None = None
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    hotel_cost: CostSummary | None = None
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    costs: list[Cost] = Field(min_length=1)
    tradeoffs: list[str] = Field(default_factory=list)
    destination: str | None = None
    total_cost: CostSummary | None = None
    budget_cost: CostSummary | None = None
    budget_cap: AggregateMoney | None = None
    budget_categories: list[str] = Field(default_factory=list)
    nights: int | None = None
    adults: int | None = None
    transit_minutes: int | None = None
    destination_minutes: int | None = None
    adventure_score: int | None = None
    exertion: Literal["low", "moderate", "high"] | None = None
    accommodation: str | None = None
    score: float | None = None
    fit_reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    itinerary: list[str] = Field(default_factory=list)


class Exclusion(Contract):
    candidate_id: str
    reasons: list[str]


class ResultSnapshot(Contract):
    preference_revision: int = Field(strict=True, ge=0)
    created_at: datetime
    status: Literal["options", "no_match", "unavailable"]
    options: list[Option] = Field(default_factory=list, max_length=3)
    coverage_gaps: list[str] = Field(default_factory=list)
    exclusions: list[Exclusion] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_result(self):
        if self.created_at.tzinfo is None:
            raise ValueError("Snapshot timestamps need a timezone")
        if (self.status == "options") != bool(self.options):
            raise ValueError("Options status requires options; other statuses cannot contain them")
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Option IDs must be unique")
        return self
