"""The parallel one-range-per-band window reader returns exactly the right pixels."""

from __future__ import annotations

import httpx
import numpy as np


def test_bsq_window_matches_full_cube(monkeypatch):
    from app.config import Settings
    from app.services import cube_fetch as cf

    bands, lines, samples = 7, 30, 40
    cube = np.random.default_rng(0).random((bands, lines, samples), dtype=np.float32)
    raw = cube.astype("<f4").tobytes()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        rng = request.headers["Range"]
        seen.append(rng)
        start, end = (int(v) for v in rng.removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=raw[start : end + 1])

    real_client = httpx.Client
    monkeypatch.setattr(
        cf.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    meta = {
        "samples": samples,
        "lines": lines,
        "bands": bands,
        "data_type": 4,
        "interleave": "bsq",
        "byte_order": 0,
        "header_offset": 0,
    }
    out = cf._read_bsq_window(Settings(), "https://example/cube.img", meta, 5, 9, 12, 8)

    np.testing.assert_array_equal(out, cube[:, 9:17, 5:17])
    assert len(seen) == bands  # exactly one request per band


def test_non_bsq_falls_back():
    from app.config import Settings
    from app.services import cube_fetch as cf

    meta = {"samples": 4, "lines": 4, "bands": 2, "data_type": 4, "interleave": "bil"}
    assert cf._read_bsq_window(Settings(), "u", meta, 0, 0, 2, 2) is None


def test_full_width_strip_streams_to_disk_with_progress(monkeypatch, tmp_path):
    """fetch_subset_cube writes a full-width strip straight to an ENVI file."""
    import rasterio
    from rasterio.transform import from_origin

    from app.config import Settings
    from app.core.constants import MARS2000_EQUIRECT_WKT
    from app.services import cube_fetch as cf

    bands, lines, samples = 6, 50, 33
    cube = np.random.default_rng(1).random((bands, lines, samples), dtype=np.float32)
    raw = cube.astype("<f4").tobytes()

    def handler(request: httpx.Request) -> httpx.Response:
        start, end = (int(v) for v in request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=raw[start : end + 1])

    real_client = httpx.Client
    monkeypatch.setattr(
        cf.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    hdr = (
        f"ENVI\nsamples = {samples}\nlines = {lines}\nbands = {bands}\nheader offset = 0\n"
        "data type = 4\ninterleave = bsq\nbyte order = 0\n"
    )
    monkeypatch.setattr(
        cf, "_resolve_mtrdr_urls", lambda *a, **k: {"img": "https://x/c.img", "hdr": "h"}
    )
    monkeypatch.setattr(cf.httpx, "get", lambda *a, **k: type("R", (), {"text": hdr})())

    class DS:
        width, height = samples, lines
        crs = rasterio.crs.CRS.from_wkt(MARS2000_EQUIRECT_WKT)

        def window_transform(self, win):
            return from_origin(0, 0, 18, 18)

        def index(self, x, y):
            return (0, 0)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(rasterio, "open", lambda *a, **k: DS())
    seen = []
    out = cf.fetch_subset_cube(
        Settings(),
        "obs",
        (0, 0, 1, 1),
        tmp_path,
        stem="obs_strip",
        rows=10,
        progress=lambda d, t: seen.append((d, t)),
    )
    assert out is not None and out.name == "obs_strip.img"
    got = np.fromfile(out, dtype="<f4").reshape(bands, 10, samples)
    r0 = lines // 2 - 5
    np.testing.assert_array_equal(got, cube[:, r0 : r0 + 10, :])  # full width
    assert seen[-1] == (bands, bands) and len(seen) == bands
    assert (tmp_path / "obs_strip.hdr").exists()
    assert not list(tmp_path.glob("*_partial*"))  # published atomically
