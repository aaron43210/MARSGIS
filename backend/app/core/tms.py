"""Custom Mars GEOGRAPHIC TileMatrixSet matching NASA Trek's equirectangular grid.

rio-tiler defaults to a WebMercator (Earth) grid, which would misregister Mars
overlays against the Cesium Mars globe and the Trek basemaps. This module builds
a morecantile TMS over the Mars 2000 geographic CRS with the verified Trek grid
(z0 = 2 columns x 1 row, 256px tiles). The same scheme is advertised to the
frontend in every result ``MapLayer.source`` so overlays co-register pixel for
pixel.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.constants import MARS_RADIUS_M

if TYPE_CHECKING:  # pragma: no cover
    from morecantile import TileMatrixSet

MARS_EQC_TMS_ID = "MarsEQC"


@lru_cache(maxsize=1)
def get_tms() -> TileMatrixSet:
    """Build (once) the Mars geographic TileMatrixSet.

    ``morecantile.custom()`` cannot build a degree-based geographic TMS: it
    assumes a metric CRS via ``meters_per_unit`` and mis-scales the extent. We
    instead reuse OGC **WorldCRS84Quad** — whose tile geometry is exactly the
    2x1-at-z0 equirectangular degree grid used by NASA Trek and Cesium's
    ``GeographicTilingScheme`` — and swap its CRS for the Mars 2000 sphere so
    rio-tiler warps the Mars COG on the correct celestial body. The
    ``PROJ_IGNORE_CELESTIAL_BODY`` flag (set in ``app.core.constants``) lets
    morecantile's internal degree<->degree conversions run across the
    Mars/Earth boundary. Imported lazily so merely importing this module does
    not require the geospatial stack.
    """
    import morecantile
    from morecantile.models import CRSType

    mars_crs = CRSType(f"+proj=longlat +R={MARS_RADIUS_M:.1f} +no_defs")
    base = morecantile.tms.get("WorldCRS84Quad")
    return base.model_copy(update={"crs": mars_crs, "id": MARS_EQC_TMS_ID})
