# Local demo reliability (L8)

Run one backend worker on one machine. Trips and transcripts remain in memory and
reset on restart. Provider attempt counts persist separately in
`data/private/usage.sqlite3`, excluded from Git. `TRAVEL_USAGE_DB` can specify an
absolute path on local disk. Keep that same file across runs. Avoid a network or
cloud-synced filesystem for concurrent processes; choose a local path if needed.

`TRAVEL_MODEL_MAX_CALLS` (0–100) and `TRAVEL_HOTEL_MAX_CALLS` (0–10) are lifetime
attempt ceilings. For example, with two attempts used, setting the hotel cap to
three allows one further attempt. They do not refill at restart or monthly.
Increasing the ceiling is an explicit operator action after checking the account's
free quota. Deleting/changing the ledger removes its protection; do not do this to
retry an exhausted quota. There is no HTTP reset endpoint.

SQLite reserves an attempt atomically before external I/O. Failures and cancelled
requests consume reservations. Both model adapters share one model bucket; hotels
use a separate bucket. An inaccessible/corrupt ledger fails closed. Only bucket
names and integer counts are persisted, never keys, prompts, dates or responses.
These limits protect this installation, not other users of the same provider
account. Session state is not shared across workers, so multi-worker deployment
is unsupported even though concurrent ledger access is tested.

Use **Refresh options + activity guide** to update both result sections. In live
mode a failed hotel search leaves previous hotel results visible but marked
unrefreshed, while the researched activity guide can succeed independently. No
fixture replaces live data. An expired guide also does not prevent hotel results.
Model failures save nothing; a hotel failure after valid interpretation saves the
preferences and returns source-specific notices.

`POST /api/trips/{id}/refresh` accepts `expected_revision` and a UUID `request_id`.
Reusing a completed ID returns current state without new calls, including when a
different refresh has since completed. Concurrent operations for the same trip
return 409; changed revisions reject late publication. At most 100 unique completed
refresh IDs are kept per trip; further new IDs return 429. They live as long as the
trip. Restarts invalidate trip IDs while retaining provider usage. Other endpoints
use revision/concurrency guards, not refresh ID deduplication. A deliberate new
button click gets a new ID. No automatic network retries occur.

Hotel evidence expires after five minutes; activity evidence after 30 days from
the actual source review, not the click time. Future-dated evidence is invalid.
Responses compute freshness, and the UI rechecks age every 30 seconds without
fetching data. An activity refresh regenerates the guide; it does not recheck the
source website. Synthetic fixture prices do not acquire live freshness claims.
Changing dates/adults prevents chat reuse and requires a fresh hotel query.

Controlled tests cover concurrent threads/processes, app recreation, failed
attempt accounting, shared model allowance, completed-request deduplication,
slider changes without calls, late-result rejection, partial results and age.
Authenticated model/hotel checks and automated activity schedules remain pending;
this document does not establish that the combined live journey passed.
