#!/usr/bin/env python3
"""Validation-AOI step — the scientific-defensibility gate before 1.0.0.

Processes a LARGE, heterogeneous AOI of a real CRISM scene at a locality whose
mineralogy is independently documented, and checks the SAM output is defensible
rather than degenerate. Target: FRT00003E12, Nili Fossae — a documented
olivine-rich terrain with LOCALIZED Mg-carbonate (Ehlmann et al. 2008, Science
322:1828; Mustard et al. 2009, JGR). So the independent expectation is:

  * olivine should be the best match over broad areas,
  * carbonate should be present but localized (not scene-wide),
  * the method must DISCRIMINATE (not flag every pixel as the same mineral).

Because remote /vsicurl window reads are latency-bound (see A3), this follows
the reviewer's own fallback: download the source product once to a local cache
(gitignored, outside Docker) and process locally.

Run:  python scripts/validate_aoi.py            # uses .cache/validation/
      python scripts/validate_aoi.py --px 384   # AOI window size
Writes docs/evidence/validation_aoi.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "engine" / "src"))
EVIDENCE = ROOT / "docs" / "evidence"
CACHE = ROOT / ".cache" / "validation"

OBS = "frt00003e12"
IMG = CACHE / "frt00003e12_07_if166j_mtr3.img"
HDR = CACHE / "frt00003e12_07_if166j_mtr3.hdr"

# Minerals to compete for each pixel's best (smallest-angle) match.
MINERALS = ["carbonate", "olivine", "clay"]  # mg_carbonate, mg_olivine, fe_smectite
REFERENCE = "Ehlmann et al. 2008 (Science 322:1828); Mustard et al. 2009 (JGR 114:E00D12)"


def _prepare_local_cube(px: int, work: Path):
    """Read a central AOI from the cached full cube and write an engine-ready
    ENVI (real wavelengths + Mars map info) via the validated writer."""
    import rasterio
    from app.services.cube_fetch import _parse_hdr, _write_envi
    from rasterio.windows import Window

    meta = _parse_hdr(HDR.read_text(errors="ignore"))
    with rasterio.open(str(IMG)) as ds:
        w, h = ds.width, ds.height
        wp = min(px, w, h)
        c0 = max(0, w // 2 - wp // 2)
        r0 = max(0, h // 2 - wp // 2)
        win = Window(c0, r0, min(wp, w - c0), min(wp, h - r0))
        arr = ds.read(window=win).astype("float32")
        transform = ds.window_transform(win)
        crs_wkt = ds.crs.to_wkt() if ds.crs else None
        full_shape = (ds.count, ds.height, ds.width)
    base = work / f"{OBS}_aoi"
    _write_envi(base, arr, meta, transform, crs_wkt)
    return base.with_suffix(".img"), arr.shape, full_shape, crs_wkt is not None


def _angle_array(cube_img: Path, mineral: str, out_dir: Path):
    import numpy as np
    import rasterio
    from marsgis_engine import RunParams, run_sam

    res = run_sam(
        str(cube_img), mineral,
        RunParams(out_dir=str(out_dir), out_prefix=mineral, timestamp="placeholder", block_rows=16),
    )
    with rasterio.open(res.angle_path) as ds:
        return np.asarray(ds.read(1), dtype="float64"), json.loads(Path(res.provenance_path).read_text())


def main() -> int:
    import numpy as np

    ap = argparse.ArgumentParser(description="Validation-AOI scientific-defensibility gate")
    ap.add_argument("--px", type=int, default=384, help="central AOI window size")
    ap.add_argument("--threshold", type=float, default=0.10, help="SAM candidate threshold (rad)")
    args = ap.parse_args()

    record: dict[str, Any] = {
        "gate": "validation-aoi",
        "observation": OBS,
        "locality": "Nili Fossae",
        "independent_reference": REFERENCE,
        "expectation": "olivine broad; carbonate present but localized; method discriminates",
    }

    if not (IMG.exists() and HDR.exists()):
        record.update(status="incomplete", reason=f"cached cube missing under {CACHE}")
        return _finish(record, 2)

    work = Path(tempfile.mkdtemp())
    cube_img, aoi_shape, full_shape, has_crs = _prepare_local_cube(args.px, work)
    record["aoi_shape_bands_lines_samples"] = list(aoi_shape)
    record["full_cube_shape_bands_lines_samples"] = list(full_shape)
    record["aoi_has_real_crs"] = has_crs

    # SAM angle raster per competing mineral.
    angles: dict[str, Any] = {}
    bands_used: dict[str, int] = {}
    for m in MINERALS:
        arr, prov = _angle_array(cube_img, m, work / m)
        angles[m] = arr
        bands_used[m] = prov["wavelength_alignment"]["n_bands_used"]

    stack = np.stack([angles[m] for m in MINERALS], axis=0)  # (M, H, W)
    valid = np.all(np.isfinite(stack), axis=0)
    n_valid = int(valid.sum())
    thr = float(args.threshold)

    # Per-mineral detected fraction at the threshold.
    detected = {
        m: (float((angles[m][valid] <= thr).mean()) if n_valid else 0.0) for m in MINERALS
    }
    # Best (smallest-angle) match per valid pixel -> argmin share.
    best = np.argmin(stack, axis=0)
    best_share = {
        m: (float((best[valid] == i).mean()) if n_valid else 0.0)
        for i, m in enumerate(MINERALS)
    }

    record.update(
        status="ok",
        n_valid_pixels=n_valid,
        threshold_rad=thr,
        bands_used=bands_used,
        detected_fraction=detected,
        best_match_share=best_share,
    )

    # --- Defensibility criteria ----------------------------------------
    carb = detected["carbonate"]
    max_share = max(best_share.values())
    checks = {
        # SAM is not degenerate: carbonate neither 0 nor the whole scene.
        "carbonate_structured_not_saturated": 0.0 < carb < 0.98,
        # The method discriminates: no mineral wins ~every pixel.
        "discriminates_best_match_not_monopoly": max_share < 0.98,
        # Independent mineralogy ordering: olivine broader than carbonate.
        "olivine_broader_than_carbonate": best_share["olivine"] > best_share["carbonate"],
    }
    record["checks"] = checks
    record["defensible"] = all(checks.values())
    return _finish(record, 0 if record["defensible"] else 1)


def _finish(record: dict[str, Any], code: int) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "validation_aoi.json").write_text(json.dumps(record, indent=2) + "\n")
    _write_md(record)
    print(f"[validate] status={record['status']} defensible={record.get('defensible')}")
    if record["status"] == "ok":
        print(f"   valid px: {record['n_valid_pixels']}  threshold: {record['threshold_rad']} rad")
        print(f"   detected fraction: {record['detected_fraction']}")
        print(f"   best-match share: {record['best_match_share']}")
        for k, v in record["checks"].items():
            print(f"   {'✓' if v else '✗'} {k}")
    else:
        print(f"   {record.get('reason')}")
    print(f"[validate] evidence -> {EVIDENCE / 'validation_aoi.json'}")
    return code


def _write_md(record: dict[str, Any]) -> None:
    lines = [
        "# Validation AOI — scientific defensibility",
        "",
        f"- Observation: `{record['observation']}` — {record['locality']}",
        f"- Independent reference: {record['independent_reference']}",
        f"- Expectation: {record['expectation']}",
        f"- Status: **{record['status']}**",
    ]
    if record["status"] == "ok":
        d = record["detected_fraction"]
        b = record["best_match_share"]
        lines += [
            (
                f"- AOI: {record['aoi_shape_bands_lines_samples']} (bands, lines, samples) "
                f"from full {record['full_cube_shape_bands_lines_samples']}; "
                f"real CRS: {record['aoi_has_real_crs']}"
            ),
            (
                f"- Valid pixels: {record['n_valid_pixels']} at threshold "
                f"{record['threshold_rad']} rad"
            ),
            "",
            "| mineral | detected fraction | best-match share | bands used |",
            "|---|---|---|---|",
        ]
        for m in ("carbonate", "olivine", "clay"):
            lines.append(
                f"| {m} | {d[m]:.3f} | {b[m]:.3f} | {record['bands_used'][m]} |"
            )
        lines += ["", f"**Defensible: {record['defensible']}**", ""]
        for k, v in record["checks"].items():
            lines.append(f"- {'✅' if v else '❌'} {k}")
        lines += [
            "",
            (
                "> Detection depends on the operator threshold and on the ratioed-MICA "
                "vs. unratioed-scene caveat recorded in each run's provenance. These are "
                "spectral *candidates*, not confirmed deposits; the gate checks that the "
                "method is non-degenerate, discriminating, and consistent with the "
                "published gross mineralogy — not that any pixel is ground-truth confirmed."
            ),
        ]
    else:
        lines.append(f"- Reason: {record.get('reason')}")
    (EVIDENCE / "validation_aoi.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())

