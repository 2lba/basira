# User Flow Simulation Results

Date: 2026-05-21
Branch: `master-audit-pre-release`
Spec file pattern: `frontend/e2e/tests/user-flows/flow-*.spec.js`
Helpers: `frontend/e2e/tests/user-flows/helpers/flow.js`
Backend test routes added: `POST /test/revoke-key/{user_id}`, `POST /test/scans/orphan-running`

## Test ledger

| Flow | What it covers | Round 1 | Round 2 | Round 3 |
|------|----------------|---------|---------|---------|
| A | New user: banner, settings CTA, add key, scan, resolve finding | PASS | PASS | PASS |
| B | Returning user: rescan, two runs in history | PASS | PASS | PASS |
| C | Notifications: slack + discord receive a payload after scan | PASS | PASS | PASS |
| D | Team isolation: user B blocked on A's repo / scan / api-keys | PASS | PASS | PASS |
| E.1 | Edge - invalid key rejected at write time | PASS | PASS | PASS |
| E.2 | Edge - deleting a key blocks new scans only | PASS | PASS | PASS |
| E.3 | Edge - revoked key shows is_valid=false on api | PASS | PASS | PASS |
| F | Performance - scan terminal within budget, metadata exposed | PASS | PASS | PASS |
| G | Recovery - orphan running scans transition to failed | PASS | PASS | PASS |

| Round | Wall-clock |
|-------|------------|
| 1 | 21.7s |
| 2 | 21.1s |
| 3 | 21.3s |

## Fixes during stabilisation

The first pass failed three tests (A, C, D) and round 3 of the second pass failed two more (E.2, F) under accumulated load. Root causes and fixes:

- Flow A: the per-finding action buttons are only rendered after the row is expanded. Fixed by clicking `items.first().locator("button").first()` to expand before clicking `action-resolve`.
- Flow C: the webhook URL validator blocks loopback hosts (correct SSRF defense). Routed the sink URL through the docker-network internal hostname `http://backend:8000` instead of `http://localhost:8001`.
- Flow D: Playwright's `request` fixture shares cookies. Switched to per-user request contexts via `playwrightRequest.newContext()` so user B never carries user A's session.
- Flows E.2 + F: the `/test/scans/{id}/finalize-now` route races the worker (`StaleDataError: UPDATE statement on table 'scans' expected to update 1 row(s); 0 were matched.`). Replaced the manual finalize with a `waitForTerminal` poll - the e2e stub in the worker already lands the scan in a deterministic succeeded state with canned findings, so the manual route was redundant and conflicting. Race gone, three rounds clean.

## Notes for follow-up

- The `/test/scans/{id}/finalize-now` helper is still used by some pre-existing e2e tests (`scan-flow.spec.js` and friends). They have not flaked in the audit runs, but the same race exists. Worth a follow-up to either gate the route on "scan must be terminal already" or remove its callers in favour of `waitForTerminal`.
- One pre-existing test, `onboarding.spec.js:35`, still flakes occasionally in the larger suite (passes 6/6 in isolation). Likely a localStorage bleed from sibling tests; not in scope for this round.
