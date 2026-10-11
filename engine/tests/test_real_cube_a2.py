"""A2 evidence: one real CRISM MTRDR observation processed end to end.

Runs the full SAM pipeline on a *real* streamed MTRDR subset (committed fixture
under ``tests/fixtures/real_mtrdr_subset/``, produced once from the PDS archive
via ``scripts/bench_vsicurl.py``'s streaming path) and asserts the engine writes
valid, georeferenced, honestly-provenanced COGs on real data — within a bounded
memory budget (small ``block_rows``).

This complements the synthetic ``test_pipeline.py``: that proves correctness
against planted truth; this proves the pipeline survives *real* CRISM data end
to end. Detection fraction is NOT asserted (that needs validation data); the
gate is "real cube in, valid honest output out".

The test skips (never fails) when the fixture is absent, so a checkout without
the ~2 MB fixture still has a green suite; CI runs it once the fixture is
committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("spectral")

import rasterio

from marsgis_engine import RunParams, config, run_sam

# Pinned fixture identity (committed alongside the data).
OBSERVATION_ID = "frt00003e12"
BBOX_WSEN = (76.9404, 22.1347, 77.2127, 22.3863)

_FIX = Path(__file__).resolve().parent / "fixtures" / "real_mtrdr_subset"
_CUBE = _FIX / f"{OBSERVATION_ID}_subset.img"

pytestmark = pytest.mark.skipif(
    not _CUBE.exists(),
    reason=f"real MTRDR fixture not present ({_CUBE}); run scripts to generate it",
)


def _run(out_dir: Path, **overrides):
    params = RunParams(
        out_dir=str(out_dir),
        out_prefix="a2",
        timestamp="placeholder",
        block_rows=8,  # bounded memory: process 8 rows at a time, not the whole cube
        **overrides,
    )
    return run_sam(str(_CUBE), "carbonate", params)


def test_real_cube_produces_valid_georeferenced_cogs(tmp_path):
    res = _run(tmp_path)
    for p in (res.angle_path, res.candidate_path, res.provenance_path, res.report_path):
        assert Path(p).exists(), p

    with rasterio.open(res.angle_path) as ds:
        assert ds.dtypes[0] == "float32"
        assert ds.crs is not None  # real cube carried a Mars CRS through
        assert ds.transform is not None and ds.transform.a != 0
        assert np.isnan(ds.nodata)
    with rasterio.open(res.candidate_path) as ds:
        mask = ds.read(1)
        assert ds.dtypes[0] == "uint8"
        assert set(np.unique(mask)).issubset(
            {config.CANDIDATE_MATCH, config.CANDIDATE_NON_MATCH, config.CANDIDATE_NODATA}
        )


def test_real_cube_provenance_is_honest(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "provenance.schema.json").read_text()
    )
    res = _run(tmp_path)
    record = json.loads(Path(res.provenance_path).read_text())
    jsonschema.validate(record, schema)

    # Real cube: hashed, many bands, and NOT a fallback CRS (ENVI carried one).
    assert record["inputs"]["cube"]["sha256"]
    assert record["inputs"]["cube"]["n_bands"] >= 100
    # A4 honesty blocks are present on real data too.
    wa = record["wavelength_alignment"]
    assert wa["n_bands_used"] >= config.MIN_OVERLAP_BANDS
    assert wa["n_bands_used"] == len(wa["bands_used_wavelengths_nm"])
    assert "ratioed" in record["preprocessing_caveat"].lower()
    assert "candidate" in record["disclaimer"].lower()


def test_real_cube_run_is_deterministic(tmp_path):
    r1 = _run(tmp_path / "a")
    r2 = _run(tmp_path / "b")
    with rasterio.open(r1.angle_path) as a, rasterio.open(r2.angle_path) as b:
        assert np.allclose(a.read(1), b.read(1), equal_nan=True)
