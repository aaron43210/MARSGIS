# MarsGIS — Architecture

The reconciled, binding contract across the four build concerns. Where two concerns proposed
different designs, the resolution recorded here is canonical. The authoritative wire contract is
`contracts/openapi.yaml` (generated from `backend/app/schemas/`, Pydantic v2); `contracts/enums.json`
pins every closed vocabulary and the SAM/tile defaults; `frontend/src/types/*.ts` is a hand-written
TypeScript mirror. `contract_version` is **1.0.0**.

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

- **Frontend** is map-first: one persistent CesiumJS `Viewer` on the Mars ellipsoid, four workspace
  modes as dock panels, a one-way `LayerManager` reconciling the imagery stack from the Zustand
  store (the store is the single source of truth; the UI never touches Cesium directly). The frontend
  does no raster math.
- **Backend** serves the catalogue, runs analysis jobs, and tiles results on the fly. It imports
  `app.schemas` (never redefining shapes) and calls the engine through one adapter seam.
- **Engine** is a standalone package + CLI + image; it runs SAM and emits COGs + provenance, and
  makes no geologic claim.

## Coordinate convention (binding, everywhere)

Mars **IAU 2000** degrees, on **CRS 104905**:

- Longitude east-positive, `[-180, 180]` (a centralized `normalizeLon` helper enforces this).
- Latitude planetocentric, `[-90, 90]`.
- GeoJSON carries plain degrees; the datum is documented in `enums.json.crs`.
- Imagery and overlays use a `GeographicTilingScheme` with **2 columns × 1 row at z0**, matching the
  NASA Trek EQ equirectangular grid, so basemaps, result tiles, footprints, the gazetteer, and pixel
  queries all align with no reprojection. This is Mars, not Earth WGS84.

## Result → map flow (canonical)

Resolution of the frontend "client-side XYZ vs SingleTile" proposal against the backend "on-the-fly
rio-tiler endpoint" proposal: **the backend on-the-fly tiler is canonical; the frontend does no raster
math.**

1. The engine writes an angle COG (float32 radians, NaN nodata) and a candidate-mask COG (uint8) in
   the input Mars CRS.
2. `GET /api/results/{id}` returns an `AnalysisResult` whose `map_layer` is a ready
   `MapLayer(type=result_tiles, tile_order=zxy)` — the exact object the frontend layer manager
   appends, identical to how it appends a catalogue basemap.
3. The frontend builds a Cesium `UrlTemplateImageryProvider` on a `GeographicTilingScheme({x:2,y:1})`
   from that `map_layer`, pointed at
   `GET /api/results/{id}/tiles/{z}/{x}/{y}.png?colormap=&rescale=`.
4. The backend tiles the COG on the fly with **rio-tiler over a custom morecantile Mars GEOGRAPHIC
   TileMatrixSet** (z0 = 2×1), 256 px tiles, **color baked server-side** (default `magma`, rescaled
   `0..threshold_rad`, transparent nodata and alpha 0 above threshold). A tile with no data returns
   `204`. Caching headers are immutable; `z/x/y` are bounded.
5. For a tiny bbox, `map_layer.source` selects the `GET /api/results/{id}/preview.png`
   `SingleTileImageryProvider` fallback (max size bounded).

rio-tiler is **embedded** in the backend tiles route for v1 (no extra service); a standalone
`titiler` sits behind an opt-in `compose --profile tiles` for scale-out later.

## Analysis job lifecycle

Resolution of "in-process asyncio worker vs arq+Redis vs async-and-poll": **default in-process
asyncio worker; production arq+Redis; always poll.** v1 has **no SSE/websockets**.

```
POST /api/analysis-jobs                → 202 AnalysisJob{status: queued} + Location header
      │  (validate: observation exists & analysis_suitable, reference exists,
      │   algorithm implemented [SID/BAND_RATIO → 422], quota [→ 429],
      │   optional Idempotency-Key dedupe)
      ▼
   queued ──► running ──► succeeded  (result_id set)
                    └───► failed     (error{code,message,retriable} set)
```

- Terminal states (`succeeded`, `failed`) have **no** outgoing transitions; the transition table is
  pinned in `enums.json.job_status_transitions`. Cancellation is out of scope for v1.
- The client polls `GET /api/analysis-jobs/{id}` for `status` + `progress (0..1)` + `message`.
- **Default:** an in-process `asyncio.Queue` drained by a lifespan task, with the CPU-bound engine
  call dispatched via `anyio.to_thread`, a `JOB_CONCURRENCY` cap, and a per-job `wait_for` timeout.
- **Production:** `JOB_BACKEND=arq` + `REDIS_URL` + a `marsgis-worker` process
  (`compose --profile worker`). Both backends write **identical** status/progress to the
  `analysis_job` row, so the API is backend-agnostic.
- `SamParams` defaults (from `enums.json`): `threshold_rad=0.10`, `continuum_removed=true`,
  `wavelength_subset_nm=[1000,2600]`.

## EngineAdapter modes

Resolution of "hard-wired import vs subprocess/container": **a single `EngineAdapter` seam**
selected by `ENGINE_MODE`. The engine owns the Python API, the `marsgis-engine` CLI, and the image.

| `ENGINE_MODE` | How the backend calls the engine | Use |
|---|---|---|
| `inprocess` (default) | `import marsgis_engine; run_sam(...)` in a worker thread | Fastest; dev + CI. The backend installs the engine editable. |
| `subprocess` | Spawns the `marsgis-engine run ...` CLI | Process isolation on one host. |
| `container` | `docker run ghcr.io/${GHCR_OWNER}/marsgis-engine ...` with `RLIMIT_CPU` / `RLIMIT_AS` + wall-clock timeout | Hard boundary for untrusted public workloads. |

All three produce the same artifacts (angle COG + candidate COG + `provenance.json` + `report.txt`)
and the same provenance shape (`engine/schemas/provenance.schema.json`), so switching modes never
changes the result contract. `ENGINE_CUBE_SOURCE` picks the input: `sample` (bundled synthetic cube,
flagged `synthetic_input`) or `archive` (the real MTRDR `_if` cube streamed from PDS on demand).

## Database dialect strategy

Resolution of "SQLModel + bbox columns vs PostGIS-required vs SQLite-fallback": **one SQLModel /
SQLAlchemy 2.x async engine; dialect chosen by `DATABASE_URL`; dialect-agnostic bbox filtering.**

| | Default (dev) | Production |
|---|---|---|
| URL | `sqlite+aiosqlite:///./storage/marsgis.db` | `postgresql+asyncpg://…` |
| Footprint | GeoJSON **text** + denormalized `minx/miny/maxx/maxy` | `geometry(POLYGON,104905)` + GiST + the same bbox columns |
| Viewport filter | numeric range on the bbox columns | `ST_Intersects` |
| Migrations | `SQLModel.metadata.create_all` on startup | `alembic upgrade head` (enables PostGIS, registers IAU 104905 in `spatial_ref_sys`, builds GiST) |

The denormalized bbox columns give dialect-agnostic viewport filtering with **no SpatiaLite
dependency**, so the dev stack runs with zero geospatial infrastructure while production keeps true
PostGIS geometry.

## Shared contract integrity

`backend/app/schemas/` (Pydantic v2, `extra=forbid`) is authoritative. It generates
`contracts/openapi.yaml` via `contracts/gen_openapi.py`; CI asserts the backend's live
`/openapi.json` equals that committed file. `frontend/src/types/*.ts` is a hand-written, `tsc
--strict`-clean mirror (not codegen) kept in lockstep by `contract_version`; the frontend keeps zod
validators only for render-critical payloads. The contract files, `enums.json`, the seed JSON, and
`engine/sample_data/*` are **frozen** — build against them, never redefine them.

## Scientific-honesty invariant

`CANDIDATE_MATCH_CAVEAT` is a single constant in `contracts/enums.json`, enforced as a **required**
field on `AnalysisResult`, `SummaryStats`, `Legend`, and `Provenance`, and surfaced in the status
bar, inspector, results panel, and the spectral-angle badge. The continuous angle raster is always
retained alongside the mask. A result without the caveat is structurally unrepresentable, and
synthetic inputs are flagged `synthetic_input` so they can never be mistaken for a real detection.

## API surface (authoritative = `contracts/openapi.yaml`)

`GET /api/health` · `GET /api/layers` · `GET /api/observations[/{id}]` · `GET /api/minerals[/{id}]` ·
`POST|GET /api/analysis-jobs` · `GET /api/analysis-jobs/{id}` · `GET /api/results/{id}` ·
`GET /api/results/{id}/tiles/{z}/{x}/{y}.png` · `GET /api/results/{id}/download` ·
`GET /api/provenance/{id}` · `GET /openapi.json`. (`GET /api/results/{id}/preview.png` is the
small-bbox SingleTile fallback, not part of the OpenAPI contract.)
