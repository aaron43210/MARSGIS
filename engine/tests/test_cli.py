"""CLI wiring tests (requires rasterio + spectral for the run/info paths)."""

from __future__ import annotations

import math

import pytest

from marsgis_engine import __version__
from marsgis_engine.cli import _threshold_rad, _window_nm, main


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_list_minerals(capsys):
    assert main(["list-minerals"]) == 0
    out = capsys.readouterr().out
    assert "mg_carbonate" in out
    assert "mg_olivine" in out


def test_threshold_units_deg_to_rad():
    import argparse

    ns = argparse.Namespace(threshold=5.7295779513, threshold_units="deg")
    assert _threshold_rad(ns) == pytest.approx(math.radians(5.7295779513))
    ns2 = argparse.Namespace(threshold=0.1, threshold_units="rad")
    assert _threshold_rad(ns2) == pytest.approx(0.1)


def test_window_units_um_to_nm():
    import argparse

    ns = argparse.Namespace(wmin=1.0, wmax=2.6, wavelength_units="um")
    assert _window_nm(ns) == (1000.0, 2600.0)


def test_run_requires_reference_or_mineral():
    with pytest.raises(SystemExit):  # argparse mutually-exclusive required group
        main(["run", "--cube", "x.img", "--out", "o"])


def test_bad_cube_path_maps_to_data_exit_code():
    # Missing cube -> CubeReadError -> exit code 3.
    code = main(["run", "--cube", "/no/such/cube.img", "--mineral", "carbonate", "--out", "/tmp/o"])
    assert code == 3


def test_run_end_to_end(tmp_path, syn_cube, syn_reference, capsys):
    pytest.importorskip("rasterio")
    pytest.importorskip("spectral")
    out = tmp_path / "out"
    code = main(
        [
            "run",
            "--cube",
            str(syn_cube.img_path),
            "--reference",
            str(syn_reference),
            "--method",
            "SAM",
            "--threshold",
            "0.10",
            "--out",
            str(out),
            "--timestamp",
            "placeholder",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "candidate" in printed.lower()
    assert (out / "result_SAM_angle.tif").exists()
    assert (out / "result_SAM_candidate.tif").exists()
    assert (out / "result_provenance.json").exists()
    assert (out / "result_report.txt").exists()


def test_info(tmp_path, syn_cube, capsys):
    pytest.importorskip("rasterio")
    pytest.importorskip("spectral")
    code = main(["info", "--cube", str(syn_cube.hdr_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "wavelengths" in out
    assert "good bands" in out
