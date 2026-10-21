# Changelog

All notable changes to `marsgis-engine` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres
to [Semantic Versioning](https://semver.org/). The version here is the source of
truth for the published image tag `ghcr.io/<account>/marsgis-engine:<semver>`.

## [0.1.0] - 2026-10-11

### Added
- Vectorized, row-block **Spectral Angle Mapper** core (`science/sam.py`) with
  per-pixel pairwise NaN handling and albedo-scale invariance.
- Dual **ENVI reader** (`io/envi_reader.py`): spectra/wavelengths/bbl/ignore via
  SPy, CRS/affine via rasterio, with a logged Mars-2000 equirectangular CRS
  fallback (`crs_is_fallback`). No re-calibration, no reprojection.
- **MICA `.tab` reference loader** (`io/reference.py`) with alias resolution via
  `data/minerals.json`, PDS `.lbl`-aware column defaults, um→nm conversion, and
  SHA-256.
- Reference **resampling** (linear + optional FWHM-aware gaussian) and optional
  convex-hull **continuum removal**.
- **COG writer** (`io/raster_writer.py`): tiled interim GTiff →
  `rasterio.shutil.copy(driver="COG")`; angle (float32 radians, NaN nodata) and
  candidate (uint8 {0,1,255}) rasters preserving the input CRS/affine.
- **Provenance** JSON (`io/provenance.py`) conforming to
  `schemas/provenance.schema.json` (v1.0.0), with input SHA-256, pinned library
  + GDAL versions, result stats, a `--timestamp placeholder` for reproducible
  output, and the candidate-not-confirmed disclaimer; plus a human-readable
  **report** (`io/report.py`).
- End-to-end orchestration `run_sam` with `RunParams` / `SamResult`
  (`science/pipeline.py`) and the public API re-exports in `__init__.py`.
- **CLI** `marsgis-engine` (`cli.py`): `run`, `info`, `list-minerals`,
  `fetch-references`, `version`; exit codes 0/2/3/4.
- Opt-in `fetch-references` downloader (`io/fetch.py`) — single small files, not
  bulk mirrors; never on the default run path.
- Bundled **REAL** public-domain CRISM MICA type spectra (mg/fe_ca carbonate,
  mg/fe olivine, fe_smectite) with `NOTICE.txt` (source, retrieval date,
  SHA-256).
- Fully offline test-suite (`tests/`) on synthetic ENVI fixtures + bundled MICA:
  SAM, resample, continuum, wavelengths, ENVI reader, reference, COG writer,
  provenance (schema-validated), pipeline (planted carbonate < threshold),
  and CLI.

### Scientific notes
- A thresholded match is a **candidate**, never a confirmed deposit; the
  continuous angle raster is always retained.
- The ratioed-MICA vs un-ratioed-scene I/F mismatch is documented and partially
  mitigated (SAM albedo invariance + continuum removal + wavelength windowing).

[0.1.0]: https://github.com/aaron43210/MARSGIS/releases/tag/engine-v0.1.0
