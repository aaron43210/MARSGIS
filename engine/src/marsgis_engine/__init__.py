"""MarsGIS science engine — standalone, reproducible SAM pipeline.

Turns an analysis-ready CRISM MTRDR cube (ENVI ``.img``/``.hdr``, already
calibrated + map-projected) plus a MICA reference spectrum into a float32
spectral-angle raster and a thresholded *candidate-match* mask, both written as
Cloud-Optimized GeoTIFFs that preserve the input Mars CRS/affine, accompanied by
a machine-readable provenance JSON and a human-readable report.

Contract: the engine performs NO radiometric re-calibration and NO
reprojection. MTRDR is analysis-ready I/F, so outputs inherit the input grid
losslessly; tiling / reprojection is the backend / frontend concern.

Scientific honesty: a thresholded match is a *candidate*, never a confirmed
deposit. The continuous angle raster is always retained alongside the mask.

Public API (imported by the backend):

    from marsgis_engine import (
        __version__,
        run_sam, RunParams, SamResult,
        load_cube, CrismCube,
        load_reference, Reference,
    )
"""

from __future__ import annotations

from ._version import __version__
from .io.envi_reader import CrismCube, load_cube
from .io.reference import Reference, load_reference
from .science.pipeline import RunParams, SamResult, run_sam

__all__ = [
    "__version__",
    "run_sam",
    "RunParams",
    "SamResult",
    "load_cube",
    "CrismCube",
    "load_reference",
    "Reference",
]
