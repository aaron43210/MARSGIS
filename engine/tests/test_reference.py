"""MICA reference parsing tests (numpy only; no rasterio/spectral needed)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from marsgis_engine.errors import ReferenceError
from marsgis_engine.io.reference import list_minerals, load_reference, sha256_file


def test_parse_synthetic_tab_um_to_nm(syn_reference: Path, syn_cube):
    ref = load_reference(syn_reference)
    # Wavelengths converted um -> nm; cover the synthetic 1000-2600 nm grid.
    assert ref.wavelengths_nm.min() >= 999.0
    assert ref.wavelengths_nm.max() <= 2601.0
    assert ref.point_count == syn_cube.wl_nm.size
    assert np.all(np.diff(ref.wavelengths_nm) > 0)  # strictly increasing


def test_sha256_matches(syn_reference: Path):
    ref = load_reference(syn_reference)
    expected = hashlib.sha256(Path(syn_reference).read_bytes()).hexdigest()
    assert ref.sha256 == expected == sha256_file(syn_reference)


def test_column_overrides(tmp_path: Path):
    p = tmp_path / "threecol.tab"
    p.write_text("# c0, c1, c2\n1.0, 99.0, 0.5\n1.5, 98.0, 0.6\n2.0, 97.0, 0.7\n")
    # value in column index 2, not the default 1.
    ref = load_reference(p, wavelength_col=0, value_col=2, wavelength_units="um")
    assert np.allclose(ref.values, [0.5, 0.6, 0.7])
    assert np.allclose(ref.wavelengths_nm, [1000.0, 1500.0, 2000.0])


def test_resolve_bundled_carbonate_alias():
    ref = load_reference("carbonate")
    assert ref.mineral_key == "mg_carbonate"
    # Real MICA coverage 0.436-3.897 um -> 436-3897 nm.
    assert 430.0 <= ref.wavelengths_nm.min() <= 440.0
    assert 3890.0 <= ref.wavelengths_nm.max() <= 3900.0
    assert ref.point_count > 400  # real MICA has 480 rows
    # Values are the ratioed I/F corrected column (dimensionless, ~0.5-1.5).
    assert 0.3 < float(np.median(ref.values)) < 2.0


def test_resolve_olivine_and_clay_aliases():
    assert load_reference("olivine").mineral_key == "mg_olivine"
    assert load_reference("clay").mineral_key == "fe_smectite"


def test_unknown_alias_raises():
    with pytest.raises(ReferenceError):
        load_reference("unobtainium")


def test_list_minerals_has_core_phases():
    keys = {e["mica_key"] for e in list_minerals()}
    assert {"mg_carbonate", "mg_olivine", "fe_smectite"} <= keys


def test_invalid_constant_dropped(tmp_path: Path):
    p = tmp_path / "withinvalid.tab"
    p.write_text("1.0, 0.5\n1.5, 65535\n2.0, 0.7\n2.5, 0.8\n")
    ref = load_reference(p, wavelength_units="um")
    assert 65535.0 not in ref.values
    assert ref.point_count == 3
