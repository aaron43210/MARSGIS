# Architecture

MarsGIS has three parts: a CesiumJS frontend, a FastAPI backend, and a standalone
hyperspectral engine. The wire contract is `contracts/openapi.yaml`, generated from the
Pydantic schemas in `backend/app/schemas/`; `contracts/enums.json` pins every closed
vocabulary and the SAM/tile defaults; `frontend/src/types/*.ts` mirrors them by hand.
The contract version is **1.0.0**.

## System shape

```
┌──────────────┐   REST /api/*    ┌──────────────────────────┐   EngineAdapter   ┌───────────────┐
│  frontend    │ ───────────────► │  backend (FastAPI)       │ ────────────────► │ marsgis_engine│
│  React 19 +  │ ◄─────────────── │  catalogue · jobs · tiler│ ◄──────────────── │   SAM / COG   │
│  CesiumJS    │   JSON / PNG      │  SQLModel async          │   COG + prov.json │               │
└──────────────┘   tiles          └──────────────────────────┘                   └───────────────┘
        │                                   │                                            │
   one persistent                      SQLite (dev) /                            ENVI cube in →
   Mars globe                          PostGIS (prod)                            COG + provenance out
```

- **Frontend** is map-first: one persistent CesiumJS `Viewer` on the Mars ellipsoid, workspace
  modes as dock panels, and a `LayerManager` that reconciles the imagery stack one way from the
  Zustand store. The UI never touches Cesium directly, and the frontend does no raster math.
- **Backend** serves the catalogue, runs analysis jobs and tiles results on the fly. It calls the
  engine through a single adapter.
- **Engine** is a standalone package, CLI and container image. It runs SAM and writes COGs plus
  provenance; it makes no geologic claim.

## Repository layout

```
contracts/        enums.json · openapi.yaml (generated) · gen_openapi.py
engine/           marsgis_engine: io/ · science/ · data/mica/ · cli.py; sample_data/ (synthetic); tests/
backend/app/      main.py · api/routes/ · schemas/ · services/ (catalog, jobs, engine_adapter, raster, ode…) · db/ · alembic/
frontend/src/     cesium/ (MarsViewer, LayerManager, picking…) · components/ · store/ · api/ · types/
packages/         mars-globe: the reusable Cesium Mars globe, published to npm
docker/           all-in-one image config, PostGIS init
scripts/          validation and benchmark scripts behind docs/evidence/
docs/             this file · DEVELOPMENT · RELEASING · DATA_LICENSES · evidence/
```

## Technology choices

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React 19, TypeScript 5.9, Vite 7.3 | Mature, stable line rather than the newest majors |
| Globe | CesiumJS 1.146, one persistent `Viewer` | 3D planetary globe; an imperative viewer with one-way reconciliation avoids WebGL remounts |
| State | Zustand 5 (immer + persist) | `store.subscribe` drives Cesium from outside React without re-renders |
| Backend | Python 3.12, FastAPI, SQLModel / SQLAlchemy 2 (async) | GDAL, rasterio and the spectral tooling live in Python |
| Database | SQLite by default, PostGIS in production | Runs with no infrastructure; same queries on both (see below) |
| Jobs | In-process asyncio worker by default, arq + Redis in production | No broker needed to try it; both write identical job state |
| Result tiles | rio-tiler over a Mars geographic tile matrix set | Results become ordinary map layers; colour is applied server-side |
| Engine | `marsgis_engine`, numpy-vectorised SAM, COG output | The same code runs in-process, from the CLI and in Docker |
| Containers | `python:3.12-slim`, `node:24`, rasterio wheels | Small, reproducible, non-root (uid 10001) |

## Coordinate convention

Mars **IAU 2000** degrees, CRS **104905**:

- Longitude east-positive, `[-180, 180]` (enforced by the shared `normalizeLon180` helper).
- Latitude planetocentric, `[-90, 90]`.
- GeoJSON carries plain degrees; the datum is documented in `enums.json.crs`.
- Imagery and overlays use a `GeographicTilingScheme` with **2 columns × 1 row at z0**, matching
  the NASA Trek equirectangular grid, so basemaps, result tiles, footprints, the gazetteer and
  pixel queries align without reprojection.

## From result to map

The backend tiles results on the fly; the frontend never processes rasters.

1. The engine writes an angle COG (float32 radians, NaN nodata) and a candidate-mask COG (uint8)
   in the input Mars CRS.
2. `GET /api/results/{id}` returns an `AnalysisResult` whose `map_layer` is a ready
   `MapLayer(type=result_tiles, tile_order=zxy)`, the same shape as a catalogue basemap.
3. The frontend builds a Cesium `UrlTemplateImageryProvider` on a `GeographicTilingScheme({x:2,y:1})`
   pointed at `GET /api/results/{id}/tiles/{z}/{x}/{y}.png?colormap=&rescale=`.
4. The backend renders tiles with rio-tiler over a custom morecantile Mars geographic
   TileMatrixSet (z0 = 2×1, 256 px). Colour is applied server-side (default `magma`, rescaled
   `0..threshold_rad`, transparent for nodata and above the threshold). Empty tiles return `204`;
   responses are cached as immutable and `z/x/y` are bounded.
5. For a very small bbox, `map_layer.source` selects the `GET /api/results/{id}/preview.png`
   single-image fallback.

The tiler is embedded in the backend. A standalone `titiler` service is available behind
`docker compose --profile tiles` for scaling out.

## Analysis job lifecycle

Jobs run on an in-process asyncio worker by default, or on arq + Redis in production. Clients
poll for status; there are no websockets.

```
POST /api/analysis-jobs                → 202 AnalysisJob{status: queued} + Location header
      │  (validate: observation exists & analysis_suitable, reference exists,
      │   algorithm implemented [SID/BAND_RATIO → 422], quota [→ 429],
      │   optional Idempotency-Key dedupe)
      ▼
   queued ──► running ──► succeeded  (result_id set)
                    └───► failed     (error{code,message,retriable} set)
```

- `succeeded` and `failed` are terminal; the transition table is in
  `enums.json.job_status_transitions`. Cancellation is not supported.
- A worker claims a job atomically, so a job enqueued twice runs once.
- Clients poll `GET /api/analysis-jobs/{id}` for `status`, `progress` (0–1) and `message`.
- **Default:** an `asyncio.Queue` drained by a lifespan task; the CPU-bound engine call runs in a
  thread via `anyio.to_thread`, bounded by `JOB_CONCURRENCY` and a per-job timeout.
- **Production:** `JOB_BACKEND=arq` with `REDIS_URL` and a worker process
  (`docker compose --profile worker`). Both backends write the same state to the
  `analysis_job` row, so the API doesn't change.
- `SamParams` defaults (from `enums.json`): `threshold_rad=0.10`, `continuum_removed=true`,
  `wavelength_subset_nm=[1000,2600]`.

## Engine modes

The backend reaches the engine only through `EngineAdapter`, selected by `ENGINE_MODE`:

| `ENGINE_MODE` | How the engine runs | Use |
|---|---|---|
| `inprocess` (default) | `marsgis_engine.run_sam(...)` in a worker thread | Development and CI |
| `subprocess` | `python -m marsgis_engine run ...` with CPU/memory limits | Process isolation on one host |
| `container` | `docker run --network none ghcr.io/aaron43210/marsgis-engine ...` with CPU/memory limits and a timeout | Untrusted public workloads |

All three produce the same artefacts (angle COG, candidate COG, `provenance.json`, `report.txt`)
and the same provenance shape (`engine/schemas/provenance.schema.json`). `ENGINE_CUBE_SOURCE`
picks the input: `sample` (the bundled synthetic cube, flagged `synthetic_input`) or `archive`
(the real MTRDR cube, streamed from PDS on demand).

## Database

One async SQLModel / SQLAlchemy 2 engine; the dialect comes from `DATABASE_URL`.

| | Default (dev) | Production |
|---|---|---|
| URL | `sqlite+aiosqlite:///./storage/marsgis.db` | `postgresql+asyncpg://…` |
| Footprint | GeoJSON text + `minx/miny/maxx/maxy` columns | `geometry(POLYGON,104905)` + GiST + the same bbox columns |
| Viewport filter | numeric range on the bbox columns | `ST_Intersects` |
| Schema | `SQLModel.metadata.create_all` on startup | `alembic upgrade head` (enables PostGIS, registers IAU 104905, builds GiST) |

The bbox columns let viewport filtering work on both dialects without SpatiaLite, so development
needs no geospatial infrastructure.

## Contract integrity

`backend/app/schemas/` (Pydantic v2, `extra=forbid`) is authoritative.
`contracts/gen_openapi.py` generates `contracts/openapi.yaml` from it, and CI checks that the live
`/openapi.json` matches the committed file. `frontend/src/types/*.ts` is a hand-written,
`tsc --strict`-clean mirror kept in step by `contract_version`; zod validates only render-critical
payloads.

To change a shape: edit the Pydantic schema, run `python contracts/gen_openapi.py`, update the
TypeScript mirror and bump `contract_version`.

## Scientific honesty

`CANDIDATE_MATCH_CAVEAT` is a single constant in `contracts/enums.json`. It is a required field on
`AnalysisResult`, `SummaryStats`, `Legend` and `Provenance`, and it is shown in the status bar,
inspector, results panel and spectral-angle badge. The continuous angle raster is always kept
alongside the mask, and synthetic inputs are flagged `synthetic_input`, so a result can't be
presented as a confirmed deposit or a real detection.

## External data

Nothing is bulk-committed; data is fetched from public services at runtime.

| Source | Endpoint |
|---|---|
| NASA Mars Trek basemaps (WMTS) | `https://trek.nasa.gov/tiles/Mars/EQ/{product}/1.0.0//default/default028mm/{z}/{y}/{x}.{ext}` |
| CRISM MTRDR discovery | PDS ODE REST, `https://oderest.rsl.wustl.edu/live2/` |
| CRISM MTRDR cubes | `https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/` |
| CRISM MICA reference spectra | `https://pds-geosciences.wustl.edu/mro/mro-m-crism-4-typespec-v1/mrocr_8001/data/` |
| USGS SIM 3292 geologic map | `https://astrogeology.usgs.gov/pygeoapi/collections/mars/sim3292_global_geologic_map` |

`engine/sample_data/` holds a small synthetic cube for offline use and CI; it is always labelled
synthetic.

## API surface

The full contract is `contracts/openapi.yaml`.

`GET /api/health` · `GET /api/layers` · `GET /api/observations[/{id}]` · `GET /api/minerals[/{id}]` ·
`POST|GET /api/analysis-jobs` · `GET /api/analysis-jobs/{id}` · `GET /api/results/{id}` ·
`GET /api/results/{id}/tiles/{z}/{x}/{y}.png` · `GET /api/results/{id}/download` ·
`GET /api/provenance/{id}` · `GET /openapi.json`. `GET /api/results/{id}/preview.png` is the
small-bbox fallback and is not part of the OpenAPI contract.

## Ports

| Service | Local dev | Docker Compose (127.0.0.1) |
|---|---|---|
| Frontend | 5173 (Vite) | 8080 (nginx) |
| Backend | 8000 | 8000 |
| PostGIS | — | 5432 |
| Redis (`worker` profile) | — | 6379 |
| Adminer (dev overlay) | — | 8081 |
