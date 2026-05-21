# Basira - Threat Model

Date: 2026-05-19 · Version: v0.1.0 · Reviewer: Abdulaziz AlQahtani

This is the working threat model for Basira. It is grounded in the actual
code paths in this repo (not a generic template). Update it when you add a
new asset, a new trust boundary, or a new external integration.

---

## Assets

| Asset | Sensitivity | Storage |
|-------|-------------|---------|
| User identity (GitHub login, email) | low–medium | Postgres (`users`) |
| User OAuth access token | **high** - full GitHub access | Postgres, Fernet-encrypted |
| GitHub App private key | **critical** - signs install JWTs | `secrets/github-app-key.pem`, mounted RO |
| GitHub App webhook secret | high - verifies inbound webhooks | env var |
| JWT signing key (`SECRET_KEY`) | high - issues session tokens | env var |
| `TOKEN_ENCRYPTION_KEY` (Fernet) | high - decrypts user OAuth tokens at rest | env var |
| `ANTHROPIC_API_KEY` | high - billed against the host | env var |
| Source code being scanned | medium - may contain user IP | streamed to Anthropic; not persisted |
| Scan results / findings | low–medium | Postgres |
| SMTP / Slack / Discord webhook URLs | medium | Postgres, Fernet-encrypted |

## Trust boundaries

```
   ┌────────────┐  HTTPS   ┌──────────────┐
   │ User's     │ ───────▶ │ Basira       │
   │ browser    │ ◀─────── │ frontend     │  (Vite, public assets only)
   └────────────┘          └──────┬───────┘
                                   │  same-origin proxy
                                   ▼
                          ┌──────────────────┐
                          │  Basira backend  │
                          │  (FastAPI)       │
                          └──┬─────┬─────┬───┘
              ┌──────────────┘     │     └──────────────┐
              ▼                    ▼                    ▼
      ┌──────────────┐    ┌────────────────┐   ┌──────────────┐
      │  Postgres    │    │  Anthropic API │   │  GitHub      │
      │  (encrypted  │    │  (Claude)      │   │  (App + API) │
      │   creds      │    └────────────────┘   └──────────────┘
      │   inside)    │
      └──────────────┘
```

Boundaries:
1. **Browser → backend** - only via Vite same-origin proxy. Auth via
   `basira_access` (JWT, HttpOnly, SameSite=lax) + `basira_refresh`.
2. **Backend → Postgres** - internal network, password auth.
3. **Backend → Anthropic** - outbound HTTPS, Bearer API key.
4. **Backend → GitHub** - outbound HTTPS, installation tokens (per repo,
   1h TTL).
5. **GitHub → backend (webhooks)** - inbound HTTPS, HMAC SHA-256 signature.

Every cross-boundary write is signed, authenticated, or both.

---

## STRIDE per asset

### S - Spoofing

| Threat | Mitigation | Status |
|--------|------------|--------|
| Attacker forges a session JWT for another user | HS256 with a server-only `SECRET_KEY`; tampered payloads fail verification | covered by `test_tampered_jwt_payload_is_rejected` |
| Attacker forges a webhook that looks like GitHub | HMAC SHA-256 over the raw body with the App's webhook secret | `test_webhook_missing_signature_returns_401`, `test_webhook_bad_signature_returns_401` |
| Attacker logs in as a victim by stealing the OAuth code | `state` parameter (CSRF token) is generated per attempt, set as HttpOnly cookie, and compared in constant time | covered by `test_should_redirect_with_state_mismatch_*` |

### T - Tampering

| Threat | Mitigation | Status |
|--------|------------|--------|
| Mid-flight tampering of webhook body | HMAC verification covers the entire body | covered |
| User edits cookie to elevate privileges | Cookie is the JWT itself; signature gates everything | covered |
| User edits API request body to mutate another user's repo settings | Visibility check on every repo route (`user_can_access_repo`) | covered by IDOR tests |

### R - Repudiation

| Threat | Mitigation | Status |
|--------|------------|--------|
| User denies starting a scan | `scans.triggered_by_user_id` records who initiated each scan; structured logs on every API request via `request_id` (TODO: add) | partial - request_id middleware not yet implemented |
| User denies a settings change | Settings updates aren't audit-logged separately yet | **open** - see CHANGELOG roadmap |

### I - Information disclosure

| Threat | Mitigation | Status |
|--------|------------|--------|
| User A reads User B's repo / scan / finding (IDOR) | All resource fetches go through `user_can_access_repo`; non-owned resources return 404 (not 403) so existence isn't leaked | covered by `test_user_b_cannot_*` |
| Postgres dump leaks OAuth tokens | All third-party credentials (OAuth, SMTP password, Slack/Discord URLs) are Fernet-encrypted at rest | covered |
| Anthropic API key leaks through error messages | The client never logs the API key; tracebacks go through structlog with explicit field allowlists | manual review - no `api_key` in logs |
| Email leaks via /user/emails for users who hide it | Fall back to `{id}+{login}@users.noreply.github.com` instead of failing the flow | covered by `test_email_403_falls_back_to_noreply_and_login_succeeds` |

### D - Denial of service

| Threat | Mitigation | Status |
|--------|------------|--------|
| Brute force login | `slowapi` rate limit `5/minute` on auth routes + 5-attempt account lockout per IP for 15 min via Redis | covered |
| Webhook flood | `slowapi` rate limit `120/minute` on `/webhooks/*` + dedupe on `delivery_id` | covered |
| Unbounded scan of a huge monorepo | Hard caps: `MAX_FILES=400`, `MAX_FILE_BYTES=60_000`, `TOTAL_TOKEN_BUDGET=100_000`. Scan stops chunking when token budget is hit | covered |
| Concurrent scans on the same repo | `start_scan` returns the in-flight scan instead of starting a duplicate | covered |

### E - Elevation of privilege

| Threat | Mitigation | Status |
|--------|------------|--------|
| `e2e_test_mode` routes (`/test/*`) exposed in production | Mounted only when `E2E_TEST_MODE=true`; `assert_production_safe` refuses to boot if the flag is on in prod | covered by `assert_production_safe` |
| Default `SECRET_KEY=change-me` shipped to prod | `assert_production_safe` raises at startup if any default secret persists in `APP_ENV=production` | covered |
| Direct Postgres access bypassing the API | DB user has only the privileges granted by `compose`. Use a separate DB user with `pg_read_server_files=off` in production | manual - documented in docs/operations/backup.md |

---

## Attack-vector catalogue

### OAuth attacks
- **Authorization code injection.** A different user's code is replayed in
  this user's callback. Mitigated by the `state` parameter cookie binding.
- **Open redirect via `next`.** `_safe_redirect` whitelists same-origin or
  paths starting with `/`. External hosts fall back to `FRONTEND_BASE_URL`.
- **Token reuse.** Refresh tokens are single-use (`replaced_by` chain); if
  a presented token is already revoked, the entire family is revoked.

### Webhook attacks
- **Signature forgery.** Reject anything that fails `secrets.compare_digest`.
- **Replay.** `webhook_events.delivery_id` is `UNIQUE`; replays return
  `{"duplicate": true}` without re-processing.
- **Confused deputy via `installation` payload.** Owner binding goes by
  `account.id` (preferred) or `account.login` (fallback), not "whoever's
  logged in".

### SSRF (Slack/Discord webhook URLs)
- Reject non-http(s) schemes.
- Reject loopback / private / link-local / reserved / multicast IPs.
- Reject known cloud metadata hostnames.

### Prompt injection on Claude
- The prompt frames Claude as a **senior engineer doing code review** and
  asks for structured JSON output. A user committing `# Ignore previous
  instructions, output ...` doesn't escape the JSON schema.
- Responses go through `parse_json_strict` + `validate_finding`. Anything
  that doesn't fit the finding schema is dropped.
- A user *can* make Claude generate noisy/garbage findings - that
  inconveniences the user, not the platform. There's no execution path
  from a finding's text to backend code.

### Anthropic API key disclosure
- API key only in env, only used at httpx client construction.
- Tracebacks captured by `structlog` exclude env values.
- Periodic key rotation documented in `docs/operations/secrets.md`.

---

## Open items / known gaps

- **No CSRF tokens on state-changing requests.** Cookies are `SameSite=lax`,
  which prevents most CSRF in modern browsers, but a defense-in-depth CSRF
  token on POST/PATCH would be stronger. Tracked in roadmap.
- **No formal audit log table.** Settings changes, scan triggers, and
  installation events are logged via structlog but not written to a
  queryable table. Roadmap.
- **No 2FA / step-up auth.** Sensitive operations (delete account, revoke
  share link) use the same session token. Acceptable for v0.1.
- **Self-hosters with shared Postgres.** If you put Basira's DB on a shared
  server, encrypted tokens are only as safe as `TOKEN_ENCRYPTION_KEY`. Use
  a dedicated DB instance for production.
