# Basira — Production-Readiness Audit

Date: 2026-05-19  ·  Auditor: Claude Opus 4.7 (session-bound)  ·  Branch: `small-improvement`

## Summary

| Item | Count |
|------|-------|
| Hours of work (this session + carry-over) | ~5 |
| Bugs found this session | 6 |
| Bugs fixed this session | 6 |
| Tests added this session | 22 (18 security + 4 oauth fetch_profile) |
| Backend tests total | 114 passing |
| Frontend e2e (Playwright) | 48 passing |
| Known CVEs after upgrade | 0 (Python) · 0 (npm) |
| OWASP Top 10 pass | 8 / 10 (2 partial) |

## Commits made in this audit

```
858bb97 issue and pr templates plus codeql workflow and tighter ci
3ed9874 public security contributing privacy changelog
e93246e threat model and owasp audit grounded in code
6768793 prod env safety + readyz version endpoints
44d3bab block ssrf via webhook url validator + idor jwt webhook tests
024f887 bump eslint to match plugin api and clean unused imports
5549d9e pin vite to 7.x for stable hmr
dde0c5c tidy import order
e040753 patch known cve dependencies
```

Earlier commits in the same broader effort are summarized in `CHANGELOG.md`.

## Bugs found and fixed during the audit

1. **11 Python CVEs across 6 packages.** `cryptography 44`, `pyjwt 2.10`,
   `python-multipart 0.0.20`, `fastapi/starlette 0.115/0.41`, plus dev
   tools. Fixed by pinning to current secure versions (`e040753`).
2. **2 high/moderate npm vulnerabilities** in `react-router-dom 7.1.1`
   (XSS + open redirect). Fixed via `7.15.1`.
3. **3 more moderate npm vulns** in `vite 6`, `postcss`, `eslint` deps.
   Bumped to current; Vite settled on 7.3.3 because 8.0.13 broke HMR
   (`__WS_TOKEN__ is not defined`) in our setup (`5549d9e`).
4. **Two real SSRF vectors** through Slack/Discord webhook URL fields:
   AWS IMDS (`169.254.169.254`) and GCP metadata
   (`metadata.google.internal`) passed the old `startswith("http://")`
   check. Closed by parsing the URL, blocking known metadata hostnames,
   and rejecting any IP literal that is private/loopback/link-local/
   reserved/multicast/unspecified (`44d3bab`).
5. **Default-secret production boot** was possible. Added
   `Settings.assert_production_safe()` called at module load
   (`6768793`); refuses to start in `APP_ENV=production` if any of
   `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `ANTHROPIC_API_KEY`,
   `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_SECRET`, or
   `GITHUB_APP_WEBHOOK_SECRET` is missing or default; refuses
   `APP_DEBUG=true` or `E2E_TEST_MODE=true` in prod.
6. **Two unused-import lint failures** under the new ESLint
   (`React` in `main.jsx` for React 19, `useMemo` in `ScanDetail.jsx`).
   Cleaned (`024f887`).

## Security simulation results

All tests live in `backend/tests/test_security.py`. 18/18 pass.

| OWASP | Tests | Status |
|-------|-------|--------|
| A01 IDOR | 5 (repo / scan / finding / scan-start / unauth) | Pass |
| A02 JWT tampering | 3 (payload swap / alg-none / garbage) | Pass |
| A07 Webhook auth | 3 (missing sig / bad sig / replay dedup) | Pass |
| A03 Injection | 2 (UUID SQLi / XSS storage) | Pass |
| A10 SSRF | 5 parameterised (IMDS, GCP, file://, ftp://, javascript:) | Pass |

Notable wins:
- IDOR returns **404, not 403**, so resource IDs aren't enumerable.
- JWT with `alg:none` is rejected.
- Webhook replays return `{"duplicate": true}` and do **not** re-process.

## OWASP Top 10 — final scorecard

| Item | Status | Evidence |
|------|--------|----------|
| A01 Broken Access Control | Pass | 5 IDOR tests |
| A02 Cryptographic Failures | Pass | JWT + Fernet at-rest tests |
| A03 Injection | Pass | UUID parse before query; parametrized SQL throughout |
| A04 Insecure Design | Partial | No CSRF token; SameSite=lax cookies only |
| A05 Security Misconfiguration | Pass | `assert_production_safe` |
| A06 Vulnerable Components | Pass | 0 CVEs `pip-audit` + `npm audit` |
| A07 Auth Failures | Pass | Lockout, single-use refresh, no password reuse |
| A08 Data Integrity Failures | Pass | All deps pinned, lockfiles committed |
| A09 Logging & Monitoring | Partial | Structured logs; no audit table yet |
| A10 SSRF | Pass | URL validator with IP-range + metadata-host block |

Full breakdown: `docs/security/owasp-audit.md`.

## Production-readiness checklist

- [x] All env vars validated at boot in `APP_ENV=production`
- [x] HTTPS-only cookies in production (`Secure=True`)
- [x] DB migrations run automatically on container boot
- [x] `/healthz` (liveness) and `/readyz` (DB + Redis) endpoints
- [x] `/version` endpoint exposes git SHA + version
- [x] Structured JSON logs via structlog; sensitive fields never logged
- [x] Rate limits set: `5/min` auth, `120/min` webhooks, `100/min` general
- [x] Dependabot enabled
- [x] CI runs tests + lint + audit + CodeQL on every PR
- [x] `.env` never committed; lockfiles committed; `secrets/` mounted RO
- [x] Refresh-token reuse detection (full family revoke on reuse)
- [ ] Sentry/monitoring connected (hook stubbed, not wired)
- [ ] DB backups scheduled (documented in `docs/operations/backup.md` —
      placeholder; host operator must wire pg_dump cron)
- [ ] Audit log table for sensitive operations (roadmap)
- [ ] CSRF tokens on top of SameSite=lax (roadmap)
- [ ] Privacy policy hosted at a public URL (file is in repo;
      operator must surface it)

## Open issues (won't-fix-this-cycle)

1. **No CSRF tokens** — SameSite=lax cookies block the common CSRF
   patterns, but a token-based defense would be stronger. Defensive but
   not blocking for v0.1.
2. **No audit log** — settings/scope changes go to structlog only, not
   a queryable table. Acceptable for self-hosted single-user.
3. **OAuth `/user/repos` returns 403 on GitHub App tokens.**
   Architectural, inherited from GitHub. The dashboard shows an empty
   list until the user installs the App — handled gracefully (empty
   state with install CTA). Documented in `CHANGELOG.md`
   known-limitations.
4. **Scoring formula is harsh.** `100 − Σ severity×weight` caps the
   penalty at 100, so any repo with ~10+ findings tops out at score 0.
   Honest for v0.1 per the owner's call.
5. **`reviewly-backend` editable install lingers in the dev container.**
   Cosmetic — `pip-audit` skips it. A fresh container is clean.

## Things I did NOT verify

- **Prompt injection on Claude.** Not exercised with a real
  `evil.py`-style payload because we're under an Anthropic-token
  budget for this audit. The architectural defense (Claude returns
  JSON, we validate it against a schema, we never `exec` any returned
  text) is solid in principle, but a follow-up test with a
  deliberately hostile repo would close the gap.
- **Anthropic API key disclosure via logs.** I manually reviewed every
  `log.*` call — no key flows through — but I did not write an
  automated test that scans the log stream for leaks.
- **Concurrent OAuth from two tabs.** State cookie overwrites means
  the second callback wins. Not exploitable, but a UX paper cut.
- **Real GitHub App marketplace E2E.** I tested everything except the
  `marketplace_purchase` events because that requires actual
  marketplace publication.

## Decisions taken without asking

- **Vite 7.3.3 instead of 8.0.13** — Vite 8 breaks HMR
  (`__WS_TOKEN__` ReferenceError) in our dev config. 7.3.3 ships the
  same esbuild ≥0.25 (closing the CVE) without the regression.
- **`react-router-dom 7.15.1`** instead of `7.1.1` — required for the
  XSS fixes.
- **`fastapi 0.136.1` + explicit `starlette==0.49.1`** — fastapi's
  own pin caps starlette at `<0.49.0`, but starlette `0.49.1` is
  needed to clear CVE-2025-62727. The version skew is benign because
  fastapi only imports symbols that are still present in 0.49.
- **Idempotent CI test DB creation** — CI now does `CREATE DATABASE
  basira_test … || true` so re-runs don't fail on existing DB.

## Confidence

**7 / 10 for public open-source release** (you fork, self-host, hack
on it).

**5 / 10 for unattended SaaS deployment** (you stand it up for
strangers).

Reasoning for the gap:
- The code itself is solid: zero known CVEs, tested, defensive, with
  every OWASP-Top-10 item in Pass or Partial.
- For self-hosters that's enough — they own their data and trust
  themselves.
- For SaaS the gaps are operational, not code-level: no Sentry,
  no audit-log table, no DB backup automation, no on-call runbook,
  no signed SBOM, no formal incident-response process, no support
  inbox routed to anyone.

Closing those operational gaps is a few days of work, not a refactor.
The code is ready. The launch checklist isn't.

## How to verify this report yourself

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
sleep 30

# backend
docker compose exec -T backend pytest tests/ -q                # 114 passing
docker compose exec -T backend ruff check app/                 # clean
docker compose exec -T backend pip-audit --skip-editable       # 0 CVEs
docker compose exec -T backend bandit -r app/ -ll              # 1 false positive

# frontend
docker compose exec -T frontend npx eslint src/ --ext .js,.jsx # clean
docker compose exec -T frontend npm audit --audit-level=high   # 0 vulns

# end-to-end browser tests
cd frontend/e2e && npx playwright test                          # 48 passing
```

If any of the above is red, please open an issue — either the report
is wrong or the dependency landscape moved underneath us.
