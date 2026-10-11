"""End-to-end offline integration test (requires rasterio + spectral)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("spectral")

import rasterio

from marsgis_engine import RunParams, config, run_sam


def _run(syn_cube, syn_reference, out_dir, **overrides):
    params = RunParams(
        out_dir=str(out_dir),
        out_prefix="result",
        timestamp="placeholder",
        **overrides,
    )
    return run_sam(str(syn_cube.img_path), str(syn_reference), params)


def test_outputs_exist_and_planted_detected(tmp_path, syn_cube, syn_reference):
    res = _run(syn_cube, syn_reference, tmp_path)
    for p in (res.angle_path, res.candidate_path, res.provenance_path, res.report_path):
        assert Path(p).exists(), p

    with rasterio.open(res.candidate_path) as ds:
        mask = ds.read(1)
    # Every planted carbonate pixel is a candidate (angle ~0 < threshold).
    for r, c in syn_cube.planted:
        assert mask[r, c] == config.CANDIDATE_MATCH, (r, c)
    # Ignore-value pixels are nodata.
    for r, c in syn_cube.ignore_pixels:
        assert mask[r, c] == config.CANDIDATE_NODATA
    # Background (olivine-like) pixels are not candidates.
    assert res.stats["detected_pixel_count"] == len(syn_cube.planted)


def test_angle_raster_zero_at_planted(tmp_path, syn_cube, syn_reference):
    res = _run(syn_cube, syn_reference, tmp_path)
    with rasterio.open(res.angle_path) as ds:
        assert ds.dtypes[0] == "float32"
        angle = ds.read(1)
        assert np.isnan(ds.nodata)
    for r, c in syn_cube.planted:
        assert angle[r, c] < 1e-4
    for r, c in syn_cube.ignore_pixels:
        assert np.isnan(angle[r, c])


def test_crs_preserved_end_to_end(tmp_path, syn_cube, syn_reference):
    res = _run(syn_cube, syn_reference, tmp_path)
    with rasterio.open(syn_cube.img_path) as src, rasterio.open(res.angle_path) as dst:
        assert dst.transform.a == pytest.approx(src.transform.a)
        assert dst.crs is not None


def test_provenance_conforms_and_deterministic(tmp_path, syn_cube, syn_reference):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "provenance.schema.json").read_text()
    )
    res = _run(syn_cube, syn_reference, tmp_path)
    record = json.loads(Path(res.provenance_path).read_text())
    jsonschema.validate(record, schema)
    assert record["created_utc"] == config.TIMESTAMP_PLACEHOLDER
    assert record["inputs"]["cube"]["crs_is_fallback"] is False
    assert record["results"]["n_candidate_pixels"] == len(syn_cube.planted)
    assert "candidate" in record["disclaimer"].lower()

    # Deterministic angle raster with the placeholder timestamp.
    out2 = tmp_path / "run2"
    res2 = _run(syn_cube, syn_reference, out2)
    with rasterio.open(res.angle_path) as a, rasterio.open(res2.angle_path) as b:
        assert np.allclose(a.read(1), b.read(1), equal_nan=True)


def test_report_has_disclaimer(tmp_path, syn_cube, syn_reference):
    res = _run(syn_cube, syn_reference, tmp_path)
    text = Path(res.report_path).read_text()
    assert "SCIENTIFIC DISCLAIMER" in text
    assert "NOT A CONFIRMED MINERAL DEPOSIT" in text.upper()


def test_continuum_removal_off_still_detects(tmp_path, syn_cube, syn_reference):
    res = _run(syn_cube, syn_reference, tmp_path, continuum_removal=False)
    with rasterio.open(res.candidate_path) as ds:
        mask = ds.read(1)
    for r, c in syn_cube.planted:
        assert mask[r, c] == config.CANDIDATE_MATCH
