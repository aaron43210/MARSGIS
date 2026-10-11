"""Build and serialise the provenance record (the stable JSON contract).

The emitted document conforms to ``engine/schemas/provenance.schema.json``
(draft 2020-12). It is the machine-readable reproducibility record for one SAM
run: inputs + their SHA-256, parameters, result statistics, pinned library /
GDAL versions, and the scientific-honesty disclaimer. The backend consumes this
to populate its API ``Provenance`` object and may validate engine outputs
against the same schema.

The ``created_utc`` timestamp defaults to UTC-now but honours an explicit value
(including :data:`config.TIMESTAMP_PLACEHOLDER`) for byte-reproducible test
outputs.
"""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import config
from .._version import __version__
from ..errors import WriteError
from ..logging_utils import get_logger
from .reference import sha256_file

_log = get_logger("provenance")


def _resolve_timestamp(timestamp: str | None) -> str:
    """Return the ISO-8601 created-at string to embed."""
    if timestamp is None:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if timestamp.strip().lower() in ("placeholder", "fixed", "test"):
        return config.TIMESTAMP_PLACEHOLDER
    return timestamp


def _environment() -> dict[str, str]:
    env: dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for mod_name, key in (
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("rasterio", "rasterio"),
        ("spectral", "spectral"),
    ):
        try:
            mod = __import__(mod_name)
            env[key] = getattr(mod, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            env[key] = "unavailable"
    try:
        import rasterio

        env["gdal"] = getattr(rasterio, "__gdal_version__", "unknown")
    except Exception:  # noqa: BLE001
        env["gdal"] = "unavailable"
    return env


def _crs_to_text(crs: Any) -> str:
    if crs is None:
        return ""
    for attr in ("to_wkt", "wkt"):
        try:
            val = getattr(crs, attr)
            return val() if callable(val) else str(val)
        except Exception:  # noqa: BLE001
            continue
    return str(crs)


def _transform_to_list(transform: Any) -> list[float]:
    try:
        return [float(x) for x in transform[:6]]
    except Exception:  # noqa: BLE001
        return []


def build_provenance(
    cube: Any,
    reference: Any,
    params: Any,
    stats: dict[str, Any],
    *,
    timestamp: str | None = None,
    output_paths: dict[str, Path] | None = None,
    engine_image: str = "",
) -> dict[str, Any]:
    """Assemble the provenance dict for one SAM run."""
    window = tuple(float(w) for w in params.window_nm)
    created = _resolve_timestamp(timestamp)

    outputs: dict[str, dict[str, Any]] = {}
    if output_paths:
        for role, p in output_paths.items():
            p = Path(p)
            if p.exists():
                outputs[role] = {
                    "file": p.name,
                    "sha256": sha256_file(p),
                    "size_bytes": p.stat().st_size,
                }

    record: dict[str, Any] = {
        "schema_version": config.PROVENANCE_SCHEMA_VERSION,
        "software": {"name": "marsgis-engine", "version": __version__},
        "engine_image": engine_image,
        "algorithm": "SAM",
        "created_utc": created,
        "inputs": {
            "cube": {
                "path": str(cube.path),
                "label_id": cube.label_id,
                "sha256": sha256_file(cube.path),
                "shape": [int(cube.rows), int(cube.cols), int(cube.bands)],
                "crs": _crs_to_text(cube.crs),
                "crs_is_fallback": bool(cube.crs_is_fallback),
                "transform": _transform_to_list(cube.transform),
                "n_bands": int(cube.bands),
                "n_good_bands": int(cube.n_good_bands),
                "ignore_value": (None if cube.ignore_value is None else float(cube.ignore_value)),
                "wavelength_units_original": cube.wavelength_units,
            },
            "reference": {
                "name": reference.name,
                "mica_key": reference.mineral_key,
                "source": str(reference.source_path),
                "sha256": reference.sha256,
                "n_points": int(reference.point_count),
                "units_original": reference.units_original,
            },
        },
        "parameters": {
            "threshold": float(params.threshold_rad),
            "threshold_units": "radians",
            "wavelength_window_nm": [window[0], window[1]],
            "bands_used": int(stats.get("n_bands_used", 0)),
            "mask_bad_bands": bool(params.mask_bad_bands),
            "continuum_removal": bool(params.continuum_removal),
            "resample_method": str(params.resample_method),
        },
        "results": {
            "n_pixels": int(stats.get("pixel_count", 0)),
            "n_valid_pixels": int(stats.get("valid_pixel_count", 0)),
            "n_candidate_pixels": int(stats.get("detected_pixel_count", 0)),
            "candidate_fraction": float(stats.get("detected_fraction", 0.0)),
            "angle_min": _opt_float(stats.get("min")),
            "angle_max": _opt_float(stats.get("max")),
            "angle_mean": _opt_float(stats.get("mean")),
            "angle_median": _opt_float(stats.get("median")),
            "angle_median_candidates": _opt_float(stats.get("candidate_angle_median")),
        },
        "environment": _environment(),
        "outputs": outputs,
        "disclaimer": config.CANDIDATE_DISCLAIMER,
    }
    return record


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    import math

    return None if math.isnan(f) else f


def write_provenance(path: str | Path, record: dict[str, Any]) -> Path:
    """Serialise a provenance record to JSON (sorted keys, 2-space indent)."""
    path = Path(path)
    try:
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise WriteError(f"could not write provenance {path.name}: {exc}") from exc
    return path
