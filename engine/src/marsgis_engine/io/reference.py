"""Load and parse a MICA type-spectrum ``.tab`` (or a CSV / alias) reference.

A MICA ``.tab`` is fixed-width ASCII with comma-separated columns (the PDS
``.lbl`` documents them). For the bundled Nili Fossae phases the relevant
columns are:

* column 1 (index 0): WAVELENGTH, micrometres, 0.436-3.897 um
* column 2 (index 1): CRISM RATIOED I/F CORRECTED  <- the SAM reference values

These defaults are honoured unless a sibling ``.lbl`` or explicit column flags
say otherwise. The parser is tolerant of comment / header lines and both
comma- and whitespace-delimited numeric rows, so the synthetic
``carbonate_reference.csv`` fixture loads through the same path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from ..errors import ReferenceError
from ..logging_utils import get_logger, log_assumption
from ..science.wavelengths import to_nm

_log = get_logger("reference")

#: Values at or above this magnitude are treated as the PDS INVALID_CONSTANT.
_INVALID_CONSTANT = 65535.0
#: Below this wavelength magnitude we assume micrometres (Mars IR is 0.4-4 um).
_UM_MAGNITUDE_CUTOFF = 50.0

_NUMERIC_SPLIT = re.compile(r"[,\s]+")


@dataclass
class Reference:
    """A resampled-ready reference end-member spectrum."""

    name: str
    mineral_key: str
    source_path: Path
    wavelengths_nm: np.ndarray
    values: np.ndarray
    units_original: str
    sha256: str
    point_count: int


def sha256_file(path: str | Path) -> str:
    """Hex SHA-256 of a file's bytes (streamed)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_minerals() -> list[dict[str, Any]]:
    path = config.mineral_data_path()
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ReferenceError(f"could not read mineral map {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ReferenceError(f"mineral map {path} must be a JSON array")
    return data


def list_minerals() -> list[dict[str, Any]]:
    """Return the bundled alias -> MICA mapping (from data/minerals.json)."""
    return _load_minerals()


def _resolve_alias(name: str) -> tuple[Path, str]:
    """Resolve a friendly alias / mica_key to a bundled .tab path + key."""
    key = name.strip().lower()
    for entry in _load_minerals():
        aliases = {str(a).lower() for a in entry.get("alias", [])}
        aliases.add(str(entry.get("mica_key", "")).lower())
        if key in aliases:
            fpath = config.mica_dir() / str(entry["file"])
            if not fpath.exists():
                raise ReferenceError(
                    f"bundled reference file missing: {fpath.name}",
                    hint="reinstall the package or fetch it with 'marsgis-engine fetch-references'",
                )
            return fpath, str(entry["mica_key"])
    known = sorted({a for e in _load_minerals() for a in e.get("alias", [])})
    raise ReferenceError(
        f"unknown mineral alias {name!r}",
        hint=f"known aliases: {', '.join(known)}; or pass --reference <path.tab>",
    )


def _parse_numeric_rows(text: str) -> np.ndarray:
    """Parse whitespace/comma ASCII into a 2-D float array, skipping junk."""
    rows: list[list[float]] = []
    width = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ";", '"')):
            continue
        toks = [t for t in _NUMERIC_SPLIT.split(s) if t]
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            continue  # header / comment line
        if not vals:
            continue
        rows.append(vals)
        width = max(width, len(vals))
    if not rows:
        raise ReferenceError("no numeric rows found in reference file")
    arr = np.full((len(rows), width), np.nan, dtype=np.float64)
    for i, r in enumerate(rows):
        arr[i, : len(r)] = r
    return arr


def load_reference(
    path_or_mineral: str | Path,
    *,
    wavelength_col: int = 0,
    value_col: int = 1,
    wavelength_units: str | None = None,
) -> Reference:
    """Load a reference from an explicit path or a bundled mineral alias.

    Parameters
    ----------
    path_or_mineral:
        Either a filesystem path to a ``.tab`` / ``.csv`` reference, or a
        friendly alias (``carbonate``, ``olivine``, ``clay``…) resolved through
        ``data/minerals.json`` to a bundled MICA file.
    wavelength_col, value_col:
        0-based column indices. Defaults match the MICA .tab layout
        (col0 = wavelength um, col1 = ratioed I/F corrected).
    wavelength_units:
        Force the wavelength unit (``nm``/``um``). When omitted it is inferred
        from the magnitude and the assumption is logged.
    """
    p = Path(path_or_mineral)
    if p.exists():
        source = p
        mineral_key = p.stem.replace("crism_typespec_", "")
    else:
        source, mineral_key = _resolve_alias(str(path_or_mineral))

    try:
        text = Path(source).read_text(errors="ignore")
    except OSError as exc:
        raise ReferenceError(f"could not read reference {source}: {exc}") from exc

    arr = _parse_numeric_rows(text)
    ncols = arr.shape[1]
    if wavelength_col >= ncols or value_col >= ncols:
        raise ReferenceError(
            f"reference {source.name} has {ncols} columns; "
            f"cannot read wavelength_col={wavelength_col}, value_col={value_col}",
            hint="pass --ref-wavelength-col / --ref-value-col to match the file",
        )

    wl = arr[:, wavelength_col].astype(np.float64)
    vals = arr[:, value_col].astype(np.float64)

    # Drop PDS invalid constants and non-finite samples.
    bad = (
        (~np.isfinite(wl))
        | (~np.isfinite(vals))
        | (vals >= _INVALID_CONSTANT)
        | (wl >= _INVALID_CONSTANT)
    )
    wl = wl[~bad]
    vals = vals[~bad]
    if wl.size < 2:
        raise ReferenceError(f"reference {source.name} has too few valid points")

    # Determine wavelength units.
    units_original = wavelength_units or ""
    if wavelength_units is None:
        if float(np.nanmax(wl)) < _UM_MAGNITUDE_CUTOFF:
            units_original = "micrometers"
            log_assumption(
                _log,
                f"{source.name}: wavelength units not given; values look like "
                "micrometres (max < 50) -> assuming um",
            )
        else:
            units_original = "nanometers"
            log_assumption(
                _log,
                f"{source.name}: wavelength units not given; values look like "
                "nanometres -> assuming nm",
            )
    wl_nm = to_nm(wl, units_original)

    # Sort strictly increasing, collapse duplicates (keep first).
    order = np.argsort(wl_nm)
    wl_nm = wl_nm[order]
    vals = vals[order]
    keep = np.concatenate(([True], np.diff(wl_nm) > 0))
    if not keep.all():
        _log.warning(
            "%s: dropped %d non-increasing/duplicate wavelength rows",
            source.name,
            int((~keep).sum()),
        )
    wl_nm = wl_nm[keep]
    vals = vals[keep]

    if wl_nm.size < config.MIN_OVERLAP_BANDS:
        _log.warning("%s: only %d reference points after cleaning", source.name, wl_nm.size)

    return Reference(
        name=Path(source).stem,
        mineral_key=mineral_key,
        source_path=Path(source),
        wavelengths_nm=wl_nm,
        values=vals,
        units_original=units_original,
        sha256=sha256_file(source),
        point_count=int(wl_nm.size),
    )
