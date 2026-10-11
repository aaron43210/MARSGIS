# MarsGIS — Architecture

> Map-first planetary Web GIS for Mars + a reproducible CRISM hyperspectral mineral-mapping engine.
> The **interactive Cesium map is the primary product**; the science engine is an integrated, independently reproducible capability.

Contract version: **1.0.0** · Canonical vocabulary: [`contracts/enums.json`](contracts/enums.json) · Canonical API: [`contracts/openapi.yaml`](contracts/openapi.yaml)

---

## 1. System overview

```
                         ┌──────────────────────────────────────────────┐
   NASA / USGS services  │                 Browser (SPA)                │
   ─────────────────────  │   React + TypeScript + Vite + CesiumJS       │
   • Mars Trek WMTS  ─────┼─▶ one persistent Mars globe (GlobeView)      │
     (basemaps, direct)  │   LayerManager ◀─ Zustand store (slices)      │
                         │   dock panels: Explorer│Catalogue│Analysis│Results│Inspector │
                         └───────────────▲───────────────┬──────────────┘
                                         │ REST (/api/*)  │ XYZ result tiles (.png)
                                         │                ▼
                         ┌──────────────────────────────────────────────┐
                         │              Backend — FastAPI               │
                         │  routers ─ CRUD ─ SQLModel (SQLite│PostGIS)   │
                         │  in-process asyncio job worker (│arq+Redis)   │
                         │  rio-tiler result tiler (Mars geographic TMS) │
                         │  EngineAdapter ──┐                            │
                         └──────────────────┼───────────────────────────┘
                   inprocess import │ or │ subprocess/container CLI
                                    ▼
                         ┌──────────────────────────────────────────────┐
                         │        marsgis_engine (Python package)        │
                         │  ENVI reader ─ MICA refs ─ SAM ─ COG writer   │
                         │  CLI `marsgis-engine run …`  +  run_sam() API  │
                         │  ships as ghcr.io/<owner>/marsgis-engine      │
                         └──────────────────────────────────────────────┘
   PDS ODE REST (CRISM MTRDR discovery) ─▶ backend data-acquisition (on demand, no bulk download)
   USGS pygeoapi (SIM 3292 geology)     ─▶ backend / frontend overlay
```

Three deployable artifacts, each independently useful:
1. **Hosted Web GIS** — the map + API (`docker compose up`).
2. **Public engine image** — `ghcr.io/<owner>/marsgis-engine:<semver>`, reproduces one documented analysis on a user's own data.
3. **Open-source repo** — code, contract, tests, docs.

## 2. Technology stack (with rationale)

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| Frontend | React 19 + TypeScript 5.9 + Vite 7.3 + `@vitejs/plugin-react` 5.2 | Pinned to the mature line, not Vite 8 / plugin-react 6 (Rolldown/oxc) / TS 7 — reliability over bleeding edge; typescript-eslint needs TS < 6.1 |
| Planetary map | CesiumJS 1.146, **one** persistent globe | 3D planetary globe is the core experience; a single imperative `Viewer` + one-way `LayerManager` reconciliation beats declarative wrappers for dynamic layers/picking and avoids WebGL remounts on screen changes |
| Map state | Zustand 5 (immer + persist) | `store.subscribe` drives Cesium from outside React (no re-render stutter); persists camera/basemap/panels |
| Backend | Python 3.12 + FastAPI 0.143 + SQLModel/SQLAlchemy 2 (async) | GDAL/rasterio/Spectral-Python/scikit-learn live in Python and are already installed; FastAPI is async and fast enough. (Go/C++ were on the table but would strand the entire scientific ecosystem.) |
| Database | **SQLite by default** (zero-setup dev), **PostgreSQL + PostGIS** for prod via `DATABASE_URL` | Runs out of the box with no infra; footprints stored as GeoJSON text + denormalized `minx/miny/maxx/maxy` bbox columns give dialect-agnostic viewport filtering, upgraded to real `ST_Intersects` on PostGIS |
| Jobs | **In-process asyncio worker by default**, arq + Redis for prod (`JOB_BACKEND`) | No broker needed to try the product; both write identical status to `analysis_job`; client polls `GET /api/analysis-jobs/{id}` (no SSE/websockets in v1) |
| Result tiling | rio-tiler on-the-fly over a **custom Mars _geographic_ TMS** (z0 = 2×1), color baked server-side | Frontend does zero raster math; the result is just another map layer with a tiles URL template + legend |
| Science engine | standalone `marsgis_engine` package, numpy-vectorized SAM, COG output | Importable in-process **and** a CLI/Docker image → the same code reproduces results off-platform |
| Engine seam | `EngineAdapter`: `ENGINE_MODE=inprocess` (dev) \| `subprocess`\|`container` (isolated public workloads) | One seam switches between fast dev imports and resource-limited isolation |
| Containers | Docker + `docker compose`; `python:3.12-slim` + `node:24`; rasterio PyPI wheels (no system GDAL) | Reproducible, small, non-root (uid 10001); Docker/CI are the authoritative runtime (host is python 3.14 / node 26, used best-effort) |

## 3. The shared contract (single source of truth)

`contracts/enums.json` pins every closed vocabulary + cross-cutting default (SAM threshold, tile grid, colormaps, the Mars CRS, the `candidate_match` caveat). It is mirrored **verbatim** by `backend/app/schemas/enums.py` (Pydantic) and `frontend/src/types/enums.ts` (TypeScript).

Flow of truth:

```
contracts/enums.json  ──mirrored──▶  backend/app/schemas (Pydantic v2, extra=forbid)   ← AUTHORITATIVE shapes
                                             │ gen_openapi.py
                                             ▼
                                   contracts/openapi.yaml   ──(CI asserts == live /openapi.json)
                                             │ hand-mirrored, tsc --strict clean
                                             ▼
                                   frontend/src/types/*.ts  ← consumed by the typed API client
```

A result is **structurally unable** to exist without its `candidate_match` caveat — the field is required on `AnalysisResult`, `SummaryStats`, `Legend`, and `Provenance`.

## 4. End-to-end data flow: observation → analysis → map

1. **Discover** — backend queries the PDS Orbital Data Explorer REST API for CRISM MTRDR products over Nili Fossae; footprints + metadata are seeded/ingested into `observations`. The map draws footprint polygons the user can click.
2. **Select** — user picks an observation + a target mineral (reference spectrum from `spectral_references`, e.g. carbonate) + algorithm (SAM) + threshold in the Analysis panel.
3. **Submit** — `POST /api/analysis-jobs` creates a row with status `queued` and returns its id. The job enters the asyncio worker queue.
4. **Acquire + run** — the worker stages the MTRDR cube to a local path (fetched on demand from PDS, never a bulk archive), then invokes the engine via `EngineAdapter`:
   - `inprocess`: `run_sam(cube_path, reference_or_mineral, RunParams(...)) -> SamResult`
   - `subprocess`/`container`: `marsgis-engine run --cube … --mineral … --method SAM --threshold … --out …`
   - Status transitions `queued → running → succeeded|failed` are written to `analysis_job`; the client polls `GET /api/analysis-jobs/{id}`.
5. **Persist** — on success the engine's outputs (`*_SAM_angle.tif` COG, `*_SAM_candidate.tif` COG, `*_provenance.json`, `*_report.txt`) are recorded as an `analysis_result` with a ready-to-display `map_layer` (type `result_tiles`, a tiles URL template + bounds + legend + value range).
6. **Display** — the frontend adds `result.map_layer` to the globe. Tiles are rendered on demand by `GET /api/results/{id}/tiles/{z}/{x}/{y}.png` (rio-tiler, magma colormap, transparent nodata). `/preview.png` is the small-bbox fallback.
7. **Inspect + export** — clicking a pixel fetches its spectral angle + spectrum (plotted against the reference with uPlot); the user downloads the GeoTIFF (`/download`) and reads provenance (`/provenance/{id}`). Everything is labelled a **candidate** match.

## 5. API surface (authoritative in `contracts/openapi.yaml`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness + dependency status |
| GET | `/api/layers` | map layers (basemaps, geology, overlays) with source/attribution/availability |
| GET | `/api/observations` | search (filters: instrument, product_type, region, bbox, suitable) |
| GET | `/api/observations/{id}` | one observation's full metadata |
| GET | `/api/minerals` · `/api/minerals/{id}` | available reference spectra |
| POST | `/api/analysis-jobs` | submit an analysis (optional `Idempotency-Key`) |
| GET | `/api/analysis-jobs/{id}` | job status (polled) |
| GET | `/api/results/{id}` | result metadata + `map_layer` + summary stats |
| GET | `/api/results/{id}/download` | output GeoTIFF |
| GET | `/api/results/{id}/tiles/{z}/{x}/{y}.png` | on-the-fly colored result tiles |
| GET | `/api/provenance/{id}` | full processing history |

## 6. Coordinate system

Mars IAU 2000, **planetocentric** latitude, **east-positive** longitude in `[-180, 180]`; CRS id `IAU_2000:49900`; ellipsoid radii `3396190 / 3396190 / 3376200 m`. GeoJSON/bbox carry plain Mars degrees — **not** Earth WGS84. Cesium is configured with a Mars `Ellipsoid.default` set *before* any `Viewer` is created; the Trek equirectangular tile grid (2×1 at level 0) maps directly to Cesium's `GeographicTilingScheme`. The engine never reprojects: outputs inherit the MTRDR grid; if GDAL cannot resolve the Mars datum from the ENVI header a Mars-2000 equirectangular WKT fallback is attached and recorded as `crs_is_fallback` in provenance.

## 7. Scientific-integrity invariants

- Outputs are **candidate spectral matches**, never confirmed deposits — enforced as a required caveat field and surfaced in the UI (status bar, inspector, results panel).
- The continuous spectral-angle raster is always retained alongside the binary candidate mask, so uncertainty stays inspectable and the threshold can be re-applied without recompute.
- MTRDR is analysis-ready (calibrated + map-projected): the engine performs **no** re-calibration and **no** reprojection.
- Known caveat recorded in docs + provenance: MICA type spectra are *ratioed* I/F while scene pixels are *un-ratioed* I/F; SAM's albedo-invariance + optional continuum removal + a diagnostic wavelength window partially mitigate this.
- Synthetic/sample data is always labelled as such and never presented as real archive data.

See [`plan.md`](plan.md) for the delivery plan and [`connections.md`](connections.md) for the wiring between modules, services, ports, and env vars. A deeper companion lives at [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).


