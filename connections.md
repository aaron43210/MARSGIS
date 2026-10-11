# MarsGIS — Connections

How the pieces wire together: directories, the contract, the service seams, external data, ports, env vars, and the commands that run it all.

## 1. Repository map (who owns what)

```
MARS/
├── contracts/            FROZEN shared contract (source of truth)
│   ├── enums.json          canonical vocab + defaults + Mars CRS + caveat
│   ├── openapi.yaml        canonical REST API (generated from backend schemas)
│   └── gen_openapi.py      regenerates openapi.yaml from app.schemas
├── engine/               marsgis_engine — hyperspectral SAM engine (standalone + importable)
│   ├── src/marsgis_engine/  io/ · science/ · data/mica/ · cli.py · pipeline.py
│   ├── sample_data/         tiny synthetic ENVI cube + reference (offline/CI)
│   ├── schemas/             provenance.schema.json
│   └── tests/               offline unit + e2e tests
├── backend/              FastAPI API + jobs + tiler
│   └── app/  main.py · config.py · db.py · models.py · routers/ · schemas/ (FROZEN) · seed/ (FROZEN) · engine_adapter.py · worker.py · tiler.py
├── frontend/             React + Vite + CesiumJS SPA (the primary product)
│   └── src/  main.tsx · GlobeView · LayerManager · store/ (zustand slices) · panels/ · api/ · types/ (FROZEN)
├── docker/               compose helpers + notes          (infra-owned)
├── .github/workflows/    ci.yml · release.yml             (CI-owned)
├── docs/                 DEVELOPMENT · RELEASING · DATA_LICENSES · ARCHITECTURE
├── docker-compose.yml · Makefile · .env.example           (infra-owned)
└── plan.md · architecture.md · connections.md · MEMORY.md  (top-level docs)
```

Cross-cutting files that physically nest inside service dirs but are **infra-owned**: every `Dockerfile`, `.dockerignore`, `backend/entrypoint.sh`, `frontend/nginx/`. Each service owns its own `pyproject.toml` / `requirements.txt` / `package.json`.

## 2. The contract chain

```
contracts/enums.json  ──verbatim mirror──▶  backend/app/schemas/enums.py  (Pydantic)
         └────────────verbatim mirror──────▶  frontend/src/types/enums.ts   (TypeScript)

backend/app/schemas/*.py  ──gen_openapi.py──▶  contracts/openapi.yaml  ══CI asserts══  backend /openapi.json
                                                       │
                                   hand-mirrored (tsc --strict clean)
                                                       ▼
                                          frontend/src/types/*.ts  ──▶  frontend/src/api client
```

Change a shape → edit the Pydantic schema → `python contracts/gen_openapi.py` → update the TS mirror → bump `contract_version`. CI fails if the three drift.

## 3. Service seams

### Frontend → Backend
- REST over `/api/*` (dev: Vite proxies `/api` → `http://127.0.0.1:8000`). Typed client in `frontend/src/api` built on the frozen `frontend/src/types`, with `AbortController`, error normalization, and zod validation of render-critical payloads.
- Result rasters: the frontend treats `AnalysisResult.map_layer` (type `result_tiles`) as a ready Cesium `UrlTemplateImageryProvider` pointing at `GET /api/results/{id}/tiles/{z}/{x}/{y}.png` (+ legend, bounds, value range). No raster math client-side.
- Basemaps: fetched **directly** from NASA Trek WMTS (not proxied) — see §5.

### Backend → Engine (`EngineAdapter`, the single seam)
```python
from marsgis_engine import run_sam, RunParams, SamResult, load_cube, load_reference
result: SamResult = run_sam(cube_path, reference_or_mineral, RunParams(
    threshold_rad=0.1, window_nm=(1000.0, 2600.0), continuum_removal=False,
    resample_method="linear", out_dir=..., out_prefix=..., timestamp=...))
# SamResult -> angle_path, candidate_path, provenance_path, report_path, stats
```
- `ENGINE_MODE=inprocess` (default): import + call `run_sam` on an `anyio` worker thread.
- `ENGINE_MODE=subprocess|container`: shell out to the CLI with resource limits:
  `marsgis-engine run --cube <path> (--mineral <alias>|--reference <path>) --method SAM --threshold <f> --out <dir> [--continuum-removal] [--resample linear|gaussian] [--timestamp <iso|placeholder>]`
- Output artifacts (stable contract): `<prefix>_SAM_angle.tif` (COG float32 radians, NaN nodata), `<prefix>_SAM_candidate.tif` (COG uint8 {0,1,255}), `<prefix>_provenance.json` (validates `engine/schemas/provenance.schema.json`), `<prefix>_report.txt`.

### Backend → Database
- `DATABASE_URL` unset → SQLite via `aiosqlite` (`metadata.create_all`); footprints = GeoJSON text + `minx/miny/maxx/maxy` bbox columns.
- `DATABASE_URL=postgresql+asyncpg://…` → PostgreSQL + PostGIS (Alembic `upgrade head`, geometry + GiST, `ST_Intersects`).

### Backend job flow
`POST /api/analysis-jobs` → row `queued` → asyncio queue → worker (`running`) → `EngineAdapter` → persist `analysis_result` + `map_layer` → `succeeded`. Client polls `GET /api/analysis-jobs/{id}`. `JOB_BACKEND=arq` swaps the in-process worker for arq+Redis with identical status writes.

## 4. Ports

| Service | Dev | Compose (127.0.0.1) |
|---|---|---|
| Frontend (Vite dev / nginx) | 5173 | 8080 |
| Backend (uvicorn) | 8000 | 8000 |
| PostGIS | — | 5432 |
| Redis (profile `worker`) | — | 6379 |

## 5. External data endpoints (fetched via API/service — nothing bulk committed)

| Source | Verified | Endpoint |
|---|---|---|
| Trek basemaps (WMTS) | ✅ | `https://trek.nasa.gov/tiles/Mars/EQ/{product}/1.0.0//default/default028mm/{z}/{y}/{x}.{ext}` — Viking (jpg), MOLA ClrShade (jpg) `zyx`; MOLA-DEM `mola128_mola64_merge_90Nto90S_SimpleC_clon0` (png), THEMIS `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` (png) |
| CRISM MTRDR discovery | ✅ | PDS ODE REST — `https://oderest.rsl.wustl.edu/live2/?query=product&target=mars&ihid=MRO&iid=CRISM&pt=MTRDR&results=m&output=JSON` |
| CRISM MTRDR archive | ✅ | `https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/` (ENVI `.img/.hdr`) |
| CRISM MICA references | ✅ | `https://pds-geosciences.wustl.edu/mro/mro-m-crism-4-typespec-v1/mrocr_8001/data/` (`.tab`) |
| USGS SIM 3292 geology | ✅ | pygeoapi — `https://astrogeology.usgs.gov/pygeoapi/collections/mars/sim3292_global_geologic_map/units/items?bbox=…&f=json` |
| Bundled sample (offline/CI) | ✅ | `engine/sample_data/` synthetic cube + reference — labelled synthetic, never presented as real |

## 6. Key environment variables (`.env.example`)

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | *(unset → SQLite)* | PostGIS DSN for prod |
| `ENGINE_MODE` | `inprocess` | `inprocess` \| `subprocess` \| `container` |
| `ENGINE_IMAGE` | `ghcr.io/<owner>/marsgis-engine:<tag>` | used when `ENGINE_MODE=container` |
| `JOB_BACKEND` | `inprocess` | `inprocess` \| `arq` |
| `JOB_CONCURRENCY` / `JOB_TIMEOUT_S` | small caps | worker bounds |
| `STORAGE_DIR` | `./storage` | result rasters (shared backend↔worker volume) |
| `GHCR_OWNER` | `${{ github.repository_owner }}` | image namespace |
| `CORS_ORIGINS` | `http://127.0.0.1:8080,http://localhost:5173` | allowed origins |
| `REQUIRE_API_KEY` | `false` (dev) | **must be `true` for public hosting** |

## 7. Commands

```bash
# One-command full stack (Docker is authoritative)
cp .env.example .env && make up            # db(postgis) + backend + frontend → http://127.0.0.1:8080

# Local dev without Docker
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ./engine[dev] -e ./backend[dev]
uvicorn app.main:app --app-dir backend --port 8000      # SQLite + in-process worker + engine
cd frontend && npm ci && npm run dev                    # http://127.0.0.1:5173

# Engine, standalone & offline
marsgis-engine run --cube engine/sample_data/sample_crism_nili.img \
  --mineral carbonate --method SAM --threshold 0.1 --out /tmp/sam_out --timestamp placeholder

# Quality gates
make test            # engine + backend pytest, frontend vitest
make lint typecheck  # ruff / mypy / eslint / tsc
docker compose config -q   # compose validity

# Production path — config only, no code change
DATABASE_URL=postgresql+asyncpg://… JOB_BACKEND=arq ENGINE_MODE=container \
  docker compose --profile worker up
```

See [`architecture.md`](architecture.md) for the system design and [`plan.md`](plan.md) for the delivery plan and acceptance checklist.

