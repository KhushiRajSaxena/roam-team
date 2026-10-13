# Security review and fixes

Reviewed September 16, 2026. Scope: this local FastAPI application, its browser UI, SQLite state and bundled source archive. This is an implementation review with regression tests, not an independent penetration-test certification or a guarantee against every attack.

## Six areas

| Area | Finding before changes | Implemented protection | Boundary |
|---|---|---|---|
| Authorization | No account identity; every local caller could initiate plans. | Local accounts required for planning, config, usage and sessions. No public registration or account-admin API. Model-decision cache partitioned by authenticated user. | Plans are returned only to the requesting connection and are not stored as retrievable user records. There is no plan-by-ID endpoint to expose another user's history. Public flight/hotel/place quotes and aggregate provider quotas remain shared. |
| Rate limiting | Provider quotas existed, but cached/demo planning and inbound requests had no limits. | Atomic SQLite rolling counters by actual socket peer, user and globally. Both planning endpoints use the same buckets. New sessions, spoofed forwarding headers and server restart do not reset limits. | Distributed network floods and resource exhaustion by an attacker with filesystem access require OS/ingress controls; this app is deliberately local-only. |
| Secrets management | Keys stayed server-side, but private-file modes and diagnostics needed tightening. | `.env` and SQLite/owner credential files set to 0600; `.local` set to 0700. Session secrets stored as SHA-256 digests; passwords salted with scrypt. No JWT/localStorage bearer tokens. Validation errors do not echo input; configured provider secrets scrubbed from errors. No raw exception logging. Known credentials scanned out of source and archive. | Local credentials and cached provider data are not encrypted at rest; secure the OS account/disk. Downloaded PDFs are ordinary user-owned files. The initial credential file intentionally contains the one-time provisioned password, readable by its OS owner. |
| Access control | Only a Host/optional-Origin check guarded requests. | Authentication, mandatory same-Origin and JSON for mutations, per-session CSRF value, Fetch Metadata checks, server schema validation, strict Host policy, local-peer enforcement and no trusted forwarded IP. Private directories are outside the static mount. API docs/schema disabled. CSP, no framing, no sniffing and no-store headers. | Changing hidden form fields cannot bypass server validation. Local filesystem account management is an administrator capability, not exposed over HTTP. |
| Token security | No authenticated sessions or revocation mechanism existed. | Random 256-bit opaque session cookies, HttpOnly, SameSite=Strict, Secure under HTTPS; 30-minute idle and 8-hour absolute expiry. Login rotates the prior browser session. Logout, logout-all, CLI revoke, password reset and disable revoke server-side sessions. Active jobs recheck revocation about once per second. | Theft allows replay until revoked/expired; HttpOnly is not protection against all XSS or a compromised OS. Local HTTP does not provide transport encryption. |
| Resilience | Expensive requests could wait in an unbounded semaphore queue; request/provider bodies were unbounded. | Immediate admission: 3 active jobs globally, 1 per user via shared SQLite leases; 180-second job deadline; cancellation on disconnect/revocation; bounded 64-event queue; 16 KiB request bodies including chunked bodies; 10-second body read limit; URL/query limits; 2 MiB decoded provider responses; 64 MiB cached-payload cap. Uvicorn connection concurrency 64 and keepalive 5 seconds. Existing provider budgets remain. | Requires the supplied run configuration. Local SQLite is not a distributed service; disk capacity, backups and OS resource limits remain operational responsibilities. The cache cap is payload size, not a promise that the SQLite file shrinks after deletes. |

## Limits

All windows roll and persist in `.local/state.sqlite3`:
- API: 180 requests/minute globally; 120/minute per actual peer; 60/minute per signed-in user.
- Login attempts: 5/minute per peer; 10/minute globally. Failures count; usernames and forwarded headers do not create new peer buckets.
- Planning: 5/minute and 20/hour per account; 30/hour globally. Demo, AI, live, cache hits and invalid attempts share these counters.
- Excess requests return 429 with Retry-After: 60. Longer hourly limits may require waiting longer; no automatic retries.
- Existing Groq, SerpApi and Geoapify quotas still apply independently.

## Verification

69 pytest tests passed (one upstream Starlette deprecation warning). Security regressions cover unauthenticated APIs, private-file access, password/session hashing, cross-account revoke attempts, CSRF/Origin/Fetch Metadata, unknown fields, body/URL/type limits, chunked-body bypass attempts, login limits after restart and forwarding spoof attempts, expiry/disabled accounts, concurrent atomic admission/limits, shared limits across planning routes, private cache partitioning, in-flight cancellation after revocation, remote-peer rejection, bounded and compressed provider responses, secret-safe errors, and response headers.

jsdom plus the running server verified initial sign-in gating, password-field clearing, configured live mode, authenticated demo planning, actual PDF construction, logout-all, rejection of the old cookie, clearing the previous plan and no token storage in localStorage/sessionStorage. No provider/model requests were made. Known Groq/SerpApi/Geoapify values and the initial owner password were absent from application source, browser assets, tests and docs; `.env` and `.local` are ignored by Git. This scan does not claim to identify every possible unknown secret in Git history.

## Required local transition

The secured app runs at **http://127.0.0.1:8003**. Older processes still listening on **8000, 8001 and 8002** could not be terminated from this sandbox (OS returned “operation not permitted”). Stop those old Roam Team processes from their original terminals or Activity Monitor. Their in-memory backend code does not acquire these protections just because files changed.

The initial login is `owner`; find its password in `.local/owner-login.txt`, never in chat. Additional accounts and emergency revocation are managed by `python -m scripts.accounts`. Keep the database: deleting it also deletes accounts, sessions, quotas and limits.

## Deployment boundary and references

Do not publish this local build via a tunnel or reverse proxy. Public hosting needs HTTPS, reviewed proxy/host settings, a production account/recovery policy, per-deployment secret storage, monitoring, backups and external rate/connection protection. No claim is made that these six areas can be universally “satisfied” independent of the deployment and threat model.

Implementation guidance: [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html), and [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
