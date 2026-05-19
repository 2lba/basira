# Changelog

All notable changes to Basira are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); dates are YYYY-MM-DD.

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-05-19

First public release. Scan-now flow works end-to-end on real
repositories; the rest of this list is what shipped.

### Features
- GitHub OAuth + GitHub App installation flow
- Repository discovery (connected via App + OAuth-visible via /user/repos)
- One-click "Scan now" — pulls the tree, chunks files by token budget,
  drives Claude with a structured-output prompt, persists findings with
  severity / category / suggestion
- Per-repo settings: enable/disable, severity threshold, ignored paths,
  custom rules, model override
- Scan history with score-trend chart
- Compare two scans (new / resolved / persisting findings)
- Mark resolved / false-positive / ignore-rule actions on findings
- Public share links (revocable, no-auth read)
- Markdown export of any scan
- Rescan-now button
- Scheduled scans (daily / weekly / monthly per repo)
- Email notifications (user-supplied SMTP, optional)
- Slack + Discord webhook notifications (optional)
- Unified settings page with tabs (Account, Notifications, API Keys)
- Onboarding tour on first visit
- Keyboard shortcuts (`/`, `n`, `g r/h/s/a`, `?`)
- Error toast bus with retry
- Skeleton screens during loading
- Empty states with a clear next step

### Security
- HMAC SHA-256 webhook signature verification (with replay dedup)
- HttpOnly + SameSite=lax session cookies; refresh-token rotation with
  reuse detection (full family revoke on reuse)
- Fernet at-rest encryption for OAuth tokens, SMTP passwords, and Slack
  /Discord webhook URLs
- Account lockout (5 attempts / 15 min) on failed OAuth via Redis
- SSRF guard on webhook URL fields (blocks loopback / private / cloud
  metadata)
- `assert_production_safe()` refuses to boot in `APP_ENV=production`
  with any default secret still in place
- All routes go through `user_can_access_repo` before reading or writing
  a repo / scan / finding (404, not 403, on miss — so IDs don't leak)
- OWASP Top 10 coverage in `docs/security/owasp-audit.md`
- Zero known CVEs (`pip-audit` + `npm audit` clean as of release)

### Production
- Backend auto-runs `alembic upgrade head` on boot
- `/healthz` (liveness), `/readyz` (DB + Redis), `/version` (build info)
- Structured logging via structlog
- Dependabot configured
- CI runs backend tests + frontend lint + Playwright + pip-audit +
  npm audit + CodeQL on every PR

### Known limitations
- One user per deployment (single-tenant). Org features are roadmap.
- OAuth `user/repos` returns 403 on most GitHub App user-to-server
  tokens; users with no installed repos see an empty dashboard until
  they install the App.
- Scoring formula is harsh — a repo with ~50 minor findings will score
  near 0. Intentional for v0.1.0.
- No formal audit log (use structlog output for forensics).
- No 2FA / step-up auth.
- IDE plugins, GitLab/Bitbucket support, and multi-AI consensus are not
  in scope for v0.1.

### Migration notes
- Renamed from internal codename "Reviewly". Old `.env`s using
  `REVIEWLY_*` won't load — copy `.env.example` to `.env` and re-fill.
- DB schema is at `0011`. `down -v` wipes data; `docker compose up`
  re-runs migrations automatically.
