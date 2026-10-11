"""Seeding idempotency + catalogue/reference/layer endpoints."""

from __future__ import annotations

OBS_ID = "frt00003e12"


async def test_health_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["contract_version"] == "1.0.0"
    assert data["implemented_algorithms"] == ["SAM"]
    assert set(data["components"]) == {"db", "engine", "tiler", "queue"}


async def test_layers_verified(client):
    resp = await client.get("/api/layers")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 4
    default_visible = [lyr for lyr in items if lyr["default_visible"]]
    assert len(default_visible) == 4
    for layer in default_visible:
        assert layer["availability"]["status"] == "verified"
        assert layer["source"]["file_extension"] in ("jpg", "png")
        assert layer["source"]["tile_order"] == "zyx"
        assert layer["source"]["level_zero_tiles_x"] == 2
        assert layer["source"]["level_zero_tiles_y"] == 1


async def test_layers_filter_is_base(client):
    resp = await client.get("/api/layers", params={"is_base": "true"})
    assert resp.status_code == 200
    assert all(lyr["is_base"] for lyr in resp.json()["items"])


async def test_observations_region(client):
    resp = await client.get("/api/observations", params={"region": "Nili Fossae"})
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] >= 6
    first = page["items"][0]
    assert first["footprint"]["type"] in ("Polygon", "MultiPolygon")
    assert len(first["bbox"]) == 4
    assert first["instrument"] == "CRISM"


async def test_observations_bbox_filter(client):
    hit = await client.get("/api/observations", params={"bbox": "74,20,78,24"})
    assert hit.status_code == 200
    assert hit.json()["total"] >= 1

    miss = await client.get("/api/observations", params={"bbox": "0,0,1,1"})
    assert miss.status_code == 200
    assert miss.json()["total"] == 0

    bad = await client.get("/api/observations", params={"bbox": "1,2,3"})
    assert bad.status_code == 422


async def test_observation_detail(client):
    resp = await client.get(f"/api/observations/{OBS_ID}")
    assert resp.status_code == 200
    obs = resp.json()
    assert obs["id"].lower() == OBS_ID
    assert obs["target"] == "Mars"
    assert obs["source_url"]
    assert obs["quality"] is not None

    missing = await client.get("/api/observations/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


async def test_minerals_carbonate_first(client):
    resp = await client.get("/api/minerals")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 3
    assert items[0]["mineral_class"] == "carbonate"

    mid = items[0]["id"]
    full = await client.get(f"/api/minerals/{mid}")
    assert full.status_code == 200
    spec = full.json()
    assert len(spec["wavelength"]) == len(spec["reflectance"]) == spec["point_count"]


async def test_minerals_class_filter(client):
    resp = await client.get("/api/minerals", params={"class": "olivine"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items and all(m["mineral_class"] == "olivine" for m in items)


async def test_seed_is_idempotent(client):
    from app.db.seed import seed

    counts = await seed()
    assert counts == {"observations": 0, "minerals": 0, "layers": 0}
