"""Shared pytest fixtures for the engine test-suite (fully offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

import synthetic


@pytest.fixture
def syn_cube(tmp_path: Path) -> synthetic.SyntheticCube:
    """A tiny synthetic ENVI cube with planted carbonate pixels + a CRS."""
    return synthetic.make_synthetic_cube(tmp_path, include_crs=True)


@pytest.fixture
def syn_cube_no_crs(tmp_path: Path) -> synthetic.SyntheticCube:
    """A synthetic cube whose header carries no coordinate-system string."""
    return synthetic.make_synthetic_cube(tmp_path, basename="synthetic_nocrs", include_crs=False)


@pytest.fixture
def syn_reference(tmp_path: Path, syn_cube: synthetic.SyntheticCube) -> Path:
    """A .tab reference (micrometres) equal to the cube's planted end-member."""
    ref_path = tmp_path / "synthetic_carbonate.tab"
    return synthetic.make_synthetic_reference(
        ref_path, syn_cube.wl_nm, syn_cube.reference_values, units="um"
    )
