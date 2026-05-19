# OWASP Top 10 (2021) — Basira audit

For each item: a **Status** (Pass / Partial / Open / N/A) and the concrete
controls that earn it. Anything that says "Partial" or "Open" is in the
roadmap.

## A01 — Broken Access Control

**Status: Pass**

- Every repo / scan / finding endpoint resolves the user from the session,
  then checks `user_can_access_repo(db, user.id, repo_id)` before reading
  or writing.
- Non-owned resources return **404, not 403**, so an attacker can't
  enumerate IDs.
- Tests: `backend/tests/test_security.py::test_user_b_cannot_*` cover
  repo, scan, finding, and scan start.
- Unauthenticated requests return 401, not 500: covered by
  `test_unauthenticated_caller_gets_401_not_500`.

## A02 — Cryptographic Failures

**Status: Pass**

- JWT: HS256 with a server-only `SECRET_KEY`. Tampered payloads rejected
  (`test_tampered_jwt_payload_is_rejected`). `alg:none` rejected
  (`test_jwt_with_empty_signature_is_rejected`).
- Passwords: **none stored** — auth is via GitHub OAuth. `bcrypt` is
  pinned but unused; kept for future basic-auth fallback.
- OAuth tokens: encrypted at rest with Fernet (`token_encryption_key`).
- SMTP password / Slack URL / Discord URL: same Fernet pipeline.
- TLS: terminated by the deploy target (Caddy/ngrok/nginx). Cookies set
  `Secure=True` only when `APP_ENV=production`; in dev they're plain so
  `localhost` works without a cert.

## A03 — Injection

**Status: Pass**

- SQLAlchemy parametrizes every query. No `text(...)` queries take user
  input; the two exceptions are alembic migrations and the test
  `TRUNCATE` statement.
- UUID inputs go through `uuid.UUID(...)` before any DB lookup, so
  malformed paths get a 400 — never reach the query.
- Tests: `test_sql_injection_in_uuid_param_is_rejected_cleanly`.
- Shell: no `subprocess` / `os.system` calls in the request path.

## A04 — Insecure Design

**Status: Partial**

- Authorization is checked *before* I/O on every endpoint.
- Webhook handler is **idempotent by delivery_id**, so retries from
  GitHub can't double-write.
- **Open**: no explicit CSRF token on state-changing endpoints. We lean
  on `SameSite=lax` cookies. Roadmap.

## A05 — Security Misconfiguration

**Status: Pass**

- `assert_production_safe()` runs once at startup and refuses to boot in
  `APP_ENV=production` if any of these are still default / unset:
  `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `ANTHROPIC_API_KEY`,
  `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_WEBHOOK_SECRET`.
  Also refuses `APP_DEBUG=true` or `E2E_TEST_MODE=true` in prod.
- `/test/*` routes are mounted only when `E2E_TEST_MODE` is enabled.
- `docs_url=None` / `openapi_url=None` in production builds.
- `SecurityHeadersMiddleware` sets `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy` clamping accelerometer/camera/geo/mic.

## A06 — Vulnerable and Outdated Components

**Status: Pass (zero known CVEs at audit time)**

- `pip-audit`: 0 vulnerabilities after the wave-5 dependency upgrade
  (commit `e040753 patch known cve dependencies`). Patched:
  `cryptography 44 → 46.0.7`, `pyjwt 2.10 → 2.12.0`,
  `python-multipart 0.0.20 → 0.0.27`, `fastapi 0.115 → 0.136.1`,
  `starlette 0.41 → 0.49.1`.
- `npm audit`: 0 vulnerabilities after `react-router-dom 7.1 → 7.15.1`,
  `vite 6 → 7.3.3`, `eslint 9 → 10.4.0`, `postcss → 8.5.15`.
- Dependabot enabled (`.github/dependabot.yml`).
- CI runs `pip-audit` and `npm audit` on every PR (see
  `.github/workflows/ci.yml`).

## A07 — Identification and Authentication Failures

**Status: Pass**

- Session: HttpOnly JWT cookie, 1-hour access TTL, 7-day refresh TTL,
  single-use refresh with reuse detection (entire family revoked).
- Account lockout: 5 failed OAuth attempts per IP in a 15-minute window;
  enforced via Redis counter.
- No password reuse vector — we don't store any password.
- MFA: handled by GitHub, so we inherit whatever the user configured
  there.

## A08 — Software and Data Integrity Failures

**Status: Pass**

- All dependencies pinned to exact versions (`==`) in `pyproject.toml`
  and `package.json`.
- Lockfiles committed.
- Webhook handler trusts GitHub's signature, then resolves the
  installation owner by `account_id`/`account_login` so a renamed user
  can't hijack another user's installation.

## A09 — Security Logging and Monitoring Failures

**Status: Partial**

- Structured logs via `structlog`, JSON-formatted in production.
- Login / OAuth callback / webhook handler / scan start all emit named
  events.
- **Sensitive fields are not in logs**: no `access_token`, no
  `client_secret`, no `password` ever flows into `log.info` calls.
- **Open**: no audit table for settings/scope changes; relying on log
  retention. A Sentry hook is stubbed but not wired. Roadmap.

## A10 — Server-Side Request Forgery

**Status: Pass**

- Slack / Discord webhook URL validator (`_validate_webhook_url`):
  - Scheme must be `http` or `https`
  - Length cap 2048
  - Hostname rejected if in `_BLOCKED_HOSTS` (metadata.google.internal,
    169.254.169.254, localhost, etc.)
  - If host parses as an IP literal, reject when
    private/loopback/link-local/reserved/multicast/unspecified
- Tests: `test_slack_webhook_rejects_non_http_schemes` covers `file://`,
  `ftp://`, `javascript:`, AWS IMDS, GCP metadata.
- No other endpoint takes a URL from the user and follows it.
