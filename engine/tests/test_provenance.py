"""Provenance builder + JSON-Schema validation tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from marsgis_engine import config
from marsgis_engine.io.provenance import build_provenance, write_provenance
from marsgis_engine.science.pipeline import RunParams

jsonschema = pytest.importorskip("jsonschema")

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "provenance.schema.json"


def _fake_inputs(tmp_path: Path):
    cube_file = tmp_path / "cube.img"
    cube_file.write_bytes(b"not-a-real-cube-but-hashable")
    ref_file = tmp_path / "ref.tab"
    ref_file.write_text("1.0, 0.5\n2.0, 0.6\n")

    cube = SimpleNamespace(
        path=cube_file,
        label_id="FRT0000TEST",
        rows=8,
        cols=8,
        bands=24,
        crs='PROJCS["Mars_2000"]',
        crs_is_fallback=True,
        transform=(1800.0, 0.0, 4282604.7, 0.0, -1800.0, 1326018.0),
        n_good_bands=22,
        ignore_value=65535.0,
        wavelength_units="Nanometers",
    )
    reference = SimpleNamespace(
        name="synthetic_carbonate",
        mineral_key="mg_carbonate",
        source_path=ref_file,
        sha256="deadbeef",
        point_count=24,
        units_original="micrometers",
    )
    return cube, reference


def _stats():
    return {
        "n_bands_used": 20,
        "pixel_count": 64,
        "valid_pixel_count": 63,
        "detected_pixel_count": 4,
        "detected_fraction": 4 / 63,
        "min": 0.0,
        "max": 1.2,
        "mean": 0.6,
        "median": 0.5,
        "candidate_angle_median": 0.01,
    }


def test_build_provenance_validates_against_schema(tmp_path: Path):
    cube, reference = _fake_inputs(tmp_path)
    params = RunParams(out_dir=str(tmp_path), timestamp="placeholder")
    record = build_provenance(cube, reference, params, _stats(), timestamp="placeholder")
    schema = json.loads(_SCHEMA_PATH.read_text())
    jsonschema.validate(record, schema)  # raises on failure


def test_placeholder_timestamp_is_stable(tmp_path: Path):
    cube, reference = _fake_inputs(tmp_path)
    params = RunParams(out_dir=str(tmp_path))
    r1 = build_provenance(cube, reference, params, _stats(), timestamp="placeholder")
    r2 = build_provenance(cube, reference, params, _stats(), timestamp="placeholder")
    assert r1["created_utc"] == config.TIMESTAMP_PLACEHOLDER
    assert r1["created_utc"] == r2["created_utc"]


def test_disclaimer_and_required_fields_present(tmp_path: Path):
    cube, reference = _fake_inputs(tmp_path)
    params = RunParams(out_dir=str(tmp_path))
    record = build_provenance(cube, reference, params, _stats(), timestamp="placeholder")
    assert record["disclaimer"]
    assert "candidate" in record["disclaimer"].lower()
    assert record["algorithm"] == "SAM"
    assert record["inputs"]["cube"]["crs_is_fallback"] is True
    assert record["inputs"]["reference"]["mica_key"] == "mg_carbonate"
    assert record["parameters"]["threshold_units"] == "radians"


def test_write_provenance_roundtrip(tmp_path: Path):
    cube, reference = _fake_inputs(tmp_path)
    params = RunParams(out_dir=str(tmp_path))
    record = build_provenance(cube, reference, params, _stats(), timestamp="placeholder")
    out = write_provenance(tmp_path / "p.json", record)
    reloaded = json.loads(Path(out).read_text())
    assert reloaded["software"]["name"] == "marsgis-engine"
