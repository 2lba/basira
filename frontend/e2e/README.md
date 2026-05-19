## e2e tests

Playwright tests for the scan repository flow. Run on the host (the chromium
binary inside the alpine frontend container is missing system libs).

### Requirements
- backend and worker running with `E2E_TEST_MODE=true`
- frontend running on `localhost:5173`

### One-time setup
```
npm install
npx playwright install chromium
```

### Run
```
docker compose -f ../../docker-compose.yml -f ../../docker-compose.e2e.yml up -d
npm test
```

In e2e mode the scan engine produces canned findings without calling GitHub or
Claude. The `/test/seed` and `/test/reset` endpoints are mounted only when
`E2E_TEST_MODE=true`.
