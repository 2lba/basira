# Basira

> We see what you don't.

AI code reviews on every GitHub pull request. Open source. Self-hosted. Free.

The name is Basira (Arabic: بصيرة) — insight, foresight. The tool reads your
diffs and tells you what you missed before a reviewer does.

Status: v0.1.0 — early, but feature-complete enough to dogfood. Not battle tested at scale.

## what it does

1. You install the basira GitHub App on your repo.
2. Someone opens a pull request.
3. basira fetches the diff, sends it to Claude with a structured prompt, and posts a review back to the PR — summary comment plus inline comments where it matters.
4. You read, dismiss, or fix.

## stack

- python 3.13, fastapi, sqlalchemy 2 async
- postgres 16, redis, arq workers
- react 19, vite, tailwind 3
- claude api (anthropic) — sonnet-4-5 by default
- github app + webhooks
- docker compose for local dev

## install

You need:

- docker + docker compose
- a github account (to register the app)
- an anthropic api key

### 1. clone and configure

```
git clone <this repo>
cd basira
cp .env.example .env
```

Fill in `.env`:

- `SECRET_KEY` — random string, generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `TOKEN_ENCRYPTION_KEY` — Fernet key, generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com
- `GITHUB_APP_ID`, `GITHUB_APP_NAME`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_WEBHOOK_SECRET`, `GITHUB_APP_PRIVATE_KEY_PATH` — see step 2

### 2. set up the GitHub App

basira talks to GitHub through a GitHub App that you own. The App's URL slug
is what users see when they install it on a repo — it must match
`GITHUB_APP_NAME` in your `.env`.

For local development the default is `basira-dev`. Pick whatever slug GitHub
gives you and set both:

```
GITHUB_APP_NAME=basira-dev          # appears in github.com/apps/{name}
```

Steps to register the App:

1. Go to https://github.com/settings/apps → New GitHub App
2. **GitHub App name**: must match `GITHUB_APP_NAME` (e.g. `basira-dev`). The
   slug must be globally unique on GitHub — pick something specific to you.
3. Homepage URL: wherever you host basira (or your repo URL while testing)
4. Webhook URL: `https://your-domain/webhooks/github`
5. Webhook secret: pick a long random string, put it in `.env` as `GITHUB_APP_WEBHOOK_SECRET`
6. Permissions: Repository contents (read), Pull requests (read+write), Metadata (read), Email addresses (read)
7. Subscribe to events: Pull request, Installation, Installation repositories
8. Save. Note the App ID, Client ID, Client Secret. Generate a private key (.pem) and save it as `secrets/github-app-key.pem` with `chmod 600`.
9. Fill `.env` with `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github-app-key.pem`

The "Install on GitHub" button inside the app builds its URL from
`GITHUB_APP_NAME`, so if you ever rename the App on GitHub, update the env
var to match.

### 3. boot it

```
make build
make up
make migrate
```

Then open http://localhost:5173 — sign in with GitHub and install the app on a repo. Open a PR. Watch basira comment.

For development the backend listens on port 8001 on the host (mapped from container port 8000).

## features

- structured json reviews (severity, category, line anchors)
- per-repo settings: enable/disable, severity threshold, ignored paths (regex), custom rules, model override
- diff chunking that respects token budget per request and total budget per PR
- idempotent re-reviews on PR resync (diff hash dedup)
- review history dashboard with token usage and rough cost tracking
- HMAC SHA-256 webhook signature verification
- single-use refresh tokens with reuse detection
- account lockout on repeated failed logins
- structured json logging via structlog

## honest comparison vs CodeRabbit

basira is aiming for roughly 60-70% feature parity. Things missing that CodeRabbit has:

- chat replies on review threads (you can't ask basira follow-up questions yet)
- custom rules engine beyond plain-text instructions
- learning from feedback / training on your team's preferences
- multi-model consensus
- a polished marketing site

What basira does better:

- free, self-hosted, no per-seat pricing
- transparent prompts (read `app/services/prompt.py` to see exactly what basira tells Claude)
- your code never leaves your infra except for the Claude API call

## limits in v0.1.0

- one user per deployment (single-tenant)
- review re-syncs post a new review instead of editing the old inline comments (GitHub API limit; we leave the old summary in place)
- no IDE plugins
- no Gitlab/Bitbucket
- works best on Python, JS/TS, Go, Rust, Java; weaker on niche languages

## development

```
make build       # build images
make up          # start the stack
make logs        # tail logs
make test        # run pytest in the backend container
make fmt         # black + ruff --fix
make lint        # ruff + black --check
make migrate     # alembic upgrade head
make migration m="message"  # autogenerate
```

## project layout

```
backend/
  app/
    api/routes/   fastapi routes
    core/         config, security, deps, logging
    db/           session, base
    integrations/ github, anthropic clients
    models/       sqlalchemy orm
    schemas/      pydantic
    services/     business logic
    workers/      arq jobs
  alembic/        migrations
  tests/
frontend/
  src/
    pages/        route components
    components/   layout, ui
    hooks/        useSession, etc
    api/          client
docs/
deployment/
.github/workflows/  ci
```

## contributing

Issues and PRs welcome. Keep the spirit of "small, sharp, honest code". No marketing language. No emoji. No conventional-commit prefixes — just lowercase short messages.

## license

MIT
