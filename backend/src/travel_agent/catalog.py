"""Synthetic scenarios, not real prices, schedules, or availability."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator

from travel_agent.contracts import Contract, Cost, Evidence, Money, decimal_input


class Rate(Contract):
    label: str
    category: Literal["transport", "stay", "activities", "food", "gear", "fees"]
    amount: Money | None
    basis: Literal["party_total", "per_person", "per_room_night", "per_person_night"]
    unknown_reason: str | None = None
    _money = field_validator("amount", mode="before")(decimal_input)


class Candidate(Contract):
    id: str
    title: str
    destination: str
    accommodation: Literal["dorm", "private_room", "camping"]
    transport: list[str]
    round_trip_minutes: int = Field(strict=True, ge=0)
    transfers: int = Field(strict=True, ge=0)
    adventure: int = Field(strict=True, ge=0, le=100)
    exertion: Literal["low", "moderate", "high"]
    interests: list[str]
    overnight_transport: bool = False
    feasible: bool = True
    accessibility: list[str] = Field(default_factory=list)
    rates: list[Rate]
    tradeoffs: list[str]
    itinerary: list[str]

    def costs(self, adults: int, nights: int) -> list[Cost]:
        quantities = {"party_total": 1, "per_person": adults,
                      "per_room_night": nights, "per_person_night": adults * nights}
        return [Cost(**rate.model_dump(), quantity=quantities[rate.basis], evidence=Evidence(
            kind="demo", provider="travel-agent synthetic catalog v1",
            retrieved_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            explanation="Authored fixture, not retrieved travel data; prices and schedules are invented for testing."))
            for rate in self.rates]


def rate(label, category, amount, basis="party_total", unknown_reason=None):
    return Rate(label=label, category=category, amount=amount, basis=basis, unknown_reason=unknown_reason)


def catalog() -> list[Candidate]:
    """Return fresh validated records so a caller cannot mutate the shared catalog."""
    def make(id, title, destination, accommodation, transport, minutes, adventure, exertion,
             fare, stay, activity, *, access="0", gear="0", fees="8", food="20", transfers=0,
             overnight=False, feasible=True, interests=None):
        return Candidate(
            id=id, title=title, destination=destination, accommodation=accommodation,
            transport=transport, round_trip_minutes=minutes, transfers=transfers,
            adventure=adventure, exertion=exertion, interests=interests or ["nature", "hiking"],
            overnight_transport=overnight, feasible=feasible,
            rates=[rate("Round-trip fare including baggage", "transport", fare, "per_person"),
                   rate("Terminal/trailhead access, round trip", "transport", access),
                   rate("Accommodation (one shared room/site for a pair, or individual dorm beds)", "stay", stay,
                        "per_person_night" if accommodation == "dorm" else "per_room_night"),
                   rate("Main activity / self-guided access", "activities", activity, "per_person"),
                   rate("Food allowance per person per night", "food", food, "per_person_night"),
                   rate("Food allowance for the final day", "food", food, "per_person"),
                   rate("Required equipment rental for the party", "gear", gear),
                   rate("All mandatory fixture taxes and permits", "fees", fees,
                        unknown_reason="Mandatory fee not supplied in fixture" if fees is None else None)],
            tradeoffs=[f"{minutes // 60}h {minutes % 60}m total transit; {transfers} transfers.",
                       {"dorm": "Shared sleeping room and bathroom.", "camping": "Tent camping with basic facilities; rental gear included.",
                        "private_room": "Private sleeping room; amenities are basic unless described."}[accommodation]],
            itinerary=["Travel from Chicago using the synthetic route.",
                       "Explore at the destination within the remaining time; activity is a fixture scenario.",
                       "Return to Chicago; no lodging night is removed for overnight transport."])

    return [
        make("milwaukee-bus-dorm", "Slow bus and self-guided city exploration", "Milwaukee", "dorm", ["bus"], 600, 20, "low", "30", "18", "0", food="15", transfers=2, interests=["food", "culture", "walking"]),
        make("milwaukee-train-hotel", "Fast train and private city stay", "Milwaukee", "private_room", ["train"], 180, 20, "low", "90", "125", "25", interests=["food", "culture"]),
        make("dunes-camping", "Dunes camping and self-guided hiking", "Indiana Dunes", "camping", ["train", "shuttle"], 360, 95, "high", "35", "25", "0", access="35", gear="75", transfers=2),
        make("dunes-private", "Dunes trails with a private room", "Indiana Dunes", "private_room", ["train", "shuttle"], 300, 80, "moderate", "45", "90", "0", access="30", gear="15", transfers=1),
        make("starved-remote", "Remote bargain room with costly transfers", "Starved Rock", "private_room", ["bus", "taxi"], 540, 85, "moderate", "40", "15", "0", access="320", gear="20", transfers=3),
        make("starved-missing-fee", "Outdoor stay with an unknown permit fee", "Starved Rock", "private_room", ["bus"], 420, 90, "high", "25", "25", "0", fees=None),
        make("starved-impossible", "Infeasible connection example", "Starved Rock", "private_room", ["bus"], 4000, 100, "high", "10", "10", "0", feasible=False),
        make("milwaukee-overnight", "Overnight bus and basic private room", "Milwaukee", "private_room", ["bus"], 1500, 20, "low", "15", "30", "0", food="15", overnight=True, transfers=3, interests=["culture", "food"]),
    ]
