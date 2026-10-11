"""Mars/CRS constants, Trek grid parameters, and shared limits.

Coordinates throughout MarsGIS are Mars IAU 2000 degrees (east-positive
longitude [-180,180], planetocentric latitude [-90,90]) on the Mars 2000
sphere, NOT Earth WGS84. See contracts/enums.json#crs.
"""

from __future__ import annotations

import os

# Mars data is handled on the Mars 2000 sphere while reusing the OGC
# WorldCRS84Quad geographic tile geometry (the identical 2x1@z0 equirectangular
# degree grid as NASA Trek and Cesium's GeographicTilingScheme). PROJ otherwise
# refuses Mars<->Earth geographic transforms ("different celestial body"); here
# we deliberately treat the angular (degree) grids as equivalent. This must be
# set before pyproj builds any transformer, so it lives at the top of this
# early-imported module.
os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

from app.schemas.enums import CANDIDATE_MATCH_CAVEAT

# --- Mars body (IAU 2000) ---
MARS_RADIUS_M = 3_396_190.0  # equatorial / sphere radius used by Trek + Cesium
MARS_SEMI_MINOR_M = 3_376_200.0  # polar radius (documented; Trek grid is spherical)

#: Human-readable CRS id advertised by NASA Trek WMTS (urn:ogc:def:crs:EPSG::104905).
MARS_CRS_ID = "IAU_2000:49900"
MARS_CRS_CODE = 104905

#: Mars 2000 GEOGRAPHIC CRS (degrees) as ESRI-style WKT on the Mars sphere.
#: Used for the result TileMatrixSet CRS and for reprojecting COG bounds to degrees.
MARS2000_GEOGRAPHIC_WKT = (
    'GEOGCS["Mars_2000",'
    'DATUM["D_Mars_2000",'
    'SPHEROID["Mars_2000_IAU_IAG",3396190.0,0.0]],'
    'PRIMEM["Reference_Meridian",0.0],'
    'UNIT["Degree",0.0174532925199433]]'
)

#: Mars 2000 EQUIRECTANGULAR (meters, clon=0) WKT — the Trek/MTRDR projected grid.
MARS2000_EQUIRECT_WKT = (
    'PROJCS["Mars_2000_Equidistant_Cylindrical",'
    'GEOGCS["Mars_2000",'
    'DATUM["D_Mars_2000",'
    'SPHEROID["Mars_2000_IAU_IAG",3396190.0,0.0]],'
    'PRIMEM["Reference_Meridian",0.0],'
    'UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Equidistant_Cylindrical"],'
    'PARAMETER["standard_parallel_1",0.0],'
    'PARAMETER["central_meridian",0.0],'
    'PARAMETER["false_easting",0.0],'
    'PARAMETER["false_northing",0.0],'
    'UNIT["Meter",1.0]]'
)

# --- Tile grid (matches verified Trek default028mm equirectangular grid) ---
DEFAULT_TILE_SIZE = 256
LEVEL_ZERO_TILES_X = 2
LEVEL_ZERO_TILES_Y = 1
MIN_ZOOM = 0
MAX_ZOOM = 8
NODATA_RGBA = (0, 0, 0, 0)

# Geographic extent of the whole grid in degrees [west, south, east, north].
GEOGRAPHIC_EXTENT = (-180.0, -90.0, 180.0, 90.0)

# --- Default rendering (per contracts/enums.json defaults) ---
SAM_ANGLE_COLORMAP = "magma_r"
MATCH_SCORE_COLORMAP = "viridis"

# --- Regions ---
NILI_FOSSAE_BBOX = (74.0, 20.0, 78.0, 24.0)
REGION_BBOX: dict[str, tuple[float, float, float, float]] = {
    "Nili Fossae": NILI_FOSSAE_BBOX,
}

# --- Scientific disclaimer (single source; mirrors enums.json caveat) ---
DISCLAIMER = CANDIDATE_MATCH_CAVEAT

# --- Engine/provenance identity ---
ENGINE_PACKAGE = "marsgis_engine"

__all__ = [
    "DEFAULT_TILE_SIZE",
    "DISCLAIMER",
    "ENGINE_PACKAGE",
    "GEOGRAPHIC_EXTENT",
    "LEVEL_ZERO_TILES_X",
    "LEVEL_ZERO_TILES_Y",
    "MARS2000_EQUIRECT_WKT",
    "MARS2000_GEOGRAPHIC_WKT",
    "MARS_CRS_CODE",
    "MARS_CRS_ID",
    "MARS_RADIUS_M",
    "MARS_SEMI_MINOR_M",
    "MATCH_SCORE_COLORMAP",
    "MAX_ZOOM",
    "MIN_ZOOM",
    "NILI_FOSSAE_BBOX",
    "NODATA_RGBA",
    "REGION_BBOX",
    "SAM_ANGLE_COLORMAP",
]
