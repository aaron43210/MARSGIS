# MarsGIS

[![CI](https://github.com/marsgis/marsgis/actions/workflows/ci.yml/badge.svg)](https://github.com/marsgis/marsgis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Images: GHCR](https://img.shields.io/badge/images-GHCR-181717?logo=github)](https://github.com/orgs/marsgis/packages)
[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey.svg)](https://doi.org/10.5281/zenodo.0000000)

**MarsGIS** is an interactive Mars map/dashboard — a CesiumJS 3D Mars globe is the
**primary product** — with an integrated hyperspectral analysis capability that
runs the **Spectral Angle Mapper (SAM)** on CRISM MTRDR cubes.

> **Scientific integrity.** SAM outputs are **candidate spectral matches, never
> confirmed mineral deposits.** The continuous spectral-angle raster is always
> retained alongside any candidate mask, and the candidate caveat is a required
> field on every result. The bundled offline sample is **synthetic** and is never
> presented as a real archive detection.

## Quick start (containerized — Docker + the compose plugin only)

```bash
cp .env.example .env     # edit secrets (POSTGRES_PASSWORD, SECRET_KEY) for anything non-local
make up                  # builds + starts db (PostGIS) + backend + frontend
```

Then open:

- **Frontend (the app):** http://127.0.0.1:8080
- **Backend API:** http://127.0.0.1:8000  (health: `/api/health`, docs: `/docs`)

Stop with `make down`. See `make help` for all tasks.

### Optional services (compose profiles)

```bash
docker compose --profile worker up -d    # redis + arq worker (JOB_BACKEND=arq)
docker compose --profile tiles  up -d    # titiler sidecar (scale-out tiling)
make engine-run-sample                   # run SAM on the bundled SYNTHETIC sample
```

The default job path is an **in-process** async worker (no extra infra); the
`worker` profile switches to arq + Redis.

## Architecture at a glance

| Service    | Image                                | Role                                               |
| ---------- | ------------------------------------ | -------------------------------------------------- |
| `frontend` | `ghcr.io/<owner>/marsgis-frontend`   | React 19 + Vite 7 + CesiumJS SPA, served by nginx  |
| `backend`  | `ghcr.io/<owner>/marsgis-backend`    | FastAPI: catalogue, SAM jobs, on-the-fly tiling    |
| `engine`   | `ghcr.io/<owner>/marsgis-engine`     | Standalone `marsgis-engine` SAM CLI / Python API   |
| `db`       | `postgis/postgis:17-3.5`             | PostGIS (production path; SQLite is the dev default)|

- **Database:** zero-setup **SQLite** by default; **PostgreSQL + PostGIS** in
  production, selected by `DATABASE_URL`.
- **Images:** multi-stage, non-root (uid 10001); Python pinned to **3.12**, Node
  pinned to **24** (see `docs/DEVELOPMENT.md` for the pin rationale).

## Non-Docker development

Requires **Node 24** and **Python 3.12** (the host may run newer — install a 3.12
interpreter via `uv`/`pyenv`). See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Security note (please read before exposing anything)

The dev `docker compose` stack is **unauthenticated** and binds **only
`127.0.0.1`**. Do **not** deploy it as-is on a shared network. A real deployment
needs authentication, TLS termination, and a reverse proxy / gateway in front of
the backend. Abuse limits on the open analysis endpoint are configurable in `.env`.

## Data & attribution

NASA source data is **fetched via services at runtime and is not redistributed**
in this repository. Courtesy of NASA/JPL-Caltech/JHUAPL (CRISM/MRO), NASA/GSFC
(MOLA), USGS/NASA (Viking MDIM21), and NASA Mars Trek (basemaps). Full details
and the scientific-integrity disclaimer are in
[`docs/DATA_LICENSES.md`](docs/DATA_LICENSES.md).

## Documentation

- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — dev setup, Python/Node pins, engine CLI, DB switch.
- [`docs/RELEASING.md`](docs/RELEASING.md) — SemVer, tag-driven release, Zenodo.
- [`docs/DATA_LICENSES.md`](docs/DATA_LICENSES.md) — data provenance, licenses, disclaimer.
- [`docker/README.md`](docker/README.md) — build-context convention, arm64 note, lockfiles.

## License

Source code is [MIT](LICENSE). Bundled synthetic sample data is CC0; docs are
CC-BY-4.0. See `docs/DATA_LICENSES.md`.
