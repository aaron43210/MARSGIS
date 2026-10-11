# MarsGIS — Project Memory

Living decisions log + current state + how to resume. Companion to [`plan.md`](plan.md), [`architecture.md`](architecture.md), [`connections.md`](connections.md). The full reconciled spec is at [`docs/architecture/SPEC.json`](docs/architecture/SPEC.json); the multi-agent design proposals at [`docs/architecture/DESIGNS.json`](docs/architecture/DESIGNS.json); per-unit build briefs under [`docs/architecture/build/`](docs/architecture/build/).

## What this is
Map-first planetary Web GIS for Mars (**the Cesium map/dashboard is the primary product**) + a reproducible CRISM hyperspectral SAM mineral-mapping engine shipped as a public Docker image. MSc capstone. Region focus: **Nili Fossae**; first experiment: SAM vs a MICA **carbonate** reference on scene `frt00003e12`.

## Non-negotiables
- Name is **MarsGIS** (never "MarsGeoAI").
- Git author/committer: **AARON R <aronr43210@gmail.com>** only — no other attribution.
- Fetch data via APIs/services; **no bulk archives committed**; only tiny synthetic/sample fixtures. Pipeline + tests run fully offline.
- **Scientific honesty is structural:** outputs are *candidate spectral matches*, never confirmed deposits; the caveat is a required field; the continuous angle raster is always retained; synthetic data is never presented as real.
- Must **actually run** out-of-the-box (SQLite + in-process worker + in-process engine), with a config-only production path.

## Key decisions (reconciled by the design panel)
- **Frontend:** React 19 + TS 5.9.3 + Vite 7.3.7 + plugin-react 5.2 + CesiumJS 1.146 (one persistent globe, imperative `LayerManager` reconciled one-way from a Zustand store) + uPlot + zod. Pinned off the bleeding edge on purpose.
- **Backend:** Python 3.12 + FastAPI + async SQLModel/SQLAlchemy 2. Chosen over Go/C++ because the geospatial/hyperspectral ecosystem is Python (GDAL/rasterio/spectral/scikit-learn).
- **DB:** SQLite default (GeoJSON text + bbox columns), PostGIS prod via `DATABASE_URL`.
- **Jobs:** in-process asyncio worker default, arq+Redis via `JOB_BACKEND=arq`. Polling only (no SSE/websockets in v1).
- **Result display:** backend rio-tiler on-the-fly tiles over a custom Mars **geographic** TMS (z0 2×1); `map_layer` is the ready display object; `/preview.png` fallback.
- **Engine seam:** `EngineAdapter` with `ENGINE_MODE=inprocess|subprocess|container`. Engine owns the Python API (`run_sam`), the CLI, and `ghcr.io/<owner>/marsgis-engine`.
- **Contract:** `contracts/enums.json` → Pydantic schemas (authoritative) → `contracts/openapi.yaml` (generated) → hand-mirrored TS types; CI asserts no drift. `contract_version` 1.0.0.
- **Coordinates:** Mars IAU 2000, east-positive lon [-180,180], planetocentric lat [-90,90], CRS `IAU_2000:49900`, radii 3396190/3396190/3376200. (Prod PostGIS geometry SRID to reconcile with 104905 — bbox filtering is dialect-agnostic so this is prod-only.)
- **Containers:** `python:3.12-slim` + `node:24`, rasterio PyPI wheels (no system GDAL), non-root uid 10001. Docker/CI authoritative (host is python 3.14 / node 26, best-effort).

## Verified this session
- Trek tiles return 200: Viking color + MOLA ClrShade (jpg). Template in [`connections.md`](connections.md) §5.
- Host tools: node 26, npm 11, python 3.14, Docker 29, GDAL 3.13, Postgres 17. Missing: go, cargo, pnpm, yarn.
- PyPI serves rasterio/spectral/scipy/scikit-learn for 3.12; `contracts/openapi.yaml` parses (12 paths); `engine/sample_data/sample_crism_nili.img` is a valid ENVI cube (gdalinfo).

## Build status
- **Complete and verified green (2026-10-11).** Full codebase built across `engine/ backend/ frontend/ contracts/ docker/ .github/ docs/` + root docs. Verified locally (Docker daemon was down, so Python verified in a 3.11 venv + Node on host; Docker/CI with 3.12 is the release path):
  - Engine: 63 pytest pass, ruff + format clean; real SAM run on the sample cube → valid COG (gdalinfo-confirmed).
  - Backend: 29 pytest pass, ruff + format clean; live ASGI end-to-end — `POST /api/analysis-jobs` → poll → `succeeded` → **localized** result (6.3% of scene, not 100%) → PNG tiles → COG download → provenance; `/openapi.json` == `contracts/openapi.yaml`.
  - Frontend: `typecheck` + `lint` + `test` + `build` all pass.
  - `docker compose config` valid.
- Integration fixes applied and regression-tested: greenlet via `sqlalchemy[asyncio]`; Mars geographic tiler rewritten (WorldCRS84Quad clone + `PROJ_IGNORE_CELESTIAL_BODY`); rio-tiler rescale shape; SAM `continuum_removed` default → **false**; sample cube rebuilt from real MICA with a proper Mars equirectangular WKT.
- Adversarial review (16 agents) found + confirmed 8 correctness/robustness/security bugs — ALL fixed: arq timeout leaves job stuck; orphaned `running` jobs on restart; non-atomic seeding race; X-Forwarded-For quota bypass; chunked-body size-limit bypass; health endpoint error leak; ENVI band/wavelength mismatch; non-finite reference poisoning SAM. See [[reference-marsgis-verification]].
- **Remaining (optional, documented):** push to GitHub + GHCR publish (needs the user's account); exercise the Postgres/Redis/Docker-image paths on a host with a running Docker daemon.

## How to resume
1. Read `plan.md` / `architecture.md` / `connections.md` and `docs/architecture/SPEC.json`.
2. Run the verification plan in `plan.md` → "Verification plan"; exact commands in `connections.md` §7.
3. Build/iterate with the briefs in `docs/architecture/build/` (frozen contract must not change without a `contract_version` bump).
