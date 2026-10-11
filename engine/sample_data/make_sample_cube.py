#!/usr/bin/env python3
"""Generate a tiny, synthetic CRISM-like ENVI cube for offline pipeline + CI.

This produces a *fake* hyperspectral cube that mimics the structure of a real
CRISM MTRDR I/F cube (ENVI BSQ, float32, per-band wavelengths in the .hdr) so
the MarsGIS science engine and its tests can run with ZERO network access and
without bundling any large/real PDS archive products.

It is NOT real Mars data. The embedded "carbonate" and "olivine" signatures are
hand-built absorption models placed in known pixel regions purely so the SAM
pipeline has a deterministic, checkable answer. Never present a match against
this cube as a real mineral detection.

Real counterpart (fetch at runtime via the data-access layer, do not vendor):
  CRISM MTRDR I/F cube  : <obsid>_07_if###j_mtr3.img/.hdr  (ENVI, float32, bands~489)
  MICA carbonate ref    : crism_typespec_fe_ca_carbonate.tab  (ASCII, um vs ratioed I/F)

Usage (sandbox-safe, no implicit cwd imports):
  python3 -I make_sample_cube.py --out .            # writes alongside this file
  python3 -I make_sample_cube.py --out /tmp/foo --lines 48 --samples 48

Outputs (into --out):
  sample_crism_nili.img   raw BSQ float32 little-endian cube
  sample_crism_nili.hdr   ENVI header (wavelengths, data ignore value, map info)
  carbonate_reference.csv  synthetic carbonate end-member on the SAME grid (SAM ref)
  sample_truth.json        pixel-region ground truth for test assertions

Dependencies: numpy only (installed in the engine image).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# --- Wavelength grid (micrometres) -----------------------------------------
# A compact 60-band grid over the CRISM IR range that carries the diagnostic
# features we care about: olivine's broad ~1.05 um drop and the carbonate
# 2.31 / 2.51 um doublet. Real MTRDR has ~489 bands 0.36-3.92 um; we subset.
WL_MIN_UM = 1.00
WL_MAX_UM = 2.60
N_BANDS = 60

DATA_IGNORE = 65535.0  # matches CRISM MTRDR "data ignore value"

# Proper Mars 2000 EQUIRECTANGULAR (meters, clon=0) CRS as a WKT, written into
# the ENVI header's `coordinate system string` so GDAL parses a real projected
# CRS (not an "EngineeringCRS") and the backend can warp the result COG onto the
# Mars geographic tile grid. Mirrors MARS2000_EQUIRECT_WKT in the engine/backend.
EQUIRECT_WKT = (
    'PROJCS["Mars_2000_Equidistant_Cylindrical",'
    'GEOGCS["Mars_2000",DATUM["D_Mars_2000",'
    'SPHEROID["Mars_2000_IAU_IAG",3396190.0,0.0]],'
    'PRIMEM["Reference_Meridian",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Equirectangular"],'
    'PARAMETER["standard_parallel_1",0.0],'
    'PARAMETER["central_meridian",0.0],'
    'PARAMETER["false_easting",0.0],'
    'PARAMETER["false_northing",0.0],'
    'UNIT["Meter",1.0]]'
)
# Top-left origin (meters) placing the ~1.46-deg-wide scene inside the Nili
# Fossae bbox (74-78 E, 20-24 N). 1 deg ~= 59274 m on the Mars 2000 sphere.
MAP_ORIGIN_EASTING_M = 4445550.0  # ~75.0 E
MAP_ORIGIN_NORTHING_M = 1345520.0  # ~22.7 N
MAP_PIXEL_M = 1800.0


def wavelengths_um() -> np.ndarray:
    return np.linspace(WL_MIN_UM, WL_MAX_UM, N_BANDS)


def _gaussian_band(wl: np.ndarray, center: float, depth: float, width: float) -> np.ndarray:
    """A single absorption band: subtracts a Gaussian notch from continuum 1.0."""
    return depth * np.exp(-0.5 * ((wl - center) / width) ** 2)


#: Bundled real CRISM MICA type spectra (PDS public domain) used to shape the
#: planted carbonate/olivine regions, so a SAM run against the SAME bundled MICA
#: reference localises to those regions instead of matching the whole scene. The
#: SCENE is still synthetic; only the end-member spectral SHAPES are real MICA.
MICA_DIR = Path(__file__).resolve().parent.parent / "src" / "marsgis_engine" / "data" / "mica"
_MICA_FILE = {
    "carbonate": "crism_typespec_mg_carbonate.tab",
    "olivine": "crism_typespec_mg_olivine.tab",
}


def _load_mica_resampled(kind: str, wl_um: np.ndarray) -> np.ndarray:
    """Load a bundled MICA .tab (col0=wavelength um, col1=ratioed I/F) and
    resample its ratioed I/F onto the cube's wavelength grid (edge-hold)."""
    path = MICA_DIR / _MICA_FILE[kind]
    w_list: list[float] = []
    v_list: list[float] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s[0] in "#;":
            continue
        parts = s.replace(",", " ").split()
        try:
            w, v = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            continue
        w_list.append(w)
        v_list.append(v)
    order = np.argsort(w_list)
    mw = np.asarray(w_list, dtype=float)[order]
    mv = np.asarray(v_list, dtype=float)[order]
    return np.interp(wl_um, mw, mv)


def endmember(wl: np.ndarray, kind: str) -> np.ndarray:
    """Return a ratioed-I/F end-member spectrum on the cube grid.

    ``carbonate``/``olivine`` are the REAL bundled MICA type spectra (resampled
    onto this grid), so a SAM run with the matching MICA reference localises to
    the planted region rather than flagging the whole scene. ``background`` is a
    spectrally bland synthetic continuum with no diagnostic absorptions.
    """
    if kind in _MICA_FILE:
        return _load_mica_resampled(kind, wl)
    if kind == "background":
        cont = 1.0 + 0.03 * (wl - wl.mean())  # mild spectral slope, no sharp bands
        return cont - _gaussian_band(wl, 2.0, 0.02, 0.4)
    raise ValueError(f"unknown endmember: {kind}")


def build_cube(lines: int, samples: int, seed: int):
    rng = np.random.default_rng(seed)
    wl = wavelengths_um()
    bg = endmember(wl, "background")
    carb = endmember(wl, "carbonate")
    oliv = endmember(wl, "olivine")

    # cube shape (lines, samples, bands); fill with background + noise.
    cube = np.tile(bg, (lines, samples, 1)).astype(np.float64)

    # Carbonate patch: upper-left quadrant block.
    cr0, cr1 = int(lines * 0.15), int(lines * 0.40)
    cc0, cc1 = int(samples * 0.15), int(samples * 0.40)
    cube[cr0:cr1, cc0:cc1, :] = carb

    # Olivine patch: lower-right quadrant block.
    orr0, orr1 = int(lines * 0.60), int(lines * 0.85)
    oc0, oc1 = int(samples * 0.60), int(samples * 0.85)
    cube[orr0:orr1, oc0:oc1, :] = oliv

    # Add small per-pixel multiplicative albedo variation + additive noise so
    # the scene is not perfectly uniform (exercises ratioing/normalisation).
    albedo = rng.uniform(0.9, 1.1, size=(lines, samples, 1))
    cube *= albedo
    cube += rng.normal(0.0, 0.004, size=cube.shape)

    # Mark a few "bad" pixels with the ignore value (like real CRISM gaps).
    for _ in range(max(1, (lines * samples) // 200)):
        r = int(rng.integers(0, lines))
        c = int(rng.integers(0, samples))
        cube[r, c, :] = DATA_IGNORE

    truth = {
        "wavelength_units": "micrometers",
        "n_bands": int(N_BANDS),
        "carbonate_region": {"line": [cr0, cr1], "sample": [cc0, cc1]},
        "olivine_region": {"line": [orr0, orr1], "sample": [oc0, oc1]},
        "background": "everywhere else",
        "data_ignore_value": DATA_IGNORE,
        "note": (
            "SYNTHETIC scene for offline pipeline/CI only — NOT real CRISM data. "
            "The carbonate/olivine regions are shaped from the bundled real MICA "
            "type spectra so SAM against the matching MICA reference localises to "
            "them; any match here is still a demo, never a real detection."
        ),
    }
    return cube.astype("<f4"), wl, truth


def write_envi(out: Path, basename: str, cube: np.ndarray, wl: np.ndarray) -> None:
    """Write ENVI BSQ float32 .img + a CRISM-style .hdr next to it."""
    lines, samples, bands = cube.shape
    img_path = out / f"{basename}.img"
    hdr_path = out / f"{basename}.hdr"

    # BSQ = band sequential: all of band 0, then all of band 1, ...
    with open(img_path, "wb") as fh:
        for b in range(bands):
            fh.write(np.ascontiguousarray(cube[:, :, b], dtype="<f4").tobytes())

    wl_str = ",\n ".join(f"{w:.6f}" for w in wl)
    hdr = (
        "ENVI\n"
        "description = {\n"
        "  SYNTHETIC CRISM-like cube for MarsGIS offline tests. Not real data.}\n"
        f"samples = {samples}\n"
        f"lines   = {lines}\n"
        f"bands   = {bands}\n"
        "header offset = 0\n"
        "file type = ENVI Standard\n"
        "data type = 4\n"  # 4 = 32-bit float
        "interleave = bsq\n"
        "sensor type = Unknown\n"
        "byte order = 0\n"  # 0 = little-endian
        f"data ignore value = {DATA_IGNORE:.8e}\n"
        "wavelength units = Micrometers\n"
        # Equirectangular (clon=0) geotransform near Nili Fossae; the real CRS
        # is given by the coordinate-system-string WKT below (GDAL prefers it).
        f"map info = {{Equirectangular, 1.0, 1.0, {MAP_ORIGIN_EASTING_M}, "
        f"{MAP_ORIGIN_NORTHING_M}, {MAP_PIXEL_M}, {MAP_PIXEL_M}, "
        "Mars_2000, units=Meters}\n"
        f"coordinate system string = {{{EQUIRECT_WKT}}}\n"
        "wavelength = {\n "
        f"{wl_str}}}\n"
    )
    hdr_path.write_text(hdr)


def write_reference_csv(out: Path, wl: np.ndarray) -> None:
    """Synthetic carbonate end-member on the cube's grid, for SAM matching.

    Mirrors the two columns the engine needs from a real MICA .tab:
    wavelength (um) and ratioed I/F. Header row documents provenance.
    """
    carb = endmember(wl, "carbonate")
    lines = [
        "# Carbonate reference spectrum for MarsGIS offline CI, resampled from the",
        "# bundled real CRISM MICA mg_carbonate type spectrum onto this cube's grid.",
        "# The engine normally loads MICA directly via `--mineral carbonate`; this CSV",
        "# mirrors it for the `--reference` path. Full MICA library (production):",
        "#   https://pds-geosciences.wustl.edu/mro/mro-m-crism-4-typespec-v1/"
        "mrocr_8001/data/crism_typespec_mg_carbonate.tab",
        "# columns: wavelength_um,ratioed_if",
        "wavelength_um,ratioed_if",
    ]
    lines += [f"{w:.6f},{r:.6f}" for w, r in zip(wl, carb, strict=False)]
    (out / "carbonate_reference.csv").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent),
        help="output directory (default: this script's directory)",
    )
    ap.add_argument("--basename", default="sample_crism_nili")
    ap.add_argument("--lines", type=int, default=48)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    cube, wl, truth = build_cube(args.lines, args.samples, args.seed)
    write_envi(out, args.basename, cube, wl)
    write_reference_csv(out, wl)
    (out / "sample_truth.json").write_text(json.dumps(truth, indent=2) + "\n")

    img = out / f"{args.basename}.img"
    print(
        f"wrote {img}  ({img.stat().st_size} bytes, "
        f"{cube.shape[0]}x{cube.shape[1]}x{cube.shape[2]} bsq float32)"
    )
    print(f"wrote {out / (args.basename + '.hdr')}")
    print(f"wrote {out / 'carbonate_reference.csv'}")
    print(f"wrote {out / 'sample_truth.json'}")


if __name__ == "__main__":
    main()
