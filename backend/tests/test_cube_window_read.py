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
