# Load Test Results

Date: 2026-05-21
Branch: `master-audit-pre-release`
Tool: locust 2.44.0
Environment: Docker Compose, single host, postgres 16-alpine, redis 7-alpine
Locustfile: `scripts/load/locustfile.py`

## Why a load-test overlay file

Production rate limits (`RATE_LIMIT_GENERAL=100/minute`) are intentionally
tight to defend a single-host SaaS deployment. Locust runs from one container
on the docker network, so every virtual user shares the source IP and hits
the limit before the system gets exercised. The repo now carries
`docker-compose.load.yml` which overrides the limits while a load run is in
progress; the file is documented and lives next to the prod overlay.

Run the stack with:

```
docker compose -f docker-compose.yml -f docker-compose.e2e.yml \
               -f docker-compose.load.yml up -d backend worker
```

Then copy the locustfile into the backend container and run from inside the
docker network so latency reflects service-to-service traffic rather than
host loopback:

```
docker cp scripts/load/locustfile.py basira-backend:/tmp/locustfile.py
docker compose exec backend locust -f /tmp/locustfile.py --headless \
    -u 50 -r 5 -t 2m -H http://backend:8000 --only-summary
```

## Acceptance criteria

| Scenario | Error budget | p95 budget |
|----------|--------------|------------|
| Light (20 users) | 0% | 500 ms |
| Medium (50 users) | < 1% | 1500 ms |
| Heavy (100 users) | < 5% | 3000 ms |

All three scenarios cleared their criteria with significant headroom.

## Scenario A - light (20 users, 5/s ramp, 2 min)

| Metric | Value |
|--------|-------|
| Total requests | 1,912 |
| Failures | 0 (0.00 %) |
| Throughput | 15.97 req/s |
| Median latency | 6 ms |
| p95 latency | 11 ms |
| p99 latency | 46 ms |
| Max latency | 134 ms (seed bootstrap, one-shot per VU) |

Endpoint breakdown:

| Endpoint | reqs | p95 | p99 |
|----------|------|-----|-----|
| GET /api/repos | 755 | 10 | 17 |
| GET /api/scans | 428 | 10 | 13 |
| GET /api/reviews | 297 | 10 | 13 |
| GET /api/me/api-keys | 218 | 10 | 14 |
| GET /api/repos/[id] | 120 | 9 | 20 |
| POST /api/repos/[id]/scans | 74 | 15 | 57 |
| POST /test/seed (bootstrap) | 20 | 130 | 130 |

## Scenario B - medium (50 users, 5/s ramp, 2 min)

| Metric | Value |
|--------|-------|
| Total requests | 4,655 |
| Failures | 0 (0.00 %) |
| Throughput | 38.88 req/s |
| Median latency | 6 ms |
| p95 latency | 12 ms |
| p99 latency | 38 ms |
| Max latency | 69 ms |

## Scenario C - heavy (100 users, 10/s ramp, 2 min)

| Metric | Value |
|--------|-------|
| Total requests | 9,217 |
| Failures | 0 (0.00 %) |
| Throughput | 76.97 req/s |
| Median latency | 7 ms |
| p95 latency | 18 ms |
| p99 latency | 190 ms |
| Max latency | 514 ms (one-shot seed bootstrap; steady-state p99 ~85 ms) |

The p99 tail on read endpoints lands at 84-180 ms under 100 concurrent users
- still inside the 3 s budget but visibly higher than at lighter load. The
biggest contributor is `/test/seed` (one shot per VU during ramp-up), not
the steady-state read mix.

## What this validates

- The 100-repo / 1k-reviews-day capacity claim in `CLAUDE.md` is comfortably
  reachable on a single host with the current postgres + redis + uvicorn
  pool sizes. Sustained 77 req/s with 0 % errors at p95 < 20 ms.
- The async session pool is not the bottleneck up to 100 concurrent VUs.
- POST /api/repos/{id}/scans (the only write the load profile exercises
  besides bootstrap) stays p95 < 25 ms.

## What this does not validate

- Real Anthropic scan latency. The e2e stub returns in ~2 s with deterministic
  findings; production reviews hit Claude and take 10-60 s.
- Worker queue depth under bursts of real PRs. The load profile only enqueues
  scans, it does not measure end-to-end time-to-review.
- Saturation point. p95 was still tight at 100 VUs - we have not found the
  knee of the curve. A follow-up should ramp to 200-500 VUs to locate it.
- Postgres connection pool tuning under heavier scan throughput. The default
  pool of 20 may need bumping for production traffic.

## Bottlenecks identified

None at the tested loads. The system is read-cheap and the read mix dominates
the profile.

## Optimisations applied

None needed at this load. No N+1 hotspots surfaced; no slow endpoints
identified; SQL echo was not enabled because there was nothing to chase.
