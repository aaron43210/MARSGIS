"""Generate tiny synthetic ENVI cubes + reference tables for offline tests.

TEST-ONLY — never shipped in the wheel. Produces a *fake* hyperspectral cube
mimicking a CRISM MTRDR I/F cube (ENVI BSQ float32, per-band wavelengths in the
.hdr) so the engine and its tests run with ZERO network access.

It is NOT real Mars data. "Carbonate" pixels are planted equal to the synthetic
reference end-member so SAM yields a deterministic angle of ~0 there; never
present a match against this cube as a real detection.

The ENVI header is written by hand (mirroring the verified-working
``sample_crism_nili.hdr`` format) rather than via ``spectral.envi.save_image``,
so the exact header fields — ``bbl``, ``data ignore value``,
``coordinate system string`` — are under full test control.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from marsgis_engine import config

DEFAULT_N_BANDS = 24
DEFAULT_WL_MIN_NM = 1000.0
DEFAULT_WL_MAX_NM = 2600.0
IGNORE_VALUE = config.DEFAULT_IGNORE_VALUE  # 65535.0

# A Mars-2000 equirectangular WKT the ENVI 'coordinate system string' carries so
# GDAL/rasterio can resolve a real (non-fallback) CRS in tests that opt in.
TEST_CRS_WKT = config.MARS2000_EQUIRECT_WKT


def wavelengths_nm(n_bands: int = DEFAULT_N_BANDS) -> np.ndarray:
    return np.linspace(DEFAULT_WL_MIN_NM, DEFAULT_WL_MAX_NM, n_bands)


def _gauss(wl_nm: np.ndarray, center_nm: float, depth: float, width_nm: float) -> np.ndarray:
    return depth * np.exp(-0.5 * ((wl_nm - center_nm) / width_nm) ** 2)


def carbonate_spectrum(wl_nm: np.ndarray) -> np.ndarray:
    """Synthetic carbonate: strong 2.31 / 2.51 um doublet on a mild slope.

    Features are deliberately deep so SAM cleanly separates planted carbonate
    pixels from the olivine-like background (robust margin vs the 0.10 rad
    default threshold), independent of continuum removal.
    """
    cont = 1.0 + 3e-5 * (wl_nm - wl_nm.mean())
    return cont - _gauss(wl_nm, 2310.0, 0.50, 45.0) - _gauss(wl_nm, 2510.0, 0.60, 55.0)


def background_spectrum(wl_nm: np.ndarray) -> np.ndarray:
    """Olivine-like background: broad Fe2+ absorption centred ~1.05 um.

    Spectrally distinct from carbonate (different absorption position), so the
    bland/background pixels sit well above the SAM threshold.
    """
    cont = 1.0 + 3e-5 * (wl_nm - wl_nm.mean())
    return cont - _gauss(wl_nm, 1050.0, 0.60, 230.0)


@dataclass
class SyntheticCube:
    img_path: Path
    hdr_path: Path
    wl_nm: np.ndarray
    reference_values: np.ndarray
    planted: list[tuple[int, int]]
    ignore_pixels: list[tuple[int, int]]
    bad_bands: list[int]
    rows: int
    cols: int
    include_crs: bool
    extra: dict = field(default_factory=dict)


def make_synthetic_cube(
    out_dir: str | Path,
    *,
    basename: str = "synthetic_cube",
    rows: int = 8,
    cols: int = 8,
    n_bands: int = DEFAULT_N_BANDS,
    planted: Sequence[tuple[int, int]] | None = None,
    ignore_pixels: Sequence[tuple[int, int]] | None = None,
    bad_bands: Sequence[int] | None = None,
    include_crs: bool = True,
    seed: int = 0,
) -> SyntheticCube:
    """Write a tiny synthetic ENVI cube and return its description.

    Planted pixels are set EXACTLY to the carbonate reference end-member, so a
    SAM run against the matching reference yields angle ~0 (< any sane
    threshold) at those coordinates and large angles on the bland background.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    wl = wavelengths_nm(n_bands)
    carb = carbonate_spectrum(wl)
    bg = background_spectrum(wl)

    if planted is None:
        planted = [(1, 1), (1, 2), (2, 1), (2, 2)]
    if ignore_pixels is None:
        ignore_pixels = [(rows - 1, cols - 1)]
    if bad_bands is None:
        # Mark two interior bands bad (ENVI bbl 0); must not break overlap.
        bad_bands = [5, 6]

    planted = [(int(r), int(c)) for r, c in planted]
    ignore_pixels = [(int(r), int(c)) for r, c in ignore_pixels]
    bad_bands = [int(b) for b in bad_bands]

    # Background everywhere + small multiplicative albedo + additive noise.
    cube = np.tile(bg, (rows, cols, 1)).astype(np.float64)
    albedo = rng.uniform(0.9, 1.1, size=(rows, cols, 1))
    cube *= albedo
    cube += rng.normal(0.0, 0.002, size=cube.shape)

    # Plant carbonate pixels EXACTLY equal to the reference (angle -> 0).
    for r, c in planted:
        cube[r, c, :] = carb

    # A few ignore-value pixels (CRISM gaps).
    for r, c in ignore_pixels:
        cube[r, c, :] = IGNORE_VALUE

    cube = cube.astype("<f4")

    img_path = out_dir / f"{basename}.img"
    hdr_path = out_dir / f"{basename}.hdr"
    _write_envi_bsq(img_path, cube)
    _write_envi_header(
        hdr_path,
        rows=rows,
        cols=cols,
        n_bands=n_bands,
        wl_nm=wl,
        bad_bands=bad_bands,
        include_crs=include_crs,
    )

    return SyntheticCube(
        img_path=img_path,
        hdr_path=hdr_path,
        wl_nm=wl,
        reference_values=carb,
        planted=planted,
        ignore_pixels=ignore_pixels,
        bad_bands=bad_bands,
        rows=rows,
        cols=cols,
        include_crs=include_crs,
    )


def _write_envi_bsq(img_path: Path, cube: np.ndarray) -> None:
    """Write a (rows, cols, bands) float32 cube as band-sequential (BSQ)."""
    rows, cols, bands = cube.shape
    with open(img_path, "wb") as fh:
        for b in range(bands):
            fh.write(np.ascontiguousarray(cube[:, :, b], dtype="<f4").tobytes())


def _write_envi_header(
    hdr_path: Path,
    *,
    rows: int,
    cols: int,
    n_bands: int,
    wl_nm: np.ndarray,
    bad_bands: Sequence[int],
    include_crs: bool,
) -> None:
    wl_str = ",\n ".join(f"{w:.6f}" for w in wl_nm)
    bbl = ["1"] * n_bands
    for b in bad_bands:
        if 0 <= b < n_bands:
            bbl[b] = "0"
    bbl_str = ", ".join(bbl)

    header = [
        "ENVI",
        "description = {",
        "  SYNTHETIC CRISM-like cube for MarsGIS offline tests. Not real data.}",
        f"samples = {cols}",
        f"lines   = {rows}",
        f"bands   = {n_bands}",
        "header offset = 0",
        "file type = ENVI Standard",
        "data type = 4",
        "interleave = bsq",
        "sensor type = Unknown",
        "byte order = 0",
        f"data ignore value = {IGNORE_VALUE:.8e}",
        "wavelength units = Nanometers",
    ]
    if include_crs:
        # Full georeferencing: ENVI map info + an explicit coordinate system
        # string (WKT) so GDAL/rasterio resolves a real, non-fallback CRS.
        header.append(
            "map info = {Equirectangular, 1.0, 1.0, 4282604.7, 1326018.0, "
            "1800.0, 1800.0, D_Mars_2000_Sphere, units=Meters}"
        )
        header.append("coordinate system string = {" + TEST_CRS_WKT + "}")
    header.append("bbl = {" + bbl_str + "}")
    header.append("wavelength = {\n " + wl_str + "}")
    hdr_path.write_text("\n".join(header) + "\n")


def make_synthetic_reference(
    path: str | Path,
    wl_nm: np.ndarray,
    values: np.ndarray,
    *,
    units: str = "um",
    header: bool = True,
) -> Path:
    """Write a 2-column ASCII reference (.tab/.csv): wavelength, value.

    ``units='um'`` writes wavelengths in micrometres (like a real MICA .tab),
    exercising the engine's um->nm conversion.
    """
    path = Path(path)
    scale = 1.0 / 1000.0 if units == "um" else 1.0
    lines: list[str] = []
    if header:
        lines.append("# SYNTHETIC reference spectrum for MarsGIS offline tests. Not real.")
        lines.append(f"# columns: wavelength_{units}, value")
    for w, v in zip(wl_nm, values, strict=False):
        lines.append(f"{w * scale:.6f}, {v:.6f}")
    path.write_text("\n".join(lines) + "\n")
    return path
