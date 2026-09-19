# Hotel search setup

The L6 integration is tested with synthetic provider responses only. The user deferred adding a key; no authenticated hotel search or source-price comparison has been performed.

1. Confirm a SerpApi free account and remaining searches in its dashboard. The published free plan currently lists 250 searches/month and 50/hour; account eligibility and remaining usage have not been verified. Do not enable paid overages for this demo.
2. Copy `backend/.env.example` to `backend/.env` if needed, preserving any existing model settings. Set `TRAVEL_SERPAPI_API_KEY` locally, `TRAVEL_DATA_MODE=live`, and `TRAVEL_HOTEL_MAX_CALLS=3`. Never place keys in the frontend or commit `.env`.
3. Restart the backend. Health reports `hotel_search_configured`, which means configured, not authenticated or verified.
4. In the chat UI, load an example to fill the preferences, then use `/dates YYYY-MM-DD YYYY-MM-DD` with future dates. Select **Find options** or send `/plan`. Commands work without a model key. A separately configured model can also trigger the hotel search through natural-language chat.

The pilot queries Milwaukee, Wisconsin only, in USD, for one room and one or two adults. It returns up to three hotel leads ordered by displayed whole-stay price. It does not establish room type, accessibility, final availability, all fees or whole-trip budget fit. Adventure/time sliders remain saved but do not score hotels without activity/transport evidence. Fixed dates are required; flexible dates trigger clarification without a hotel call.

Each planning request consumes at most one hotel call. Attempts—including errors—count against a persistent SQLite lifetime allowance of at most 10. There are no retries, pagination, property-detail calls or background fetches. Slider PATCHes make no provider calls. Chat can discuss existing session results for up to five minutes when dates/adults match and no failed refresh is recorded, preserving their original retrieval timestamp. Explicit refreshes fetch again with provider caching disabled. Calls are limited to 20 seconds overall. Restarting does not reset the counter. Keep the account on the free plan: this is not an account-wide spending ledger. Current offers remain in the ephemeral session; there is no cross-session provider cache or disk content archive. See [reliability and limits](reliability.md).

Direct /plan provider failures return 503 and retain previous results as unrefreshed. Combined /refresh returns partial state with source_issues and the independent activity guide. Chat preserves validated preferences and reports hotel failures with partial state; model interpretation failures still save nothing. Revision conflicts reject late results. Dates/adults are sent with each search and checked against returned search parameters. Only numeric whole-stay totals with usable HTTPS property links are displayed; nightly minima are never multiplied into invented totals. Links may not reproduce the displayed search rate. Confirm final prices on the property/provider site.

SerpApi authenticates through a query parameter. Built-in HTTP logging filters discard its URL records; errors do not expose upstream bodies or request URLs. Do not add wire logging or request instrumentation that captures credentials. SerpApi may retain search parameters under its own service terms; this local demo sends only its bounded hotel query and dates/party, never chat text.

Validation before closing L6: use one free authorized search, inspect returned date/party/currency and price basis, compare at least one linked property page, and record actual latency, call usage, differences and remaining unknowns in the vault. Documentation examples and mocked tests do not satisfy that gate.

Sources: [Google Hotels API](https://serpapi.com/google-hotels-api), [pricing](https://serpapi.com/pricing), [service terms](https://serpapi.com/legal). Planning and status: vault `Travel Agent - L6 Hotel Integration`.
