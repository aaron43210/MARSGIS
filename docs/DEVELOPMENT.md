# Development

Docker + `docker compose` is the **source of truth** for the runtime
environment. `make test` / `make lint` run inside the pinned containers, so you
never depend on whatever the host happens to have installed.

## Toolchain pins (and why)

| Tool   | Containers / CI | Host (local, best-effort) | Why pinned |
| ------ | --------------- | ------------------------- | ---------- |
| Python | **3.12**        | 3.14                      | Broadest wheel coverage across numpy 2 / scikit-learn / pyproj / shapely / fiona / rasterio / FastAPI+pydantic. 3.14 is new and some transitive deps may still build from source. |
| Node   | **24 LTS**      | 26                        | Established LTS with universal tooling support; the frontend toolchain is pinned at Vite 7.3.7 / plugin-react 5.2.0 / TS 5.9.3. |

The host interpreter must not define the artifact. Docker/compose/CI are
authoritative; local non-Docker dev is a convenience.

### Non-Docker local dev

Install a **Python 3.12** interpreter alongside the host (3.14):

```bash
# uv
uv venv --python 3.12 .venv && source .venv/bin/activate
# or pyenv
pyenv install 3.12 && pyenv local 3.12
```

Then, per service:

```bash
pip install -e "./engine[dev]"
pip install -e "./backend[dev]"
cd frontend && npm install     # Node 24 (host 26 is fine)
```

## Common tasks

```bash
make up          # build + start db + backend + frontend (detached)
make dev         # same, with the dev overlay (backend --reload) following logs
make down        # stop
make logs        # follow logs
make test        # backend + engine (in containers) + frontend (host)
make lint        # ruff (backend/engine) + eslint (frontend)
make typecheck   # mypy + tsc --noEmit
make db-upgrade  # alembic upgrade head (PostgreSQL path)
make seed        # (re)seed the catalogue (idempotent; also runs on startup)
make clean       # down -v + prune local caches
```

### Frontend hot reload

The compose `frontend` service serves the production nginx build. For a
hot-reloading SPA, run the Vite dev server on the host:

```bash
cd frontend && npm run dev     # http://127.0.0.1:5173, proxies /api -> :8000
```

## Database switch (SQLite vs PostGIS)

Selected entirely by `DATABASE_URL`:

- **Zero-setup dev (SQLite):** `sqlite+aiosqlite:///./storage/marsgis.db`
  — the app bootstraps the schema with `SQLModel.metadata.create_all`; no
  migration step, no db container.
- **Production (PostgreSQL + PostGIS):**
  `postgresql+asyncpg://marsgis:...@db:5432/marsgis`
  — the backend container's entrypoint runs `alembic upgrade head` before
  serving; PostGIS owns the geometry columns + GiST indexes.

The default compose stack uses the PostGIS `db` service.

## Running the engine CLI

```bash
# On the bundled SYNTHETIC sample (offline; result labeled SYNTHETIC):
docker compose --profile engine run --rm engine run \
  --cube /work/sample/sample_crism_nili.img \
  --mineral carbonate \
  --out /data/results/sample

docker compose --profile engine run --rm engine list-minerals
docker compose --profile engine run --rm engine info --cube /work/sample/sample_crism_nili.img
```

The engine image bundles only the public-domain MICA type spectra as package
data; it carries **no** bulk/sample archive (enforced by `engine/.dockerignore`
and the pre-commit large-file guard).

## Configuration

All settings come from `.env` (copy `.env.example`). The ones you are most likely to change:

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `DATABASE_URL` | PostGIS in compose, SQLite otherwise | Database DSN |
| `JOB_BACKEND` | `inprocess` | `inprocess` or `arq` (needs `REDIS_URL`) |
| `JOB_CONCURRENCY` / `JOB_TIMEOUT_S` | `2` / `600` | Worker limits |
| `ENGINE_MODE` | `inprocess` | `inprocess`, `subprocess` or `container` |
| `ENGINE_IMAGE` | `ghcr.io/aaron43210/marsgis-engine:latest` | Image used when `ENGINE_MODE=container` |
| `ENGINE_CUBE_SOURCE` | `sample` | `sample` (synthetic) or `archive` (real CRISM cubes from PDS) |
| `STORAGE_ROOT` | `/data` | Result rasters, shared by backend and worker |
| `CORS_ORIGINS` | local frontend origins | Allowed browser origins |
| `REQUIRE_API_KEY` / `API_KEYS` | `false` / `[]` | **Turn on before exposing the API publicly** |
| `SECRET_KEY`, `POSTGRES_PASSWORD` | `change-me` | Must be changed outside local development |

## Images

All three images are multi-stage and run as a non-root user (uid 10001). The
engine/backend base is `python:3.12-slim-bookworm` with rasterio from PyPI
wheels (vendored GDAL ≥ 3.8 — there is no system `gdalinfo`); the frontend builds
on `node:24` and serves from `nginxinc/nginx-unprivileged`. See `docker/README.md`.
