# MarsGIS — Project Plan

An interactive planetary geospatial-intelligence platform for Mars surface exploration and hyperspectral mineral mapping, with a reproducible analysis engine shipped as a public Docker image.

**Primary product:** an interactive Mars map/dashboard with searchable observations, selectable layers, feature inspection, and downloadable geospatial results.
**Research contribution:** evaluate spectral-similarity methods (SAM first) for identifying candidate mineral signatures in CRISM data, related to Martian geological context.
**Open-science contribution:** a versioned Docker image, source code, example workflows, and reproducible mineral-mapping outputs.

## Research question

> How effectively can spectral-similarity methods identify **candidate** mineral signatures in selected CRISM observations, and how can the results be made reproducible and accessible through an interactive planetary GIS?

Objectives: (1) a map-led discovery/visualization system; (2) a CRISM-compatible hyperspectral workflow; (3) candidate-vs-reference spectral comparison; (4) evaluation against existing products/published interpretations; (5) packaged reproduction; (6) an interface that makes results, provenance, and **uncertainty** understandable. A high classification score is **not** a precondition for success — honest uncertainty is a legitimate finding.

## Scope: three levels of coverage

| Level | What the map shows | Why |
|---|---|---|
| Global | Mars basemaps, elevation, geology, place names, observation footprints | Useful immediately |
| Regional | CRISM observations + context imagery for **Nili Fossae** | Detailed exploration |
| Observation | One hyperspectral cube, SAM analysis, mineral output layers | Scientific processing |

First experiment: one CRISM MTRDR scene over Nili Fossae (`frt00003e12`), SAM against a MICA **carbonate** reference, then expand to olivine and clay/phyllosilicate.

## Build strategy — map first, science integrated incrementally

| Phase | Goal | Deliverable |
|---|---|---|
| 1 | Build the global Mars map (Cesium, Mars ellipsoid, verified Trek basemaps, nav, layer manager, feature search) | Working Mars GIS shell |
| 2 | Make the map data-aware (observation catalogue table, CRISM footprints, click-to-inspect, filters) | Users select a real CRISM observation from the map |
| 3 | Geology + terrain context (USGS SIM 3292, elevation/shaded relief, optional THEMIS/CTX) | Layered GIS with geological context |
| 4 | Analysis workspace (choose observation + mineral + method + threshold → submit → monitor) | Functional analysis form wired to the map |
| 5 | First real pipeline (MTRDR read → bands/masks → MICA reference → SAM → angle + candidate rasters → provenance) | A real candidate mineral map from a real run |
| 6 | Package the engine in Docker (CLI, tests, provenance) and publish to GHCR | Public, versioned reproducible image |
| 7 | Results, export & inspection (legends, pixel/spectrum inspector, quality layers, GeoTIFF + report download, provenance links) | An inspectable, reproducible scientific result |
| 8 | Expand & publish (more observations, olivine/clay, method comparison, Zenodo) | Reusable open-source platform |

The 4 user-facing screens are **workspace modes** over one persistent globe canvas: Global explorer → Observation explorer → Analysis workspace → Results.

## Indicative 16-week schedule

| Weeks | Focus | Milestone |
|---|---|---|
| 1–2 | Data verification, map prototype | Global Mars map |
| 3–4 | Basemap, catalogue, footprints | Data-aware GIS |
| 5–6 | Geology + observation selection | Regional explorer |
| 7–8 | Analysis workspace + CRISM ingestion | Functional analysis workflow |
| 9–10 | SAM + first output raster | First candidate mineral map |
| 11 | Scientific comparison + evaluation | Evaluation report |
| 12 | Docker packaging + reproducibility | Public engine release |
| 13–14 | Results panel, downloads, metadata, styling | Complete user workflow |
| 15 | Integration tests, docs, deployment | Release candidate |
| 16 | Thesis + demonstration | Final capstone |

If time is tight, reduce mineral classes and secondary datasets — **never** drop validation.

## Deliverables

- **A.** Open-source repo (code, contract, tests, docs, example configs).
- **B.** Public Docker image `ghcr.io/<owner>/marsgis-engine:<semver>` with a tested example + documented I/O.
- **C.** Hosted Web GIS + validated regional mineral maps with provenance and downloads; research outputs archived to Zenodo.

## Version 1 acceptance checklist

- [ ] Runs out-of-the-box with no extra infra: `cp .env.example .env && make up` (or `uvicorn` + `npm run dev`) → a working map on SQLite + in-process worker + in-process engine, seeded with verified Nili Fossae data.
- [ ] Primary product is the map: one persistent CesiumJS Mars globe with the **verified** Viking + MOLA-ClrShade Trek basemaps rendering.
- [ ] CRISM MTRDR footprints over Nili Fossae draw as clickable polygons from `GET /api/observations`.
- [ ] End-to-end SAM experiment: pick observation + MICA carbonate → `POST /api/analysis-jobs` → poll → `succeeded` → result with angle COG + candidate mask COG + stats + legend + provenance.
- [ ] Result overlays register pixel-for-pixel via `GET /api/results/{id}/tiles/{z}/{x}/{y}.png` over the custom Mars **geographic** TMS; `/preview.png` fallback works.
- [ ] Pixel inspector plots reflectance-vs-wavelength against the MICA reference (uPlot) with the spectral angle shown.
- [ ] Scientific honesty enforced: the candidate-match caveat is a required field on result/stats/legend/provenance and visibly rendered; the continuous angle raster is always retained; nothing is labelled a confirmed deposit.
- [ ] Contract is single-source and drift-proof: schemas → `contracts/openapi.yaml` generated; TS mirror is `tsc --strict` clean; backend `/openapi.json` equals the committed spec (CI-checked).
- [ ] Data fetched via APIs/services only (ODE, PDS, MICA, USGS pygeoapi, Trek) — no bulk archive in the repo; only tiny synthetic/sample fixtures committed; pipeline + all tests run fully offline.
- [ ] Coordinates consistent: Mars IAU 2000 degrees, east-positive lon `[-180,180]`, planetocentric lat `[-90,90]`.
- [ ] Production path by config only: `DATABASE_URL`→PostGIS, `JOB_BACKEND=arq`, `ENGINE_MODE=container` — no code change.
- [ ] Standalone engine artifact: `marsgis-engine` CLI + Python API + GHCR image, versioned from git tag.
- [ ] Quality gates green: frontend lint+typecheck+vitest+build; backend+engine ruff+pytest; docker-build smoke; all offline in CI.
- [ ] Security posture explicit: dev binds 127.0.0.1; unauthenticated job submission hard-bounded (enum method, AOI/count caps, per-client quota, per-job timeout + rlimits); `REQUIRE_API_KEY` gate available and flagged mandatory for public hosting.

## Verification plan (how we prove it)

Run after the build (see [`connections.md`](connections.md) for exact commands). Highlights:

1. **Contract integrity** — `python contracts/gen_openapi.py && openapi-spec-validator contracts/openapi.yaml` (12 paths).
2. **Engine offline run** — `marsgis-engine run --cube engine/sample_data/sample_crism_nili.img --mineral carbonate --method SAM --threshold 0.1 --out /tmp/sam_out --timestamp placeholder` → COG + provenance + report; `gdalinfo` confirms COG + Mars CRS.
3. **Engine + backend tests** — `pytest -q` in each (SAM invariants; job lifecycle; tiles return PNG; security limits).
4. **Backend boots zero-setup** — `uvicorn app.main:app` on default SQLite → `/api/health` ok, `/api/layers` returns verified Trek layers, `/openapi.json` equals the committed spec.
5. **Live tile fetch** — `curl` the verified Trek Viking tile → `200 image/jpeg` (re-verified this session).
6. **Frontend** — `npm ci && npm run lint && npm run typecheck && npm run test -- --run && npm run build`.
7. **Full stack** — `make up` → globe + Trek basemap + Nili Fossae footprints; submit a SAM job, poll to `succeeded`, confirm the result registers on the globe with the candidate caveat shown.
8. **Production smoke (config only)** — PostGIS + arq+Redis path reaches `succeeded` identically.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Mars basemap/projection mismatch | Verified Trek endpoints + Mars `Ellipsoid` + `GeographicTilingScheme` before integrating other layers |
| Large hyperspectral cubes / OOM | Windowed row-block processing, float32, no full-cube materialization; fetch subsets, never the archive |
| Missing overlapping imagery | Draw coverage footprints; mark optional layers' availability (`verified`/`unconfirmed`) |
| Invalid/ambiguous spectra | Preserve masks, honor ENVI `bbl`, document preprocessing, show uncertainty (angle raster retained) |
| Ratioed-MICA vs un-ratioed scene | SAM albedo-invariance + optional continuum removal + diagnostic window; caveat documented in provenance/report |
| Weak ML ground truth | Start with spectral methods; add supervised ML only when defensible labels + evaluation exist |
| Excessive scope | Prioritize map, discovery, one real analysis, Docker, result visualization |
| Public processing cost/abuse | Static outputs first; bounded, isolated, quota'd server-side jobs; `REQUIRE_API_KEY` for public hosting |
| Misleading mineral claims | "Candidate" labeling enforced structurally; never "confirmed deposit" |


