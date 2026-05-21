# Switching between dev and e2e modes

A real footgun: `docker compose restart` does **not** drop compose-file
overrides. If you brought the stack up once with
`-f docker-compose.yml -f docker-compose.e2e.yml`, every subsequent
`restart`/`up` keeps those overrides until you run `docker compose down`.

## Symptom

Backend reads `localhost` URLs even though `.env` has the real ngrok
URLs:

```
$ curl -sI http://localhost:8001/auth/github/login
location: ...redirect_uri=http%3A%2F%2Flocalhost%3A8000%2F...
```

…and `docker compose logs backend` prints
`e2e_test_mode enabled; /test/* routes mounted` even though `.env` says
`APP_ENV=development` and there is no `E2E_TEST_MODE` line in it.

## Why

`docker-compose.e2e.yml` sets:

```yaml
services:
  backend:
    environment:
      E2E_TEST_MODE: "true"
      APP_BASE_URL: "http://localhost:8000"
      FRONTEND_BASE_URL: "http://localhost:5173"
```

`environment:` keys are merged **after** `env_file:` and win. Once the
backend container is created with the override, `restart` re-uses the
same container with the same merged environment.

## Fix

Don't `restart`. Do this instead:

```bash
docker compose down                                       # drops overrides
docker compose up -d --force-recreate backend worker      # re-reads .env only
```

For Playwright suites you actually want the override:

```bash
docker compose down
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
```

When you're done with Playwright, `docker compose down` and `up`
without the override puts you back on the real dev URLs.

## Verifying which mode you're in

```bash
docker compose exec backend env | grep -E "BASE_URL|E2E"
# expected (dev):
#   APP_BASE_URL=https://your-ngrok-domain/
#   FRONTEND_BASE_URL=https://your-ngrok-domain/
#   (no E2E_TEST_MODE line)

curl -s -o /dev/null -w '%{http_code}\n' \
    -X POST http://localhost:8001/test/seed
# 404 - good, /test/* not mounted

docker compose logs backend --tail=50 | grep -i e2e_test_mode || echo ok
# ok - no e2e warning

curl -s -X GET http://localhost:8001/auth/github/login -i | grep -i location
# Location should contain your real ngrok host, not localhost
```

If any of the four is wrong, run `docker compose down && docker
compose up -d` (without `-f docker-compose.e2e.yml`).
