# architecture

A short tour for someone reading the code for the first time.

## flow

```
github → webhook → backend → arq → worker → claude → github
```

1. `POST /webhooks/github` (FastAPI) verifies HMAC SHA-256 with `GITHUB_APP_WEBHOOK_SECRET`.
2. It records the event in `webhook_events` keyed by `X-GitHub-Delivery` (idempotent on replay).
3. For `pull_request` events with action `opened|synchronize|reopened|ready_for_review`, it upserts the repository and PR rows, then enqueues a job on the arq queue keyed by `review:<pr_id>` (dedup).
4. The arq worker (`app.workers.main.review_pr`) loads the PR, runs `services.review_engine.run_review`, then `services.comment_poster.post_review_to_github`.
5. `run_review` fetches PR files via the installation-scoped GitHub client, parses each file's patch into hunks, skips ignored/binary files, packs the rest into token-bounded chunks, and calls Claude once per chunk.
6. Each response is parsed as JSON, line numbers validated against the actual diff, severity/confidence filtered, then the merged result is saved into `reviews` + `review_comments`.
7. The poster builds one summary comment plus up to 20 inline comments and posts them via `POST /repos/{o}/{r}/pulls/{n}/reviews`.

## diff hash dedup

`compute_diff_hash` hashes filename + each hunk header + body. If we've already produced a `succeeded` or `posted` review for this PR with the same hash, we short-circuit. PR resync that didn't actually change the diff (e.g. ci re-trigger) won't re-spend tokens.

## token management

- each chunk: bounded by `DEFAULT_CHUNK_TOKEN_BUDGET` (~8k token-equivalents using a 4-char/token proxy)
- per PR: bounded by `DEFAULT_TOTAL_TOKEN_BUDGET` (~100k)
- single file too big for one chunk: split across hunks, each piece keeps the filename so the model still has context
- if a single hunk is too big: truncate body (rare in practice; flagged in the prompt)

## security model

- Webhooks: HMAC SHA-256, constant-time compare, 10MB body cap.
- User sessions: HttpOnly cookies, JWT access (1h) + opaque refresh (7d, single-use). Refresh token reuse revokes the whole family.
- GitHub access tokens: encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).
- GitHub App private key: separate file, chmod 600 enforced when `APP_ENV=production`.
- Rate limits: 100/min general, 5/min for auth, 120/min for webhook.
- Account lockout: 5 failed auth attempts per 15 min, redis-backed.

## scope of failure

- Claude API down → tenacity retries with exponential backoff, then fails the review (status=failed, error stored).
- Bad JSON from Claude → one re-prompt with stricter wording.
- Invalid line numbers from Claude → drop the line anchor, keep the comment as file-level.
- GitHub posting fails → review stays at `succeeded`, won't try to repost automatically. (TODO: a retry queue.)

## what we don't model

- multi-tenant orgs - single owner per deployment for v0.1
- chat replies on review threads
- per-PR token budget overrides
- streaming responses from Claude

## directories you'll touch most

- `app/services/review_engine.py` - the orchestration
- `app/services/prompt.py` - the prompt
- `app/services/chunker.py` - how diffs are sliced
- `app/integrations/github_api.py` - REST calls
- `app/api/routes/webhooks.py` - entry point
