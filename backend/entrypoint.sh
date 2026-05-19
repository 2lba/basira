#!/usr/bin/env bash
# Boot the API or worker, but first make sure the schema is at head.
# Without this, `docker compose down -v && up` leaves an empty database
# and every OAuth callback dies with "relation users does not exist".
set -euo pipefail

ROLE="${1:-api}"
shift || true

echo "[entrypoint] role=$ROLE"
echo "[entrypoint] running alembic upgrade head…"
alembic upgrade head

case "$ROLE" in
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload "$@"
    ;;
  worker)
    exec arq app.workers.main.WorkerSettings "$@"
    ;;
  *)
    exec "$ROLE" "$@"
    ;;
esac
