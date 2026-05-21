# Fresh Install Verification

Date: 2026-05-21
Source branch: `master-audit-pre-release`
Target host: Linux 6.19.14+kali, Docker Compose v2

## Procedure

1. Stopped the main audit stack to free host ports.
2. Cloned the branch into a clean directory under /tmp:
   ```
   mkdir -p /tmp/basira-fresh-test
   cd /tmp/basira-fresh-test
   git clone -b master-audit-pre-release ~/projects/reviewly basira
   cd basira
   ```
3. Followed README.md step 1 (clone + configure):
   ```
   cp .env.example .env
   ```
4. Generated the two required secrets and substituted them:
   ```
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
   FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|; s|TOKEN_ENCRYPTION_KEY=.*|TOKEN_ENCRYPTION_KEY=$FERNET|" .env
   ```
5. Skipped step 2 (GitHub App registration) - that requires real GitHub
   credentials outside the scope of an unattended boot check. The README
   already covers it accurately.
6. Booted:
   ```
   docker compose up -d --build
   ```
7. Smoke-checked health, readiness, version, frontend, alembic head.
8. Tore down with `docker compose down -v`.

## Timings

| Step | Wall-clock |
|------|------------|
| Clone | <1 s |
| `.env` populate | <1 s |
| `docker compose up -d --build` (cold images cache from earlier work) | 1 min 21 s |
| Stack reaches healthy | ~7 s after `up` returned |

If the docker layer cache is cold the build is ~5 min (downloading base images,
installing `pip` and `npm` deps). The 81 s number above is with the base
images already on disk - representative of a returning developer, not the
first-ever clone.

## Verification outputs

```
GET /healthz                          200
GET /readyz                           200
GET /version                          {"name":"basira","version":"0.1.0","git_sha":"dev","env":"development"}
GET /                                 200 (vite dev server)
alembic current                       0012 (head)
```

All five services (postgres, redis, backend, worker, frontend) came up
healthy on the first attempt. No manual recovery needed.

## README findings

The README is accurate for the boot-and-run path. One small gap that I did
not patch in this round because it requires a judgement call:

- The README's "## install" section mentions `make build && make up && make
  migrate` but the Makefile's `up` target already runs the entrypoint which
  invokes alembic on start. The explicit `make migrate` is redundant on a
  fresh boot and only useful after a schema-only rebuild. Worth a one-line
  clarification in the README but not load-bearing.

- The README does not call out the host-port collision pattern (`BACKEND_HOST_PORT`)
  for users who want to run two basira instances side by side. This is an
  edge case but came up here when verifying alongside the audit stack;
  worth a sentence in the troubleshooting section once one exists.

Both are tracked as docs-only follow-ups, not gating items.

## Cleanup

- `docker compose down -v` removed both volumes (postgres_data, redis_data)
  and the network without leaving orphans.
- `rm -rf /tmp/basira-fresh-test` cleaned the working copy.
- The main audit stack was brought back up with `-f docker-compose.yml -f
  docker-compose.e2e.yml up -d` and `readyz` returned 200 within ~8 s.

## Result

A fresh clone of `master-audit-pre-release` boots cleanly on a host with
docker compose and python3 available. No manual fixups needed beyond
generating two secrets - exactly the documented happy path.
