# A5 — PDS ODE discovery contract

**Evidence:** `backend/tests/test_ode_contract.py` (11 tests, offline, recorded fixture) — run:

```bash
PYTHONPATH=engine/src python -m pytest backend/tests/test_ode_contract.py -q
```

Locks the discovery contract against a recorded ODEResults payload (no network):

| Gate | Test |
|---|---|
| 0..360 (ODE) ↔ [-180,180] (MarsGIS) longitude, both ways + round-trip | `test_to_ode_lon_*`, `test_norm_lon_*`, `test_lon_roundtrip_is_identity` |
| WKT footprint parse + lon normalisation + ring closure | `test_wkt_polygon_parsed_and_lon_normalised`, `test_wkt_garbage_returns_none` |
| product → Observation: source product id, instrument/product-type, sync timestamp | `test_product_to_row_identifiers_and_sync_timestamp` |
| acquisition time recorded (NOT archive-release date) | `test_acquisition_time_not_release_date` |
| pagination/limit + de-duplication by id; request uses ODE 0..360 | `test_discover_dedupes_and_respects_limit`, `test_discover_limit_caps_results` |
| archive-unavailable degrades to `[]` (never raises) | `test_discover_archive_unavailable_returns_empty`, `test_discover_disabled_returns_empty` |

Note: each discovered record stores the **source product id** (`Observation.id`) and a **sync timestamp** (`created_at`/`updated_at`), distinct from the acquisition time (`acquired_at`). CRISM targeting ended 2018, so discovery surfaces archive-released products, not new observations.
