# api

All authenticated endpoints expect the `basira_access` cookie set by the login flow. Errors use a consistent envelope:

```json
{ "error": { "code": "STRING_CODE", "message": "human readable", "details": {} } }
```

## auth

- `GET /auth/github/login` → 302 to GitHub OAuth, sets a state cookie
- `GET /auth/github/login-url` → `{ "url": "..." }` for SPAs that prefer to navigate themselves
- `GET /auth/github/callback?code=&state=` → exchanges code, sets session cookies, redirects back to the frontend
- `POST /auth/refresh` → rotates the refresh token, issues a new access token, sets cookies
- `POST /auth/logout` → revokes the refresh token, clears cookies
- `GET /auth/me` → `{ id, github_login, email, avatar_url }`

## repos

- `GET /api/repos` → list of repos visible to the current user
- `GET /api/repos/{id}` → repo detail
- `PATCH /api/repos/{id}` → update any of: `review_enabled`, `severity_threshold` (nit|minor|major|critical), `ignored_paths` (list of regex), `custom_rules`, `model_override`

## reviews

- `GET /api/reviews?limit=&offset=&repo_id=&status=` → review history, scoped to user's repos
- `GET /api/reviews/{id}` → review detail with comments, tokens, cost

## webhooks

- `POST /webhooks/github` → only callable by GitHub (HMAC-verified). Supported events:
  - `ping`
  - `pull_request` (actions: opened, synchronize, reopened, ready_for_review trigger reviews)
  - `installation` (created, deleted, new_permissions_accepted)
  - `installation_repositories` (added, removed)

  Returns `{ received, result | duplicate | ignored }`. Replays with the same `X-GitHub-Delivery` are idempotent.

## health

- `GET /healthz` → liveness `{ status: "ok" }`
- `GET /readyz` → liveness + db connectivity check
- `GET /` → `{ name, version }`

## error codes you'll see

- `NOT_AUTHENTICATED` - no session cookie
- `INVALID_TOKEN` - JWT bad or expired
- `OAUTH_STATE_MISMATCH` - CSRF state didn't match
- `OAUTH_DENIED` - user clicked "cancel" on GitHub
- `REFRESH_REUSED` - single-use refresh token was reused; session revoked
- `INVALID_WEBHOOK_SIGNATURE` - HMAC mismatch
- `WEBHOOK_PROCESS_FAILED` - handler couldn't make sense of the payload
- `REPO_NOT_FOUND` / `REVIEW_NOT_FOUND` - also returned when the user is not allowed to see the resource (don't leak existence)
- `BAD_SEVERITY`, `BAD_MODEL` - validation on PATCH /api/repos
- `RATE_LIMITED` - too many failed auth attempts from this IP
