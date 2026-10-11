"""SAM score colormaps + legend construction (with the mandatory caveat).

The SAM angle raster is rendered with a sequential ``magma_r`` ramp over
``[0, threshold_rad]`` (0 rad = perfect spectral match); angles above the
threshold are rendered transparent (they are not candidate matches). Every
legend carries the candidate-not-confirmed caveat so a caveat-less rendered
detection is unrepresentable.
"""

from __future__ import annotations

import math

from app.core.constants import SAM_ANGLE_COLORMAP
from app.schemas import Legend, LegendStop
from app.schemas.enums import CANDIDATE_MATCH_CAVEAT, LegendType


def get_colormap(name: str = SAM_ANGLE_COLORMAP) -> dict:
    """Return a rio-tiler colormap dict ({0..255: (r,g,b,a)})."""
    from rio_tiler.colormap import cmap

    for candidate in (name, SAM_ANGLE_COLORMAP, "magma", "viridis"):
        try:
            return cmap.get(candidate)
        except Exception:
            continue
    # Last resort: a simple black->white ramp.
    return {i: (i, i, i, 255) for i in range(256)}


def parse_rescale(rescale: str | None) -> tuple[float, float] | None:
    """Parse a 'min,max' rescale query override."""
    if not rescale:
        return None
    parts = rescale.split(",")
    if len(parts) != 2:
        return None
    try:
        lo, hi = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if hi <= lo:
        return None
    return (lo, hi)


def _sample_hex(colormap: dict, frac: float) -> str:
    idx = max(0, min(255, int(round(frac * 255))))
    # colormap keys are 0..255; find nearest present key.
    if idx not in colormap:
        keys = sorted(colormap)
        idx = min(keys, key=lambda k: abs(k - idx))
    rgba = colormap[idx]
    r, g, b = int(rgba[0]), int(rgba[1]), int(rgba[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def build_legend(
    *,
    value_range: tuple[float, float],
    threshold_rad: float,
    mineral: str,
    reference_id: str,
    colormap_name: str = SAM_ANGLE_COLORMAP,
    n_stops: int = 5,
) -> Legend:
    """Build the continuous SAM-angle legend with per-stop rad/deg labels."""
    lo, hi = value_range
    try:
        colormap = get_colormap(colormap_name)
    except Exception:
        colormap = None

    stops: list[LegendStop] = []
    for i in range(n_stops):
        frac = i / (n_stops - 1)
        val = lo + frac * (hi - lo)
        deg = math.degrees(val)
        color = _sample_hex(colormap, frac) if colormap else "#000000"
        label = f"{val:.3f} rad ({deg:.2f} deg)"
        if i == 0:
            label += " — closest match"
        stops.append(LegendStop(value=round(val, 6), color=color, label=label))

    return Legend(
        title=f"SAM spectral angle vs {mineral}",
        type=LegendType.continuous,
        colormap=colormap_name,
        value_range=(lo, hi),
        units="radians (0 = perfect spectral match)",
        stops=stops,
        nodata_label=f"angle > {threshold_rad:.3f} rad (not a candidate; transparent)",
        caveat=CANDIDATE_MATCH_CAVEAT,
    )
