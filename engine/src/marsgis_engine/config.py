"""Central defaults and constants for the MarsGIS science engine.

This module performs NO I/O at import time beyond resolving the paths of
bundled package data via :mod:`importlib.resources`. Every tunable the
pipeline, CLI, and writers rely on lives here so there is a single place to
audit scientific defaults.

The SAM defaults MUST stay in lockstep with the frozen shared contract
``contracts/enums.json`` (``defaults.sam``): threshold 0.10 rad,
continuum_removed = false (raw spectral angle; continuum removal is an opt-in
band-shape enhancement), wavelength subset 1000-2600 nm.
"""

from __future__ import annotations

import math
from importlib import resources
from pathlib import Path

# --- SAM scientific defaults (mirror contracts/enums.json -> defaults.sam) ---
DEFAULT_THRESHOLD_RAD: float = 0.10
#: Diagnostic IR window (nm). Nili Fossae carbonate 2.3/2.5 um doublet,
#: olivine broad ~1 um, Fe/Mg-smectite 1.9/2.3 um all fall inside this range.
DEFAULT_WINDOW_NM: tuple[float, float] = (1000.0, 2600.0)
#: Shared-contract default for continuum removal (enums.json: false). SAM is
#: already albedo-scale invariant, so raw spectral angle is the default and
#: convex-hull continuum removal is an opt-in band-shape enhancement.
DEFAULT_CONTINUUM_REMOVAL: bool = False
#: Minimum number of overlapping good bands before a match is meaningful.
MIN_OVERLAP_BANDS: int = 10
#: Default reference-resampling method.
DEFAULT_RESAMPLE: str = "linear"
#: Mask ENVI bad bands (bbl == 0) by default.
DEFAULT_MASK_BAD_BANDS: bool = True

# --- Nodata conventions for the two output rasters -------------------------
#: Candidate mask nodata value (uint8). Valid values: 0 non-match, 1 candidate.
CANDIDATE_NODATA: int = 255
CANDIDATE_MATCH: int = 1
CANDIDATE_NON_MATCH: int = 0
#: Angle raster nodata (float32). NaN keeps the continuous raster honest about
#: where no computation was possible.
ANGLE_NODATA: float = float("nan")

# --- CRISM / ENVI conventions ----------------------------------------------
#: CRISM MTRDR "data ignore value"; also appears as ENVI "data ignore value".
DEFAULT_IGNORE_VALUE: float = 65535.0

# --- Row-block chunking (bounds peak memory for ~450-band cubes) ------------
DEFAULT_BLOCK_ROWS: int = 64

# --- Output filename suffixes (stable artifact contract) -------------------
ANGLE_SUFFIX: str = "_SAM_angle.tif"
CANDIDATE_SUFFIX: str = "_SAM_candidate.tif"
PROVENANCE_SUFFIX: str = "_provenance.json"
REPORT_SUFFIX: str = "_report.txt"
DEFAULT_OUT_PREFIX: str = "result"

#: Timestamp placeholder accepted by ``--timestamp`` for byte-reproducible
#: test / golden-file outputs. When supplied, this exact string is embedded.
TIMESTAMP_PLACEHOLDER: str = "1970-01-01T00:00:00Z"

#: Provenance schema version emitted in every provenance.json.
PROVENANCE_SCHEMA_VERSION: str = "1.0.0"

#: Single scientific-honesty disclaimer embedded in provenance + report.
#: Mirrors contracts/enums.json -> caveats.candidate_match in spirit.
CANDIDATE_DISCLAIMER: str = (
    "A SAM candidate match (spectral angle below the operator-chosen "
    "threshold) is NOT a confirmed mineral deposit. It indicates spectral "
    "similarity to a reference end-member and requires expert spectral review "
    "and corroborating observations before any geologic claim."
)

#: Machine-readable scientific-honesty caveat about the reference/scene
#: preprocessing mismatch. MICA type spectra are RATIOED I/F while scene pixels
#: are un-ratioed I/F. Wavelength resampling aligns the band grids only -- it
#: does NOT reconcile the ratioed-vs-unratioed difference. Surfaced in
#: provenance (not only the human report) so API consumers and contract tests
#: can assert its presence.
PREPROCESSING_CAVEAT: str = (
    "MICA reference spectra are ratioed I/F; scene pixels are un-ratioed I/F. "
    "Resampling aligns the wavelength grids only -- it does not reconcile the "
    "ratioed-vs-unratioed difference. SAM is albedo-scale invariant and "
    "continuum removal (when enabled) mitigates band-shape mismatch, but the "
    "difference is not fully eliminated; treat matches as spectral candidates."
)

# ---------------------------------------------------------------------------
# Mars 2000 equirectangular FALLBACK WKT.
#
# ASSUMED, NOT authoritative. Used ONLY when the ENVI header carries no
# resolvable CRS (see io.envi_reader). The ENVI header 'map info' /
# 'coordinate system string' is always the source of truth; this fallback keeps
# an output georeferenced (never CRS-less) and the assumption is logged at
# WARNING and recorded as crs_is_fallback=true in provenance.
#
# Sphere: Mars 2000, semimajor = semiminor = 3,396,190 m (IAU 2000 mean radius),
# clon = 0 to match the NASA Trek EQ equirectangular basemaps.
# ---------------------------------------------------------------------------
MARS2000_EQUIRECT_WKT: str = (
    'PROJCS["Mars_2000_Equirectangular_clon0",'
    'GEOGCS["Mars_2000",'
    'DATUM["D_Mars_2000",'
    'SPHEROID["Mars_2000_Sphere",3396190.0,0.0]],'
    'PRIMEM["Reference_Meridian",0.0],'
    'UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Equirectangular"],'
    'PARAMETER["standard_parallel_1",0.0],'
    'PARAMETER["central_meridian",0.0],'
    'PARAMETER["false_easting",0.0],'
    'PARAMETER["false_northing",0.0],'
    'UNIT["metre",1.0]]'
)

# --- COG write profile ------------------------------------------------------
#: Base GDAL COG-driver creation options. Per-dtype predictor/overrides are
#: applied by io.raster_writer (float32 -> predictor 3, integer -> predictor 2).
COG_PROFILE: dict[str, object] = {
    "driver": "COG",
    "compress": "DEFLATE",
    "blocksize": 512,
    "overview_resampling": "nearest",
    "bigtiff": "IF_SAFER",
}

#: Max radians == 90 deg; a SAM angle can never exceed pi/2 for non-negative
#: spectra but we clamp thresholds to this physical ceiling.
MAX_ANGLE_RAD: float = math.pi / 2.0


def _package_data_dir() -> Path:
    """Return the on-disk path of the bundled ``data`` directory."""
    return Path(str(resources.files("marsgis_engine") / "data"))


def mineral_data_path() -> Path:
    """Absolute path to the bundled ``data/minerals.json`` alias map."""
    return _package_data_dir() / "minerals.json"


def mica_dir() -> Path:
    """Absolute path to the bundled ``data/mica`` reference directory."""
    return _package_data_dir() / "mica"
