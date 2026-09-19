"""Bounded, read-only hotel search. No booking, pagination or implicit retries."""

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Lock
from urllib.parse import urlsplit

import httpx

from travel_agent.contracts import Cost, Evidence, Option, Preferences, ResultSnapshot, summarize_costs
from travel_agent.settings import Settings


class HotelUnavailable(Exception):
    pass


class PrivateHttpLogs(logging.Filter):
    """SerpApi documents query-string authentication; discard its HTTP URL logs."""
    def filter(self, record):
        return "serpapi.com" not in record.getMessage() and "api_key" not in record.getMessage()


logging.getLogger("httpx").addFilter(PrivateHttpLogs())
logging.getLogger("httpcore.http11").addFilter(PrivateHttpLogs())
logging.getLogger("httpcore.http2").addFilter(PrivateHttpLogs())

ALL_COSTS = {"transport", "stay", "activities", "food", "gear", "fees"}
GAPS = ["Hotel leads only: whole-trip cost and budget fit are unknown.",
        "Room type, accessibility and other saved requirements have not been verified.",
        "Pilot destination: Milwaukee, Wisconsin. No transport or activity inventory is searched."]


def source_url(value):
    if not isinstance(value, str) or len(value) > 4000:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.hostname == "serpapi.com" or parsed.hostname.endswith(".serpapi.com") or "api_key" in value.lower():
        return None
    return value


def normalize(body: dict, preferences: Preferences, revision: int) -> ResultSnapshot:
    now = datetime.now(timezone.utc)
    dates = preferences.dates
    expected = {"engine": "google_hotels", "q": "Hotels in Milwaukee Wisconsin", "currency": "USD",
                "check_in_date": str(dates.start), "check_out_date": str(dates.end),
                "adults": preferences.adults, "children": 0}
    if body.get("error") or body.get("search_metadata", {}).get("status") != "Success":
        raise ValueError("Provider did not complete search")
    params = body.get("search_parameters", {})
    if any(str(params.get(key)) != str(value) for key, value in expected.items()):
        raise ValueError("Search context does not match")
    rows = body.get("properties")
    if not isinstance(rows, list):
        raise ValueError("Missing properties collection")
    options, gaps, seen = [], list(GAPS), set()
    for row in rows[:50]:
        try:
            title, identity = row["name"], row["property_token"]
            link = source_url(row.get("link"))
            if not link or not isinstance(title, str) or not 0 < len(title) <= 300:
                raise ValueError("Missing source or title")
            if not isinstance(identity, str) or not 0 < len(identity) <= 1000 or identity in seen:
                raise ValueError("Missing or duplicate identity")
            # JSON floats are parsed as Decimal before normalization. Never derive
            # an entire stay from a nightly minimum or attach a vendor's nightly price.
            amount = row.get("total_rate", {}).get("extracted_lowest")
            if type(amount) not in (int, Decimal):
                raise ValueError("Missing whole-stay amount")
            evidence = Evidence(kind="observed_search_price", provider="Google Hotels via SerpApi",
                                retrieved_at=now, url=link, search_dates=dates, adults=preferences.adults,
                                explanation="Lowest displayed whole-stay search price. The property link may not reproduce this rate. Final fees, room type and availability require confirmation.")
            cost = Cost(label="Displayed hotel stay", category="stay", amount=amount, basis="party_total", quantity=1, evidence=evidence)
            total = summarize_costs([cost], ALL_COSTS)
            options.append(Option(kind="hotel", id=identity, title=title, destination="Milwaukee, Wisconsin",
                                  costs=[cost], hotel_cost=summarize_costs([cost], {"stay"}), total_cost=total,
                                  nights=(dates.end - dates.start).days, adults=preferences.adults,
                                  tradeoffs=["Other trip costs and any additional hotel fees remain unknown."],
                                  assumptions=["Search assumes one room for the selected adults; room configuration is unverified."]))
            seen.add(identity)
        except (ValueError, TypeError, KeyError, AttributeError):
            if "Some listings lacked a valid whole-stay price or source and were omitted." not in gaps:
                gaps.append("Some listings lacked a valid whole-stay price or source and were omitted.")
    options.sort(key=lambda option: (option.hotel_cost.total, option.title))
    return ResultSnapshot(preference_revision=revision, created_at=now, status="options" if options else "no_match",
                          options=options[:3], coverage_gaps=gaps)


class SerpApiHotels:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None, *, ledger=None):
        self.ledger = ledger
        self.settings, self.client = settings, client
        self.calls = 0
        self._lock = Lock()

    async def search(self, preferences: Preferences, revision: int) -> ResultSnapshot:
        dates = preferences.dates
        if not dates or dates.mode != "fixed" or dates.start < date.today() or (dates.end - dates.start).days > 60:
            return ResultSnapshot(preference_revision=revision, created_at=datetime.now(timezone.utc), status="unavailable",
                                  coverage_gaps=["Choose future fixed check-in/check-out dates, up to 60 nights, for hotel search."])
        if preferences.adults is None:
            raise HotelUnavailable("Select one or two adults before searching.")
        with self._lock:
            if not self.settings.hotels_available or self.calls >= self.settings.hotel_max_calls:
                raise HotelUnavailable("Hotel search is not configured or its local call allowance is exhausted.")
            if self.ledger is not None and not self.ledger.reserve('hotels', self.settings.hotel_max_calls):
                raise HotelUnavailable("Persistent hotel allowance unavailable or exhausted.")
            self.calls += 1
        params = {"engine": "google_hotels", "q": "Hotels in Milwaukee Wisconsin", "currency": "USD", "gl": "us", "hl": "en",
                  "no_cache": "true",
                  "check_in_date": str(dates.start), "check_out_date": str(dates.end), "adults": preferences.adults, "children": 0,
                  "api_key": self.settings.serpapi_api_key.get_secret_value()}
        try:
            async with asyncio.timeout(20):
                if self.client is None:
                    async with httpx.AsyncClient(timeout=18, follow_redirects=False) as client:
                        response = await client.get("https://serpapi.com/search.json", params=params)
                else:
                    response = await self.client.get("https://serpapi.com/search.json", params=params, timeout=18, follow_redirects=False)
                response.raise_for_status()
                body = json.loads(response.content, parse_float=Decimal)
                return normalize(body, preferences, revision)
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError, AttributeError):
            raise HotelUnavailable("Hotel search failed or returned unusable data. No fixtures were substituted.") from None
