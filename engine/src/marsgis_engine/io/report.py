"""Render a human-readable plain-text report from a provenance record.

Single source of truth: everything here is formatted from the provenance dict,
so the report and the JSON can never disagree. The report ends with a bold-caps
scientific disclaimer that a candidate SAM match is NOT a confirmed deposit.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..errors import WriteError


def _deg(rad: Any) -> str:
    if rad is None:
        return "n/a"
    try:
        return f"{math.degrees(float(rad)):.4f} deg"
    except (TypeError, ValueError):
        return "n/a"


def _rad(rad: Any) -> str:
    if rad is None:
        return "n/a"
    try:
        return f"{float(rad):.6f} rad"
    except (TypeError, ValueError):
        return "n/a"


def render_report(record: dict[str, Any]) -> str:
    inp = record.get("inputs", {})
    cube = inp.get("cube", {})
    ref = inp.get("reference", {})
    par = record.get("parameters", {})
    res = record.get("results", {})
    env = record.get("environment", {})
    out = record.get("outputs", {})

    window = par.get("wavelength_window_nm", [None, None])
    lines: list[str] = []
    add = lines.append

    add("=" * 72)
    add("MarsGIS science engine - SAM candidate-match report")
    add("=" * 72)
    add(
        f"Software           : {record.get('software', {}).get('name')} "
        f"v{record.get('software', {}).get('version')}"
    )
    add(f"Algorithm          : {record.get('algorithm')}")
    add(f"Created (UTC)       : {record.get('created_utc')}")
    add("")

    add("-- Observation (input cube) " + "-" * 44)
    add(f"  Label / product id : {cube.get('label_id')}")
    add(f"  File               : {cube.get('path')}")
    add(f"  Shape (r,c,b)      : {cube.get('shape')}")
    add(f"  Bands (total/good) : {cube.get('n_bands')} / {cube.get('n_good_bands')}")
    add(f"  Data ignore value  : {cube.get('ignore_value')}")
    add(
        f"  CRS is fallback    : {cube.get('crs_is_fallback')}  "
        f"(ASSUMED Mars-2000 equirectangular if true)"
    )
    add(f"  SHA-256            : {cube.get('sha256')}")
    add("")

    add("-- Reference spectrum (MICA) " + "-" * 43)
    add(f"  Name / phase       : {ref.get('name')}  ({ref.get('mica_key')})")
    add(f"  Source             : {ref.get('source')}")
    add(f"  Points             : {ref.get('n_points')}  (units: {ref.get('units_original')})")
    add(f"  SHA-256            : {ref.get('sha256')}")
    add("  NOTE: MICA type spectra are RATIOED I/F; scene pixels are un-ratioed")
    add("        I/F. SAM is albedo-invariant and (optional) continuum removal")
    add("        mitigates the mismatch, but it is not fully eliminated.")
    add("")

    add("-- Method & parameters " + "-" * 49)
    add(f"  Threshold          : {_rad(par.get('threshold'))}  ({_deg(par.get('threshold'))})")
    add(f"  Wavelength window  : {window[0]} - {window[1]} nm")
    add(f"  Bands used         : {par.get('bands_used')}")
    add(f"  Mask bad bands     : {par.get('mask_bad_bands')}")
    add(f"  Continuum removal  : {par.get('continuum_removal')}")
    add(f"  Resample method    : {par.get('resample_method')}")
    add("")

    add("-- Results " + "-" * 61)
    n_pix = res.get("n_pixels", 0)
    n_valid = res.get("n_valid_pixels", 0)
    n_cand = res.get("n_candidate_pixels", 0)
    frac = res.get("candidate_fraction", 0.0) or 0.0
    add(f"  Pixels (total)     : {n_pix}")
    add(f"  Valid pixels       : {n_valid}")
    add(f"  Candidate pixels   : {n_cand}  ({frac * 100.0:.3f}% of valid)")
    add(f"  Angle min          : {_rad(res.get('angle_min'))}  ({_deg(res.get('angle_min'))})")
    add(
        f"  Angle median (all) : {_rad(res.get('angle_median'))}  ({_deg(res.get('angle_median'))})"
    )
    add(
        f"  Angle median (cand): {_rad(res.get('angle_median_candidates'))}  "
        f"({_deg(res.get('angle_median_candidates'))})"
    )
    add("")

    add("-- Output files " + "-" * 57)
    for role, meta in out.items():
        add(f"  {role:18s} : {meta.get('file')}  ({meta.get('size_bytes')} bytes)")
        add(f"  {'':18s}   sha256={meta.get('sha256')}")
    add("")

    add("-- Environment " + "-" * 58)
    add(f"  python={env.get('python')} numpy={env.get('numpy')} scipy={env.get('scipy')}")
    add(f"  rasterio={env.get('rasterio')} spectral={env.get('spectral')} gdal={env.get('gdal')}")
    add(f"  platform={env.get('platform')}")
    add("")

    add("*" * 72)
    add("SCIENTIFIC DISCLAIMER")
    add("*" * 72)
    disclaimer = record.get("disclaimer", "")
    for chunk in _wrap(disclaimer, 70):
        add("  " + chunk)
    add("")
    add("  A CANDIDATE SAM MATCH IS NOT A CONFIRMED MINERAL DEPOSIT.")
    add("  Thresholding is an operator choice, not ground truth. Review the")
    add("  continuous angle raster and seek corroborating observations before")
    add("  any geologic interpretation.")
    add("=" * 72)
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def write_report(path: str | Path, record: dict[str, Any]) -> Path:
    path = Path(path)
    try:
        path.write_text(render_report(record))
    except OSError as exc:
        raise WriteError(f"could not write report {path.name}: {exc}") from exc
    return path
