# MarsGIS — Project Development Plan (updated)

**An open-source, self-hostable Mars mapping and mineral-analysis platform.**

MarsGIS is a browser-based planetary GIS where you explore Mars in 3D, **discover real Mars observations from public archives**, run a documented hyperspectral mineral-matching workflow on CRISM data, and visualize, download, and **reproduce** the result. It ships as a Docker image so anyone can run their own instance.

Design principle: **keep the system simple and scientifically honest.** NASA's MMGIS, JMARS, and PlanetServer already provide planetary globes and some analysis; MarsGIS's contribution is *not* another globe but a **simple, reproducible workflow for discovering Mars data and running a mineral analysis directly from the map** — with provenance and a public, rerunnable Docker release.

## Core user experience
A researcher interested in carbonates near Nili Fossae opens MarsGIS, navigates there, **discovers a real CRISM observation from the live archive**, inspects its coverage/bands, picks a reference spectrum, runs Spectral Angle Mapper, sees a map of **candidate** matches (never "confirmed deposits"), inspects pixel spectra, and downloads the GeoTIFF + provenance to reproduce it.

## Who it serves
| Audience | What they get |
|---|---|
| **Researchers** | Discover real CRISM/Mars products anywhere on the planet; run a validated SAM workflow; inspect spectra, quality masks, and spectral-angle values; download GeoTIFF + JSON provenance; reproduce via the pinned Docker engine. Honest "candidate, not confirmed" framing throughout. |
| **Developers** | A small, documented, self-hostable stack (React + FastAPI + a standalone engine), a frozen API contract + OpenAPI, tests, and `docker compose up`. The engine is importable, a CLI, and a public image — extend or embed it. Plus a drop-in **`mars-globe` JS package** (NPM / Web Component / Cesium plugin) to add a configured 3D Mars globe to any app in a few lines. |
| **Public** | Explore Mars in 3D on real NASA imagery + MOLA elevation read-out, browse what's been observed, and view published candidate-mineral maps with plain-language caveats — no install, no login. |

## The scope change you asked for: Nili Fossae → all of Mars
Today the catalogue is **seeded with 6 real Nili Fossae CRISM scenes** (offline, so the demo always works). The plan's central upgrade is **live, whole-Mars discovery**: query NASA's archives on demand so the catalogue can surface CRISM (and other) products **anywhere on Mars**, by region or map viewport, while still downloading heavy data **only on demand** (never the whole archive).

- **Discovery, not bulk download.** The backend queries the **PDS Orbital Data Explorer (ODE) REST API** (`oderest.rsl.wustl.edu`) for product IDs, dates, footprints, and metadata, by bounding box / target / instrument. Results merge into the local catalogue (SQLite dev / PostGIS prod).
- **Download on demand.** Only when a user runs an analysis is the selected product's data fetched to local storage; the global basemap and MOLA DEM are already streamed live (Trek WMTS; MOLA via `/vsicurl` range reads).
- **Honest cadence.** CRISM targeted observations ended in 2018, so MarsGIS surfaces *newly released / newly indexed* products — it does not promise new live Mars observations.

## Prior art — evaluate before reinventing
MarsGIS deliberately reuses NASA/USGS infrastructure and only builds the thin, novel workflow layer:

| Resource | What it already offers | How MarsGIS relates |
|---|---|---|
| **NASA Mars Trek (WMTS)** | Mars basemaps + elevation tiles | **Reused directly** as the basemaps (Viking color, MOLA shaded relief) and MOLA DEM. |
| **NASA-AMMOS MMGIS** | Configurable planetary web GIS + Docker | Evaluated as a base. We ship a small custom Cesium viewer because MarsGIS's value is the discovery→SAM→reproduce workflow, not the globe; the comparison is a documented deliverable (Phase 0/8). |
| **JMARS / PlanetServer** | Desktop planetary GIS / web CRISM analysis | Studied for workflow gaps; MarsGIS targets a *reproducible, Docker-packaged* one-click workflow. |
| **PDS ODE + CRISM MTRDR/MICA** | The actual data + reference spectra | **The data foundation** — discovered live and fetched on demand. |

## Architecture — keep it small
One Python app (API + processing) behind a React/Cesium frontend; split a worker out only when long jobs demand it.

```
Researcher ─▶ React + CesiumJS (3D Mars globe, catalogue, analysis, results)
                     │  REST /api/*            │  result tiles (.png)
                     ▼                         ▼
             FastAPI (catalogue · discovery · jobs · tiler · elevation)
                 │                    │
      Data catalogue (SQLite│PostGIS) │  Science engine (NumPy/rasterio SAM)
                 │                    │
   NASA/PDS archives (ODE, Trek, MOLA, MICA)   ▼
   discovered live, fetched on demand    GeoTIFF (COG) + JSON provenance ─▶ map overlay
```

**Stack (unchanged, already built):** React + TypeScript + Vite + CesiumJS · Python 3.12 + FastAPI · NumPy/Rasterio/Spectral SAM engine · SQLite (dev) → PostgreSQL/PostGIS (prod) · Docker. Go/GeoServer/GeoNode/Redis/Kubernetes are **not** used until a documented need appears.

## Data-refresh / discovery system
Separate *discovering products* from *processing them*. Refresh strategy per item:

| Information | Strategy |
|---|---|
| Product catalogue | Manual `refresh` command first → scheduled ODE queries once reliable |
| Observation metadata / footprints | Refresh when a product is new or changed (upsert by id, idempotent) |
| CRISM source cubes | **Download on demand** at analysis time |
| Mineral reference library | Versioned, updated deliberately |
| Processed mineral maps | Generated on demand, cached |
| Basemaps / MOLA DEM | Streamed live from Trek / `/vsicurl`; no copy stored |

## Current status (honest)
Already built and verified end-to-end (engine 63 tests, backend 29 tests, frontend typecheck/lint/test/build, a live job producing a localized candidate map, `docker compose config`):
- ✅ Interactive 3D Mars globe on **real** Trek imagery, Mars ellipsoid + geographic tiling, MOLA **elevation read-out** at the cursor.
- ✅ CRISM catalogue (6 real Nili Fossae scenes) with clickable footprints + metadata inspection.
- ✅ Validated **SAM** engine (standalone package + CLI + importable) producing angle + candidate COGs, provenance, report.
- ✅ Results overlay + legend + opacity + stats + **GeoTIFF (COG) downloads** + provenance; pixel/spectrum inspector; "candidate, not confirmed" enforced structurally.
- ✅ Docker engine image + `docker compose` stack; SQLite-default / PostGIS-prod; frozen API contract + OpenAPI.
- ✅ Live **whole-Mars discovery** via PDS ODE (`/api/observations/discover`) + "Discover across Mars" UI; idempotent merge; download-on-demand.
- ✅ Real-cube **analysis on demand** (`ENGINE_CUBE_SOURCE=archive`): streams a bounded AOI subset of a real MTRDR cube via GDAL `/vsicurl` range reads (no bulk download) and runs SAM on it.

**New target (this update): a reusable `mars-globe` developer package** (see "Reusable developer package" below). Remaining: more reference minerals, 3D terrain relief, and the prior-art/evaluation write-up.

## Roadmap
| Phase | Deliverable | Done when | Status |
|---|---|---|---|
| 0 Feasibility | Compare MMGIS / Trek / JMARS / PlanetServer | Documented what to reuse vs build | 🔜 write-up pending (decisions already made) |
| 1 Map | 3D Mars globe, real imagery, nav | Globe + Trek layers aligned on Mars CRS | ✅ |
| 2 Layers | Terrain, elevation, footprints | Layers co-register; MOLA elevation read-out | ✅ |
| 3 Catalogue | Search + inspect CRISM observations | Metadata/footprints traceable to source | ✅ (seeded) |
| 4 **Data refresh** | **Discover newly available products across all of Mars** | Live ODE queries by bbox/region; idempotent merge; no dupes; provenance kept | ✅ |
| 5 Analysis | SAM on a validated observation (sample + real-cube on demand) | Output matches an independent reference impl; archive subset streams via /vsicurl | ✅ |
| 6 Results | Display + export mineral-match maps | GeoTIFF + metadata + provenance downloadable | ✅ |
| 7 Docker | Reproducible deployment | Clean env launches via documented steps | ✅ (compose + engine image) |
| 8 Evaluation | Compare vs existing tools / science | Strengths, limits, gaps documented | 🔜 |
| 9 **Dev package** | Reusable `mars-globe` (NPM + Web Component + Cesium plugin) | `npm i mars-globe` adds a configured 3D Mars globe in ≤3 lines; published to npm + GitHub | 🔜 **next** |

## Docker image milestones
`0.1.0` map + search UI (external basemap) → `0.2.0` catalogue + metadata → `0.3.0` SAM processing + overlays → `1.0.0` documented deploy, pinned deps, persistent outputs, reproducibility tests, tested release. **Current build already spans 0.3→1.0 features**; the version is pinned from git tags. The image never bundles large CRISM cubes — users fetch products on demand; generated outputs persist outside the container.

## Deliberately left out (until a documented need)
GeoServer/GeoNode · Redis/distributed queue · Kubernetes · extra languages for appearance · a general-purpose multi-agent AI *in the product* · automatic mineral identification without validation · promises of real-time Mars observations.

## Deliverables
1. **Open-source repo** — code, frozen contract + OpenAPI, tests, docs, data-source citations.
2. **Public Docker image** `ghcr.io/<owner>/marsgis-engine:<semver>` — reproduces one documented analysis on a user's own data.
3. **Hosted Web GIS + a live, whole-Mars discovery catalogue** + validated candidate-mineral maps with provenance and downloads; outputs archivable to Zenodo.
4. **Reusable `mars-globe` JS package** — the Mars-configured Cesium globe extracted as a framework-agnostic library (NPM package + `<mars-globe>` Web Component + CesiumJS plugin), so any developer can add a 3D Mars globe in a few lines; published to npm + GitHub with a live demo.

## Reusable developer package: `mars-globe`
Configuring Cesium (or any web‑GIS lib) for Mars is fiddly and poorly documented — override the ellipsoid to **3,396 km × 3,376 km**, strip Earth atmosphere/skybox/geocoder, and wire NASA Mars Trek's geographic tile scheme. Most developers don't know how. **MarsGIS already solved this** (`frontend/src/config/cesium.ts`, `cesium/imageryProviders.ts`, `cesium/LayerManager.ts`, the four verified Trek basemaps), so this deliverable is **extraction, not new work**: lift that core into a standalone library for the broader planetary/space community — rover & mission tracking, crater/volcano databases, education & museum globes, MOLA topography inspection.

One core, three distribution forms:
- **NPM package** (`mars-globe`): `createMarsGlobe(container, { defaultBasemap: 'viking' | 'mola' })` returns a ready viewer with `.setBasemap(...)`; usable from React / Vue / Svelte / plain JS in ~3 lines.
- **Web Component** (`<mars-globe basemap="viking">`): a `<script>` tag + one element — drops into any HTML page, blog, or WordPress with no Cesium knowledge.
- **CesiumJS plugin** (`setupMarsGlobe(viewer, { basemap })`): for developers who already have a Cesium `Viewer` and just want it turned into Mars.

Packaging notes: Cesium is a **peer dependency** (not bundled, avoids version clashes); the package ships the Mars config + Trek basemap presets + a thin globe factory + TypeScript types. Basemaps stream from NASA Mars Trek (attribution bundled); **no Cesium Ion token required**. MIT‑licensed. A Docker image serves non‑developers; this package serves developers — the two distribution tracks are complementary.

## How we judge success
The end-to-end demo: a researcher **discovers a real CRISM product anywhere on Mars**, selects it from the map, runs SAM, inspects the candidate layer, and **reproduces** it from the public Docker release — then we document which steps MarsGIS makes easier than JMARS/MMGIS/PlanetServer, what it lacks, and whether outputs are scientifically defensible.

## Key risks
Mars-vs-Earth CRS/terrain mismatch (handled: Mars ellipsoid + geographic TMS + on-body transforms) · large cubes (fetch on demand, windowed processing) · ODE query/footprint variance (validate per product type, upsert idempotently) · over-claiming (candidate-only, enforced) · scope creep (ship discovery + one validated workflow before anything else).

See [architecture.md](architecture.md) for the system design, [connections.md](connections.md) for wiring, and [MEMORY.md](MEMORY.md) for current state.


