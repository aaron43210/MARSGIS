#!/usr/bin/env sh
# MarsGIS backend container entrypoint: migrate (PostgreSQL only) then serve.
#
# - PostgreSQL target  -> run `alembic upgrade head` (owns the PostGIS extension,
#   the IAU 104905 spatial_ref_sys row, geometry columns and GiST indexes).
# - Any other target (the zero-setup SQLite fallback) -> skip Alembic; the app's
#   startup lifespan bootstraps the schema via SQLModel.metadata.create_all.
#
# If arguments are passed (e.g. the dev override supplies `uvicorn --reload`),
# migrations still run first and then those arguments are exec'd. With no
# arguments the production uvicorn command is started.
set -eu

: "${DATABASE_URL:=sqlite+aiosqlite:///./storage/marsgis.db}"

case "${DATABASE_URL}" in
  postgresql* | postgres*)
    echo "[entrypoint] PostgreSQL target detected -> alembic upgrade head"
    alembic -c alembic.ini upgrade head
    ;;
  *)
    echo "[entrypoint] Non-Postgres DATABASE_URL -> skipping Alembic (app create_all handles schema)"
    ;;
esac

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# The in-process job runner keeps its queue in process memory and treats any
# `running` row it finds at startup as its own orphan, so it must be the ONLY
# web worker. Multiple workers are only safe with JOB_BACKEND=arq.
WORKERS="${WEB_CONCURRENCY:-2}"
if [ "${JOB_BACKEND:-inprocess}" != "arq" ] && [ "${WORKERS}" != "1" ]; then
  echo "[entrypoint] JOB_BACKEND=${JOB_BACKEND:-inprocess} requires one web worker; ignoring WEB_CONCURRENCY=${WORKERS}"
  WORKERS=1
fi

exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WORKERS}"
