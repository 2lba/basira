# reviewly

AI code reviews on every GitHub PR. Open source, self-hosted, free.

Status: early development, not ready for use.

## stack

- python 3.13 / fastapi / sqlalchemy 2 async
- postgres 16, redis, arq workers
- react 19, vite, tailwind 3
- docker compose for local dev

## local dev

```
cp .env.example .env
make build
make up
make migrate
```

Then open http://localhost:5173 for the dashboard and http://localhost:8000/docs for the API.

## layout

```
backend/   fastapi app, models, workers, alembic migrations
frontend/  react dashboard + landing
docs/      architecture and api notes
```

## license

MIT
