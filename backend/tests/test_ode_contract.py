"""A5 evidence: PDS ODE discovery contract tests (offline, recorded fixture).

Locks the behaviour the whole-Mars discovery relies on, against a recorded
ODE-shaped payload — no network:

* 0..360 (ODE) <-> [-180, 180] (MarsGIS) longitude conversion, both directions.
* WKT footprint parsing + longitude normalisation + ring closure.
* product -> Observation mapping: source product id, instrument/product-type
  filter, and the stored sync timestamp.
* acquisition time is recorded (NOT archive-release date).
* pagination/limit + de-duplication by id.
* archive-unavailable: the query degrades to [] rather than raising.

The fixture is a trimmed but structurally faithful ODEResults payload.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import ode

# --- Recorded ODE-shaped payload (trimmed real MTRDR fields) ----------------
# Two distinct products + one duplicate id of the first, so a 3-product page
# de-dupes to 2. Longitudes are ODE 0..360; footprints are WKT POLYGON.
_ODE_PAYLOAD: dict[str, Any] = {
    "ODEResults": {
        "Products": {
            "Product": [
                {
                    "Product_name": "FRT00003E12_07_IF166J_MTR3",
                    "Footprint_C0_geometry": (
                        "POLYGON ((76.94 22.13, 77.21 22.13, 77.21 22.39, 76.94 22.39, 76.94 22.13))"
                    ),
                    "Center_longitude": "77.08",
                    "Center_latitude": "22.26",
                    "Observation_time": "2007-01-02T03:04:05Z",
                    "UTC_start_time": "2007-01-02T03:00:00Z",
                    "Map_scale": "18.0",
                    "Comment": "Nili Fossae carbonate target",
                    "ProductURL": "https://ode.example/frt00003e12",
                },
                {
                    "Product_name": "FRT0000A425_07_IF166J_MTR3",
                    "Footprint_C0_geometry": (
                        "POLYGON ((352.0 -5.6, 352.6 -5.6, 352.6 -5.0, 352.0 -5.0, 352.0 -5.6))"
                    ),
                    "Center_longitude": "352.3",
                    "Center_latitude": "-5.3",
                    "Observation_time": "2008-05-06T07:08:09Z",
                    "Map_scale": "18.0",
                    "Comment": "",
                    "ProductURL": "https://ode.example/frt0000a425",
                },
                {
                    "Product_name": "FRT00003E12_second_file_same_obs",
                    "Footprint_C0_geometry": (
                        "POLYGON ((76.94 22.13, 77.21 22.13, 77.21 22.39, 76.94 22.39, 76.94 22.13))"
                    ),
                    "Center_longitude": "77.08",
                    "Center_latitude": "22.26",
                    "Observation_time": "2007-01-02T03:04:05Z",
                    "ProductURL": "https://ode.example/frt00003e12-dup",
                },
            ]
        }
    }
}


# --- Longitude convention ---------------------------------------------------
def test_to_ode_lon_maps_negative_to_0_360():
    assert ode._to_ode_lon(-5.0) == 355.0
    assert ode._to_ode_lon(-180.0) == 180.0
    assert ode._to_ode_lon(77.0) == 77.0  # already east-positive, unchanged


def test_norm_lon_maps_0_360_back_to_signed():
    assert ode._norm_lon(352.0) == pytest.approx(-8.0)
    assert ode._norm_lon(355.0) == pytest.approx(-5.0)
    assert ode._norm_lon(77.0) == pytest.approx(77.0)


def test_lon_roundtrip_is_identity():
    for lon in (-179.5, -8.0, 0.0, 77.08, 179.9):
        assert ode._norm_lon(ode._to_ode_lon(lon)) == pytest.approx(lon)


# --- Footprint WKT parsing --------------------------------------------------
def test_wkt_polygon_parsed_and_lon_normalised():
    g = ode._wkt_polygon_to_geojson(
        "POLYGON ((352.0 -5.6, 352.6 -5.6, 352.6 -5.0, 352.0 -5.0, 352.0 -5.6))"
    )
    assert g is not None and g["type"] == "Polygon"
    ring = g["coordinates"][0]
    assert ring[0] == ring[-1]  # closed ring
    assert all(-180 <= x <= 180 for x, _ in ring)  # normalised to signed lon
    assert ring[0][0] == pytest.approx(-8.0)


def test_wkt_garbage_returns_none():
    assert ode._wkt_polygon_to_geojson("not a polygon") is None
    assert ode._wkt_polygon_to_geojson("") is None


# --- product -> Observation mapping ----------------------------------------
def test_product_to_row_identifiers_and_sync_timestamp():
    p = _ODE_PAYLOAD["ODEResults"]["Products"]["Product"][0]
    row = ode._product_to_row(p)
    assert row is not None
    # source product id is the lowercased observation base name
    assert row.id == "frt00003e12"
    assert row.instrument == "CRISM"
    assert row.product_type == "MTRDR"
    # footprint bbox normalised into signed lon/lat, within Mars bounds
    assert -180 <= row.minx <= row.maxx <= 180
    assert row.center_lon == pytest.approx(77.08)
    # a sync timestamp is stored (created_at/updated_at), distinct from acquisition
    assert row.created_at is not None and row.updated_at is not None


def test_acquisition_time_not_release_date():
    """The stored time is the OBSERVATION time, documenting acquisition vs. the
    archive-release date (CRISM targeting ended 2018; releases are later)."""
    p = _ODE_PAYLOAD["ODEResults"]["Products"]["Product"][0]
    row = ode._product_to_row(p)
    assert row.acquired_at is not None
    assert row.acquired_at.year == 2007  # Observation_time, not a 2010s release
    # created_at (sync) is strictly later than the 2007 acquisition.
    assert row.created_at > row.acquired_at


# --- discover_crism_mtrdr: pagination, dedup, error path -------------------
class _FakeResp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured: dict[str, Any] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    """Minimal async httpx.AsyncClient stand-in capturing the request params."""

    last_params: dict[str, Any] = {}

    def __init__(self, payload: dict[str, Any] | None, exc: Exception | None, **_: Any) -> None:
        self._payload = payload
        self._exc = exc

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def get(self, url: str, params: dict[str, Any] | None = None):  # noqa: ANN201
        if self._exc is not None:
            raise self._exc
        type(self).last_params = dict(params or {})
        return _FakeResp(self._payload or {})


def _patch_ode(monkeypatch, payload=None, exc=None):
    monkeypatch.setattr(
        ode,
        "get_settings",
        lambda: SimpleNamespace(
            ode_enabled=True,
            ode_base_url="https://ode.example/live2/",
            ode_timeout_s=5,
        ),
    )
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FakeClient(payload, exc, **kw))


async def test_discover_dedupes_and_respects_limit(monkeypatch):
    _patch_ode(monkeypatch, payload=_ODE_PAYLOAD)
    rows = await ode.discover_crism_mtrdr((-10.0, -6.0, 78.0, 23.0), limit=10)
    ids = [r.id for r in rows]
    # 3 products, 2 share an id -> 2 unique observations.
    assert ids == ["frt00003e12", "frt0000a425"]
    # the request used ODE 0..360 longitude for a negative western bound.
    assert _FakeClient.last_params["westernlon"] == ode._to_ode_lon(-10.0) == 350.0
    assert _FakeClient.last_params["pt"] == "MTRDR"


async def test_discover_limit_caps_results(monkeypatch):
    _patch_ode(monkeypatch, payload=_ODE_PAYLOAD)
    rows = await ode.discover_crism_mtrdr((-10.0, -6.0, 78.0, 23.0), limit=1)
    assert len(rows) == 1


async def test_discover_archive_unavailable_returns_empty(monkeypatch):
    _patch_ode(monkeypatch, exc=RuntimeError("archive down"))
    rows = await ode.discover_crism_mtrdr((76.0, 21.0, 78.0, 23.0), limit=10)
    assert rows == []  # degrades gracefully, never raises


async def test_discover_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(ode, "get_settings", lambda: SimpleNamespace(ode_enabled=False))
    rows = await ode.discover_crism_mtrdr((76.0, 21.0, 78.0, 23.0), limit=10)
    assert rows == []
