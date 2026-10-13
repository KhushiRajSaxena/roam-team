# Validation record

Updated for the Groq / SerpApi / Geoapify implementation, 12 September 2026.

| Check | Result |
|---|---|
| Backend, quota and provider regression suite | 69 tests passed |
| JavaScript syntax | Passed |
| Current local app | Serving on port 8003; authenticated access required |
| Groq live integration | Passed: 4 distinct model calls, 3,803 input tokens and 437 output tokens |
| SerpApi live integration | Passed: 3 search requests returned flight and hotel candidates |
| Geoapify live integration | Passed: 1 places request and 3 driving-route requests |
| Complete live test | Delhi → Goa, four nights, one adult: plan assembled; one activity removed after route checks |
| Exact cached replay | 0 new provider or model calls; 7 travel cache hits and 4 AI decision cache hits |
| Interface behavior | Passed in an emulated DOM against the server: demo, cached live plan, streamed events, revisions, infeasible budget, error recovery, source attribution and quota display |
| Independent validator | Checks actual activity intervals, transfer gaps, arrival buffers, duplicate selections and monetary totals; malformed schedules are rejected |
| Quota safeguards | Tested persistent/rolling limits, atomic reservations, same-process deduplication, cache hits after quota exhaustion and protection of SerpApi's final 20 plan searches |
| Credential handling | Configured key values absent from documentation and cached records; `.env` and `.local` excluded from source control |
| Demo evaluation | Eight scenarios, including an intentionally unaffordable request; no real API quota used |
| Automated visual browser QA | Unavailable in this session; no desktop/mobile screenshot validation claim |
| Native WebMCP | Unsupported here; read-tool registration and failure behavior tested with an emulated registry |

See `live-validation.json` for the measured live run and cached replay. The live test covered one Indian route and one adult; other regions, group occupancy and edge cases are covered by provider-shaped test doubles, not claimed as live verified.

Flights/hotels are search prices, not confirmed bookings. Unknown attraction fees remain estimates. Route times are driving estimates, and source opening hours are not fully date/holiday validated. No comparative AI quality improvement is claimed from the small demo evaluation.

There is one upstream Starlette test-client deprecation warning. It does not affect the passing checks. The older app instance on port 8000 could not be stopped from this session; use port 8003 for the current secured version.

Location and saved-configuration regressions are documented in [location-fix-validation.md](location-fix-validation.md).

Security follow-up (16 September 2026): see [SECURITY.md](SECURITY.md). Authenticated UI flow and PDF generation passed without provider calls. Prior live results above are historical, not new security-run network tests.
