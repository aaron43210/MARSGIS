# MarsGIS backend

FastAPI backend for MarsGIS: the Mars CRISM catalogue API, the asynchronous SAM
analysis job runner, and on-the-fly result raster tiling over a custom Mars
**geographic** TileMatrixSet that co-registers with the NASA Trek basemaps and
the Cesium Mars globe.

## Quick start (zero setup, SQLite, offline)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # also: pip install -e ../engine  (for the real engine)
marsgis-api                       # or: uvicorn app.main:app --reload
```

With no `.env` the app boots on **SQLite** (`storage/marsgis.db`), starts the
**in-process** job worker, uses the **in-process** engine seam, and seeds the
bundled catalogue/minerals/layers. Open http://127.0.0.1:8000/docs and
http://127.0.0.1:8000/api/health.

The default engine cube source is the bundled **synthetic** sample cube
(`engine/sample_data`). Every result produced from it is flagged
`synthetic_input: true` in its provenance and carries the candidate caveat — it
is a pipeline demonstration, **never** presented as a real Mars detection. Set
`ENGINE_CUBE_SOURCE=archive` (and stage the real MTRDR `_if` cube) for real data.

## Running the tests (offline)

```bash
pip install -e '.[dev]'
pytest -q
```

Tests use a `FakeEngineAdapter` that writes a tiny synthetic Mars COG, so the
full job → result → tile flow runs with no engine install and no network.

## Endpoints

All 12 endpoints match `contracts/openapi.yaml` exactly; the live `/openapi.json`
is pinned to that committed contract (CI asserts equality). See `/docs`.

- `GET /api/health`, `GET /api/layers`, `GET /api/observations[/{id}]`,
  `GET /api/minerals[/{id}]`, `POST|GET /api/analysis-jobs`,
  `GET /api/analysis-jobs/{id}`, `GET /api/results/{id}`,
  `GET /api/results/{id}/download`, `GET /api/results/{id}/tiles/{z}/{x}/{y}.png`,
  `GET /api/provenance/{id}`.
- `GET /api/results/{id}/preview.png` is a small-bbox SingleTile fallback (not in
  the OpenAPI contract).

## Configuration

Every variable is documented in `.env.example`. Key switches:

| Variable | Default | Production |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./storage/marsgis.db` | `postgresql+asyncpg://…` (PostGIS) |
| `JOB_BACKEND` | `inprocess` | `arq` (+ `REDIS_URL`, run `marsgis-worker`) |
| `ENGINE_MODE` | `inprocess` | `subprocess` or `container` (rlimits + timeout) |
| `ENGINE_CUBE_SOURCE` | `sample` (synthetic) | `archive` (real staged cube) |
| `REQUIRE_API_KEY` | `false` | **`true`** for any public deployment |

### Migrations

- SQLite dev: `SQLModel.metadata.create_all` runs on startup (no migration step).
- PostgreSQL prod: `alembic upgrade head` (enables PostGIS, registers IAU 104905
  in `spatial_ref_sys`, adds the `geometry(POLYGON,104905)` + GiST column). Run:
  `DATABASE_URL=postgresql+asyncpg://… alembic upgrade head`.

## Cesium contract

Result overlays use the custom **MarsEQC** geographic TMS: 2 columns × 1 row at
z0, 256 px tiles, matching Trek's `default028mm` grid. `AnalysisResult.map_layer`
(`type=result_tiles`, `tile_order=zxy`) is the ready-to-add Cesium layer; the
frontend does no raster math. Coordinates are Mars IAU 2000 degrees, not WGS84.

## Security (READ THIS)

The API is **unauthenticated by default** for the zero-friction demo. `POST
/api/analysis-jobs` is a compute surface, so it is hard-bounded: a closed-enum
method (no arbitrary exec), per-client concurrency + hourly quota (→ 429), a
per-job wall-clock timeout, CPU/memory rlimits on the subprocess/container engine
path, catalogue-only observation ids, and path-traversal-safe downloads. **For
any real/public deployment set `REQUIRE_API_KEY=true` and populate `API_KEYS`.**

## Scientific honesty

A SAM candidate match is **not** a confirmed mineral deposit. The caveat
(`contracts/enums.json#caveats.candidate_match`) is a required field on every
`AnalysisResult`, `SummaryStats`, `Legend` and `Provenance`; the continuous angle
raster is always retained alongside the thresholded mask. Synthetic sample data
is labelled as such and never presented as real archive data.

## compose service snippet (infra owns the actual compose + Dockerfile)

```yaml
backend:
  build: { context: ., dockerfile: backend/Dockerfile }
  environment:
    DATABASE_URL: postgresql+asyncpg://marsgis:marsgis@db:5432/marsgis
    JOB_BACKEND: arq
    REDIS_URL: redis://redis:6379/0
    ENGINE_MODE: container
  ports: ["127.0.0.1:8000:8000"]
  depends_on: [db, redis]
```
