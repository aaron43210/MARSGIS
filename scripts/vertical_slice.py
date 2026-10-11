#!/usr/bin/env python3
"""Vertical-slice evidence writer (Milestone A).

Runs the offline slice — A1 tiling math + A2 real-cube SAM + spatial-correctness
transform + reproducibility — and records the result to
``docs/evidence/vertical_slice.{json,md}``. The automated gate is
``engine/tests/test_vertical_slice.py``; this script produces the committed
artifact and prints the lon/lat the candidate map actually landed on.

Run:  python scripts/vertical_slice.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
EVIDENCE = ROOT / "docs" / "evidence"

OBSERVATION_ID = "frt00003e12"
BBOX_WSEN = (76.9404, 22.1347, 77.2127, 22.3863)
MARS_GEOGRAPHIC = "+proj=longlat +R=3396190 +no_defs"
_CUBE = ROOT / "engine" / "tests" / "fixtures" / "real_mtrdr_subset" / f"{OBSERVATION_ID}_subset.img"


def main() -> int:
    from verify_trek import check_math, tile_grid

    record: dict[str, Any] = {
        "gate": "vertical-slice",
        "observation": OBSERVATION_ID,
        "bbox_lonlat_wsen": list(BBOX_WSEN),
    }

    # A1 leg -------------------------------------------------------------
    math_checks = check_math()
    record["a1_tiling_math_ok"] = all(c["ok"] for c in math_checks) and tile_grid(0) == (2, 1)

    if not _CUBE.exists():
        record.update(status="incomplete", reason=f"real fixture absent: {_CUBE}")
        return _finish(record, 2)

    import numpy as np
    import rasterio
    from marsgis_engine import RunParams, run_sam
    from rasterio.warp import transform_bounds

    # A2 + spatial correctness ------------------------------------------
    out = Path(tempfile.mkdtemp())
    res = run_sam(
        str(_CUBE), "carbonate",
        RunParams(out_dir=str(out), timestamp="placeholder", block_rows=8),
    )
    rec = json.loads(Path(res.provenance_path).read_text())
    with rasterio.open(res.candidate_path) as ds:
        w, s, e, n = transform_bounds(ds.crs, MARS_GEOGRAPHIC, *ds.bounds)
        angle1_path = res.angle_path
        projected = bool(ds.crs is not None and not ds.crs.is_geographic)

    cx, cy = (w + e) / 2, (s + n) / 2
    bw, bs, be, bn = BBOX_WSEN
    inside = bw <= cx <= be and bs <= cy <= bn

    # Reproducibility ----------------------------------------------------
    out2 = Path(tempfile.mkdtemp())
    res2 = run_sam(
        str(_CUBE), "carbonate",
        RunParams(out_dir=str(out2), timestamp="placeholder", block_rows=8),
    )
    with rasterio.open(angle1_path) as a, rasterio.open(res2.angle_path) as b:
        reproducible = bool(np.allclose(a.read(1), b.read(1), equal_nan=True))

    record.update(
        status="ok",
        a2_real_cube_bands=rec["inputs"]["cube"]["n_bands"],
        a2_bands_used=rec["wavelength_alignment"]["n_bands_used"],
        a2_crs_is_fallback=rec["inputs"]["cube"]["crs_is_fallback"],
        candidate_crs_projected=projected,
        candidate_center_lonlat=[round(cx, 4), round(cy, 4)],
        candidate_bounds_lonlat_wsen=[round(w, 4), round(s, 4), round(e, 4), round(n, 4)],
        spatial_correct_center_in_bbox=inside,
        reproducible=reproducible,
        detected_fraction=round(rec["results"]["candidate_fraction"], 4),
        note=(
            "Detection fraction is not a correctness signal on a tiny uniform AOI; "
            "the gate is valid, correctly-placed, reproducible output on real data."
        ),
    )
    ok = record["a1_tiling_math_ok"] and inside and reproducible and projected
    return _finish(record, 0 if ok else 1)


def _finish(record: dict[str, Any], code: int) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "vertical_slice.json").write_text(json.dumps(record, indent=2) + "\n")
    _write_md(record)
    print(f"[slice] status={record['status']} a1_math={record.get('a1_tiling_math_ok')}")
    if record["status"] == "ok":
        print(f"   candidate centre {record['candidate_center_lonlat']} "
              f"in bbox={record['spatial_correct_center_in_bbox']} "
              f"reproducible={record['reproducible']}")
    print(f"[slice] evidence -> {EVIDENCE / 'vertical_slice.json'}")
    return code


def _write_md(record: dict[str, Any]) -> None:
    lines = [
        "# Vertical slice — Milestone A",
        "",
        f"- Observation: `{record['observation']}`  bbox: {record['bbox_lonlat_wsen']}",
        f"- A1 tiling math: **{record.get('a1_tiling_math_ok')}**",
        f"- Status: **{record['status']}**",
    ]
    if record["status"] == "ok":
        lines += [
            (
                f"- A2 real cube: {record['a2_real_cube_bands']} bands, "
                f"{record['a2_bands_used']} used, crs_fallback={record['a2_crs_is_fallback']}"
            ),
            (
                f"- Candidate centre (lon,lat): **{record['candidate_center_lonlat']}** — "
                f"inside footprint: **{record['spatial_correct_center_in_bbox']}**"
            ),
            f"- Reproducible: **{record['reproducible']}**",
            "",
            f"> {record['note']}",
        ]
    else:
        lines.append(f"- Reason: {record.get('reason')}")
    (EVIDENCE / "vertical_slice.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
