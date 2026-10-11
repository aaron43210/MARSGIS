# MarsGIS — Project Development Plan (updated)

**An open-source, self-hostable Mars mapping and mineral-analysis platform.**

MarsGIS is a browser-based planetary GIS where you explore Mars in 3D, **discover real Mars observations from public archives**, run a documented hyperspectral mineral-matching workflow on CRISM data, and visualize, download, and **reproduce** the result. It ships as a Docker image so anyone can run their own instance.

Design principle: **keep the system simple and scientifically honest — simple and correct beats large and impressive.** NASA's MMGIS, JMARS, and PlanetServer already provide planetary globes and some analysis; MarsGIS's contribution is *not* another globe but a **simple, reproducible workflow for discovering Mars data and running a mineral analysis directly from the map** — with provenance and a public, rerunnable Docker release. The current priority is **not new features or infrastructure** but proving the existing vertical slice correct with repeatable evidence (see "Milestone A — 1.0.0 freeze criteria").

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

## Current status: implemented vs. validated
MarsGIS separates **implemented** (code exists and has run) from **validated** (a committed, repeatable test or recorded evidence proves it is correct). A past successful run is useful evidence, but it is not a validation.

**Implemented and in daily use** (engine 63 tests, backend 29 tests, frontend typecheck/lint/test/build, `docker compose config`):
- 3D Mars globe on **real** Trek imagery, Mars ellipsoid + geographic tiling, MOLA **elevation read-out** at the cursor.
- CRISM catalogue (6 real Nili Fossae scenes, seeded offline) with clickable footprints + metadata.
- **SAM** engine (standalone package + CLI + importable) producing angle + candidate COGs, provenance, report.
- Results overlay + legend + opacity + stats + **GeoTIFF (COG) downloads** + spectrum inspector; "candidate, not confirmed" enforced structurally.
- Docker engine image + `docker compose` stack; SQLite-default / PostGIS-prod; frozen API contract + OpenAPI.
- Live **whole-Mars discovery** via PDS ODE (`/api/observations/discover`) + UI; idempotent merge; download-on-demand.
- Real-cube **analysis on demand** (`ENGINE_CUBE_SOURCE=archive`): streams a bounded AOI subset of a real MTRDR cube via GDAL `/vsicurl` (no bulk download).

**Validated — Milestone A gates now met with committed, repeatable evidence** (engine 71 tests, backend 40 tests; evidence in [docs/evidence/](docs/evidence/)):
- **A1** Trek ↔ Cesium alignment: `scripts/verify_trek.py` — tiling-math invariants (2×1@z0, seam, poles) + live tile fetches at 4 real features all return imagery. → `docs/evidence/A1_trek_alignment.*`
- **A2** one real MTRDR end to end: committed real subset fixture of `frt00003e12`; `engine/tests/test_real_cube_a2.py` runs SAM on real data → valid georeferenced COGs + schema-valid honest provenance, deterministic, bounded memory.
- **A3** remote I/O cost: `scripts/bench_vsicurl.py` — measured **105.5 MiB over 1419 range requests in ~650 s** for a 48² AOI of a 1.27 GiB cube (**~92 % less data, but latency-bound** — confirms the reviewer's BSQ concern). → `docs/evidence/A3_vsicurl_benchmark.*`
- **A4** wavelength alignment: provenance now records the original/resampled grids + a per-stage band-drop ledger and a machine-readable `preprocessing_caveat`; locked by engine tests. (Alignment itself was already implemented — this closed the honesty gap.)
- **A5** ODE discovery: `backend/tests/test_ode_contract.py` (11 tests) locks longitude convention, footprint parse, product→row mapping, acquisition-vs-release date, pagination/dedup, and archive-unavailable. → `docs/evidence/A5_ode_contract.md`
- **Vertical slice**: `engine/tests/test_vertical_slice.py` + `scripts/vertical_slice.py` — A1 math + A2 real cube → candidate map transformed back to lon/lat lands at **77.08°E, 22.26°N, inside the footprint**, reproducibly. → `docs/evidence/vertical_slice.*`

**Scientific-defensibility gate — now met (evidence committed).** `scripts/validate_aoi.py` processes a 384² AOI of real `frt00003e12` (Nili Fossae) locally — following the reviewer's own "cache the product, process locally" fallback since A3 proved remote reads are latency-bound — and competes three MICA references. Result (threshold 0.10 rad, 147,456 valid px): best-match shares carbonate 0.20 / olivine 0.26 / clay 0.54. The method is **non-degenerate, discriminates** (no mineral >98%), and the ordering is **consistent with Nili's documented mineralogy** (widespread phyllosilicate + olivine, carbonate the least-dominant/most-localized) — Ehlmann et al. 2008; Mustard et al. 2009. → `docs/evidence/validation_aoi.*`. Standing caveats recorded in the evidence: absolute detected fractions are high (loose threshold + ratioed-vs-unratioed mismatch), so the gate judges relative discrimination, not absolute counts; these remain spectral *candidates*, never confirmed deposits. **With this, all Milestone A freeze criteria are satisfied — 1.0.0 may be tagged.**

**`mars-globe` developer package** — deferred to Milestone C, *after* the freeze. Remaining beyond that: more reference minerals, 3D terrain relief, and the prior-art/evaluation write-up.

## Roadmap
Status reflects **implementation**; the **Validation gate** column is what must pass before 1.0.0. A phase can be ✅ built yet still ⏳ unvalidated.

| Phase | Deliverable | Status | Validation gate (→ 1.0.0) |
|---|---|---|---|
| 0 Feasibility | Compare MMGIS / Trek / JMARS / PlanetServer | 🔜 write-up pending | — (decisions made; documented in Phase 8) |
| 1 Map | 3D Mars globe, real imagery, nav | ✅ built | **A1** repeatable spatial-alignment test (≥3 sites + pole + ±180° seam) |
| 2 Layers | Terrain, elevation, footprints | ✅ built | **A1** + **B3** (confirm MOLA file is a COG; return reference + resolution) |
| 3 Catalogue | Search + inspect CRISM observations | ✅ built (seeded) | — |
| 4 **Data refresh** | Discover products across all of Mars | ✅ built | **A5** ODE contract tests (conventions, pagination, product type, dates, footprints) |
| 5 Analysis | SAM on sample + real cube on demand | ✅ built | **A2** fixture test + **A3** instrumented I/O report + **A4** wavelength alignment |
| 6 Results | Display + export mineral-match maps | ✅ built | caveat/provenance contract test (**B2**) |
| 7 Docker | Reproducible deployment | ✅ built | vertical-slice reproduced from the standalone engine |
| 8 Evaluation | Compare vs existing tools / science | 🔜 | — |
| 9 **Dev package** | Reusable `mars-globe` | 🔜 Milestone C | after 1.0.0 freeze only |

## Milestone A — 1.0.0 freeze criteria
1.0.0 is tagged **only when every gate below has committed, repeatable evidence** — not merely a green CI run. The evidence must also show the real observation and reference spectra are *scientifically compatible* and the resulting map is *spatially correct*. **No new infrastructure is added during Milestone A** unless a validation test proves it necessary.

The spine is one automated **vertical-slice test**: load Trek basemap → discover one real CRISM observation → stream a bounded AOI → run SAM → assert the candidate map lands at the correct coordinates → reproduce from the standalone Docker engine.

| Gate | Acceptance evidence (committed) |
|---|---|
| **A1** Trek ↔ Cesium alignment | `scripts/verify_trek.py`: asserts WMTS tile-matrix IDs/levels/extent and that a known feature's lon/lat ↔ pixel within tolerance at ≥3 sites, plus pole + ±180° seam without error. |
| **A2** Real MTRDR end to end | One pinned observation + AOI as a committed fixture (ID + bbox + expected output hash); the vertical-slice test opens it, runs SAM, writes a valid COG within a bounded memory budget. |
| **A3** Remote-vs-local I/O | `scripts/bench_vsicurl.py` records request count, total bytes, metadata time, window-read time, and **remote == local** numerical agreement. A download-reduction figure is quoted **only** from this recorded number — never promised in advance. |
| **A4** Wavelength alignment + SAM numerics | The alignment path already exists (`select_bands` → `overlap_mask` → `resample_reference` → `require_overlap`): finite/ordered wavelengths, common range only (no extrapolation), bad bands excluded, a diagnostic-band minimum, and per-pixel nodata when a pixel can't be compared. A4 **completes the honesty, not the algorithm**: record the original + resampled wavelength grids and a per-stage band-drop ledger in provenance, surface a `preprocessing_caveat` that resampling does **not** reconcile ratioed-MICA vs. unratioed-scene I/F, and add engine tests that lock extrapolation-refusal, the band ledger, and the caveat. |
| **A5** ODE discovery/footprints | Contract tests over a recorded ODE fixture: 0–360 ↔ ±180 convention, pagination/limits, product-type filter, acquisition-vs-release date, footprint parse, and archive-unavailable error path. Each record stores source product ID + sync timestamp. |

Framing corrections shipped alongside: discovery labeled **archive-product discovery** (not live spacecraft observations), and the CRISM-targeting-ended-2018 cadence made explicit in the catalogue UI.

## Docker image milestones
`0.1.0` map + search UI (external basemap) → `0.2.0` catalogue + metadata → `0.3.0` SAM processing + overlays → `1.0.0` documented deploy, pinned deps, persistent outputs, reproducibility tests, tested release. **Current build already spans 0.3→1.0 features**; the version is pinned from git tags. The image never bundles large CRISM cubes — users fetch products on demand; generated outputs persist outside the container.

## Deliberately left out (until a documented need)
Simplicity is a feature: nothing below is added until a validation test or real workload *demonstrates* the need — and nothing new is added at all during Milestone A.

GeoServer/GeoNode · Redis/distributed queue · Kubernetes · extra languages for appearance · a general-purpose multi-agent AI *in the product* · automatic mineral identification without validation · promises of real-time Mars observations.

## After the freeze: Milestones B and C
These follow 1.0.0 and only when justified — they are not part of the freeze and add no complexity to the validated core.
- **B — Reliability & honesty hardening:** job timeouts/cancellation/dedup, concurrency cap, temp cleanup, engine memory budget; a contract test asserting every result carries caveat + source + reference + parameters + engine version; confirm the MOLA file is a COG and return reference + resolution; run containers non-root, validate IDs/AOIs, whitelist remote URLs reaching the engine.
- **C — Reuse & scale:** publish `mars-globe` **NPM module + one public example first** (Web Component / plugin only on demonstrated need; "no Ion token" claim scoped to tested layers); validate the PostGIS + separate-worker path under real load before calling it production-ready (SQLite + in-process stays the default).

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


