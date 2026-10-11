# marsgis-engine

The MarsGIS **science engine**: a standalone, reproducible Python package
(`marsgis_engine`) that runs a **Spectral Angle Mapper (SAM)** on an
analysis-ready CRISM MTRDR cube against a MICA reference spectrum and emits
georeferenced, Cloud-Optimized GeoTIFFs plus a machine-readable provenance
record.

It is importable by the backend **and** exposed as a `marsgis-engine` CLI (the
entrypoint of the standalone image `ghcr.io/<account>/marsgis-engine`).

> **Scientific honesty.** A thresholded SAM result is a **candidate** spectral
> match, **never a confirmed mineral deposit**. The continuous spectral-angle
> raster is always retained alongside the binary mask, and the
> candidate-not-confirmed disclaimer is embedded in every output.

---

## What it does / does NOT do

| Does | Does NOT |
| --- | --- |
| Read an ENVI `.img`/`.hdr` MTRDR cube (spectra via SPy, CRS/affine via rasterio) | Fetch or stage the MTRDR cube (backend/data concern) |
| Resample a MICA `.tab` reference onto the cube grid | Re-calibrate / atmospherically correct (MTRDR is analysis-ready I/F) |
| Vectorized, row-block SAM in radians | Reproject or retile (backend tiler does that) |
| Optional convex-hull continuum removal | Make any geologic claim |
| Write angle COG + candidate COG + provenance JSON + report | Call a candidate a confirmed deposit |

Outputs inherit the input Mars CRS/affine losslessly.

## Install

```bash
# Dev install (editable) with the test extras:
pip install -e "./engine[dev]"

# Runtime only (what the backend imports):
pip install ./engine
```

Python **3.12** is the pinned interpreter for containers and CI (host 3.14 is
best-effort local only). `rasterio` wheels bundle their own GDAL (including the
COG driver), so no system GDAL is required.

## CLI

```bash
# The canonical run (candidate carbonate detection, Nili Fossae first experiment):
marsgis-engine run \
    --cube /data/frt00003e12_07_if166j_mtr3.img \
    --mineral carbonate \
    --method SAM \
    --threshold 0.10 \
    --out /data/out

# Inspect a cube before a long run:
marsgis-engine info --cube /data/frt00003e12_07_if166j_mtr3.hdr

# List bundled MICA aliases:
marsgis-engine list-minerals

# Opt-in fetch of an additional MICA phase (single small file, not a bulk mirror):
marsgis-engine fetch-references --mineral al_smectite --dest ./extra_refs

marsgis-engine version
```

Key `run` flags: `--reference PATH` (instead of `--mineral`),
`--threshold-units {rad,deg}`, `--wmin/--wmax --wavelength-units {nm,um}`,
`--continuum-removal/--no-continuum-removal`, `--resample {linear,gaussian}`,
`--mask-bad-bands/--no-mask-bad-bands`, `--out-prefix`, `--mars-crs`,
`--timestamp` (use `placeholder` for byte-reproducible output).

Exit codes: `0` ok, `2` usage, `3` data/parse, `4` io.

## Docker

The image is built from `engine/Dockerfile` (owned by the infra unit). Inputs
and outputs are exchanged through a mounted volume:

```bash
docker run --rm -v "$PWD/data:/data" ghcr.io/<account>/marsgis-engine \
    run --cube /data/cube.img --mineral carbonate --threshold 0.10 --out /data/out
```

## Python API

```python
from marsgis_engine import run_sam, RunParams, SamResult, load_cube, load_reference

params = RunParams(threshold_rad=0.10, out_dir="out", timestamp="placeholder")
result: SamResult = run_sam("cube.img", "carbonate", params)

print(result.angle_path)  # <prefix>_SAM_angle.tif      (COG float32 radians, NaN nodata)
print(result.candidate_path)  # <prefix>_SAM_candidate.tif  (COG uint8 {0,1,255})
print(result.provenance_path)  # <prefix>_provenance.json
print(result.report_path)  # <prefix>_report.txt
print(result.stats["detected_fraction"])
```

## Output artifacts (stable contract)

| File | Type | Meaning |
| --- | --- | --- |
| `<prefix>_SAM_angle.tif` | COG, float32, 1 band | Spectral angle in **radians** (lower = closer match), nodata = NaN |
| `<prefix>_SAM_candidate.tif` | COG, uint8 | `0` non-match, `1` candidate, `255` nodata |
| `<prefix>_provenance.json` | JSON | Conforms to [`schemas/provenance.schema.json`](schemas/provenance.schema.json) (v1) |
| `<prefix>_report.txt` | text | Human-readable summary + scientific disclaimer |

Both rasters carry the input CRS + affine (or the logged Mars-2000 fallback).

## Reference data

Bundled under `src/marsgis_engine/data/mica/` are **REAL** CRISM MICA type
spectra retrieved from the NASA PDS (public domain) — see
[`data/mica/NOTICE.txt`](src/marsgis_engine/data/mica/NOTICE.txt) for source,
retrieval date, and SHA-256 checksums. These are *reference* end-members, not
scene data and not detections. The engine uses the **ratioed I/F corrected**
column (wavelength um, column index 1).

## VERIFIED vs ASSUMED

| Status | Item |
| --- | --- |
| **VERIFIED** | MTRDR = analysis-ready ENVI `.img`/`.hdr` (float32, nm wavelengths, `data ignore value=65535`) |
| **VERIFIED** | MICA `.tab` are ASCII, col 1 = wavelength (um), col 2 = ratioed I/F corrected (per PDS `.lbl`); fetched 200 from `pds-geosciences.wustl.edu/.../mrocr_8001/data/` on 2026-10-11 |
| **VERIFIED** | `rasterio` COG driver writes a true, overview-bearing Cloud-Optimized GeoTIFF |
| **VERIFIED** | SAM is invariant to multiplicative albedo scaling (used to mitigate the ratioed/un-ratioed mismatch) |
| **ASSUMED** | MICA column order when no sibling `.lbl` is present (col0 wavelength / col1 ratioed I/F) — overridable with `--ref-*` flags, logged `ASSUMED:` |
| **ASSUMED** | Mars-2000 equirectangular fallback WKT when the ENVI header carries no resolvable CRS — logged and recorded as `crs_is_fallback=true` |

## Scientific caveats

- **Ratioed vs un-ratioed I/F.** MICA type spectra are *ratioed* I/F while an
  MTRDR scene pixel is *un-ratioed* I/F. SAM's albedo-scale invariance, optional
  continuum removal, and the diagnostic wavelength window partially mitigate the
  mismatch, but it is not fully eliminated. Scene-ratioing is documented future
  work.
- **Candidate ≠ confirmed.** Thresholding is an operator choice, not ground
  truth. Review the continuous angle raster and seek corroborating observations
  before any interpretation.
- **Nili Fossae first experiment.** Defaults target the Mg-carbonate 2.3/2.5 µm
  doublet (Ehlmann et al. 2008; Viviano-Beck et al. 2014).

## Testing

```bash
make -C engine test     # fully offline: synthetic ENVI fixtures + bundled MICA
```

Tests generate tiny synthetic cubes (`tests/synthetic.py`) with planted
carbonate pixels equal to a synthetic reference, asserting those pixels fall
below the threshold while the olivine-like background does not — all with zero
network access.
