"""Regression tests for the engine seam (audit H1 + H2).

H1: ``ENGINE_MODE=subprocess`` shelled out to ``python -m marsgis_engine``, which
had no ``__main__`` module, so every subprocess job failed.
H2: the subprocess/container CLI argv dropped continuum removal, the wavelength
window and the CRS fallback, so those modes ran different science than the
in-process engine while provenance claimed the user's parameters.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.core.constants import MARS2000_EQUIRECT_WKT
from app.services.engine_adapter import (
    ContainerEngine,
    EngineRequest,
    InProcessEngine,
    SubprocessEngine,
)

pytest.importorskip("marsgis_engine")


def _settings() -> Settings:
    return Settings(engine_rlimit_as_mb=8192, engine_timeout_s=300)


def _request(out_dir: Path, *, continuum: bool, window: tuple[float, float] | None):
    settings = _settings()
    return EngineRequest(
        job_id="job",
        result_id="res",
        observation_id="frt00003e12",
        reference_id="mica_carbonate_mg",
        mineral_name="Mg carbonate",
        mineral_class="carbonate",
        cube_path=settings.sample_cube_abspath,
        threshold_rad=0.12,
        continuum_removed=continuum,
        wavelength_subset_nm=window,
        out_dir=out_dir,
        is_synthetic=True,
        timestamp="placeholder",
    )


def _read(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read(1)


def _noop(_frac: float, _msg: str) -> None:
    return None


def test_subprocess_engine_runs_sample_cube(tmp_path: Path):
    """H1: the subprocess engine must actually launch and produce both COGs."""
    result = SubprocessEngine(_settings()).analyze(
        _request(tmp_path, continuum=False, window=None), _noop
    )
    assert result.angle_path.is_file()
    assert result.mask_path.is_file()
    assert result.engine_version != "unknown"


def test_subprocess_engine_version_resolves():
    assert SubprocessEngine(_settings()).version() not in ("unknown", "unavailable")


def test_subprocess_matches_inprocess_with_user_params(tmp_path: Path):
    """H2: continuum removal + a wavelength window must reach the CLI engine."""
    params = {"continuum": True, "window": (1800.0, 2500.0)}
    inproc = InProcessEngine(_settings()).analyze(_request(tmp_path / "a", **params), _noop)
    subproc = SubprocessEngine(_settings()).analyze(_request(tmp_path / "b", **params), _noop)
    np.testing.assert_allclose(
        _read(inproc.angle_path), _read(subproc.angle_path), rtol=0, atol=1e-6, equal_nan=True
    )

    # And the parameters must genuinely change the output (not silently ignored).
    plain = SubprocessEngine(_settings()).analyze(
        _request(tmp_path / "c", continuum=False, window=None), _noop
    )
    assert not np.allclose(_read(plain.angle_path), _read(subproc.angle_path), equal_nan=True)


def test_container_argv_carries_every_param(tmp_path: Path):
    argv = ContainerEngine(_settings())._argv(
        _request(tmp_path, continuum=True, window=(1800.0, 2500.0))
    )
    joined = " ".join(argv)
    assert "--continuum-removal" in argv
    assert argv[argv.index("--wmin") + 1] == "1800.0"
    assert argv[argv.index("--wmax") + 1] == "2500.0"
    assert argv[argv.index("--mars-crs") + 1] == MARS2000_EQUIRECT_WKT
    assert "--cube /in/" in joined and "--out /out" in joined

    off = ContainerEngine(_settings())._argv(_request(tmp_path, continuum=False, window=None))
    assert "--no-continuum-removal" in off
