"""Regenerate contracts/openapi.yaml from the Pydantic schemas (single source of truth).

Usage (from a venv with pydantic>=2 and pyyaml installed):
    python contracts/gen_openapi.py

The `paths` section is hand-authored here; `components.schemas` are derived from
backend/app/schemas so the REST contract can never silently drift from the models.
"""
from __future__ import annotations

import pathlib
import sys

import yaml
from pydantic.json_schema import models_json_schema

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend" / "app"))

import schemas as s  # noqa: E402


class ObservationPage(s.Paginated[s.ObservationSummary]):
    pass


class JobPage(s.Paginated[s.AnalysisJob]):
    pass


class LayerList(s.ListResponse[s.MapLayer]):
    pass


class MineralList(s.ListResponse[s.SpectralReferenceSummary]):
    pass


TOP = [
    s.HealthResponse, s.ErrorResponse, LayerList, ObservationPage, s.Observation,
    MineralList, s.SpectralReference, s.AnalysisJobCreate, s.AnalysisJob, JobPage,
    s.AnalysisResult, s.Provenance,
]

_, defs = models_json_schema(
    [(m, "serialization") for m in TOP],
    ref_template="#/components/schemas/{model}",
    by_alias=True,
)
schemas_components = defs["$defs"]


def jref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def jbody(name):
    return {"required": True, "content": {"application/json": {"schema": jref(name)}}}


def jresp(name, desc="Success"):
    return {"description": desc, "content": {"application/json": {"schema": jref(name)}}}


ERRS = {
    "400": {"$ref": "#/components/responses/BadRequest"},
    "404": {"$ref": "#/components/responses/NotFound"},
    "422": {"$ref": "#/components/responses/ValidationError"},
}


def q(name, typ, desc, enum=None, required=False):
    sch = {"type": typ}
    if enum:
        sch["enum"] = enum
    return {"name": name, "in": "query", "required": required, "description": desc, "schema": sch}


def p(name, typ, desc):
    return {"name": name, "in": "path", "required": True, "description": desc, "schema": {"type": typ}}


paths = {
    "/api/health": {"get": {"tags": ["system"], "operationId": "getHealth",
        "summary": "Liveness/readiness + component status + implemented algorithms.",
        "responses": {"200": jresp("HealthResponse", "Service health")}}},
    "/api/layers": {"get": {"tags": ["map"], "operationId": "listLayers",
        "summary": "Catalog of base + overlay map layers (incl. VERIFIED NASA Trek basemaps).",
        "parameters": [q("type", "string", "filter by layer type",
                         ["basemap", "wmts", "xyz", "result_tiles", "geojson_overlay"]),
                       q("is_base", "boolean", "only base / only overlay layers"),
                       q("availability", "string", "filter by availability",
                         ["verified", "unconfirmed", "unavailable"])],
        "responses": {"200": jresp("LayerList", "Layer catalog")}}},
    "/api/observations": {"get": {"tags": ["catalog"], "operationId": "listObservations",
        "summary": "Search observations (paginated).",
        "parameters": [
            q("instrument", "string", "instrument", ["CRISM", "CTX", "HiRISE", "HRSC", "OMEGA", "THEMIS", "MOLA"]),
            q("product_type", "string", "product type",
              ["MTRDR", "TRDR", "DDR", "MOSAIC", "DEM", "ORTHOIMAGE", "BASEMAP"]),
            q("region", "string", "named region, e.g. 'Nili Fossae'"),
            q("bbox", "string", "spatial filter 'west,south,east,north' (Mars deg)"),
            q("suitable", "boolean", "only analysis_suitable observations"),
            q("q", "string", "free-text match on id/title"),
            q("limit", "integer", "page size (default 50, max 200)"),
            q("offset", "integer", "page offset"),
            q("sort", "string", "sort key",
              ["acquired_at", "-acquired_at", "id", "resolution_m", "-resolution_m"])],
        "responses": {"200": jresp("ObservationPage", "Matching observations"),
                      "422": ERRS["422"]}}},
    "/api/observations/{id}": {"get": {"tags": ["catalog"], "operationId": "getObservation",
        "summary": "Full observation record.", "parameters": [p("id", "string", "native observation id")],
        "responses": {"200": jresp("Observation"), "404": ERRS["404"]}}},
    "/api/minerals": {"get": {"tags": ["catalog"], "operationId": "listMinerals",
        "summary": "Spectral reference library summaries (no sample arrays).",
        "parameters": [q("class", "string", "mineral class",
                         ["carbonate", "olivine", "phyllosilicate", "pyroxene", "sulfate",
                          "iron_oxide", "hydrated_silica", "other"]),
                       q("source", "string", "library source"),
                       q("q", "string", "free-text match")],
        "responses": {"200": jresp("MineralList", "Reference library")}}},
    "/api/minerals/{id}": {"get": {"tags": ["catalog"], "operationId": "getMineral",
        "summary": "Full reference spectrum incl. wavelength[]/reflectance[].",
        "parameters": [p("id", "string", "reference id")],
        "responses": {"200": jresp("SpectralReference"), "404": ERRS["404"]}}},
    "/api/analysis-jobs": {
        "get": {"tags": ["analysis"], "operationId": "listJobs", "summary": "List jobs (paginated).",
                "parameters": [q("status", "string", "filter by status",
                                 ["queued", "running", "succeeded", "failed"]),
                               q("observation_id", "string", "filter by observation"),
                               q("limit", "integer", "page size"), q("offset", "integer", "page offset")],
                "responses": {"200": jresp("JobPage")}},
        "post": {"tags": ["analysis"], "operationId": "createJob",
                 "summary": "Create an analysis job (async). Returns 202 queued.",
                 "parameters": [{"name": "Idempotency-Key", "in": "header", "required": False,
                                 "description": "optional dedupe key", "schema": {"type": "string"}}],
                 "requestBody": jbody("AnalysisJobCreate"),
                 "responses": {"202": {**jresp("AnalysisJob", "Job queued"),
                                       "headers": {"Location": {"description": "job resource url",
                                                                "schema": {"type": "string"}}}},
                               "400": ERRS["400"], "404": ERRS["404"], "422": ERRS["422"]}}},
    "/api/analysis-jobs/{id}": {"get": {"tags": ["analysis"], "operationId": "getJob",
        "summary": "Poll job status/progress; result_id set when succeeded, error when failed.",
        "parameters": [p("id", "string", "job id")],
        "responses": {"200": jresp("AnalysisJob"), "404": ERRS["404"]}}},
    "/api/results/{id}": {"get": {"tags": ["analysis"], "operationId": "getResult",
        "summary": "Result incl. rasters, bounds, legend, summary_stats and ready-to-add map_layer.",
        "parameters": [p("id", "string", "result id")],
        "responses": {"200": jresp("AnalysisResult"), "404": ERRS["404"]}}},
    "/api/results/{id}/download": {"get": {"tags": ["analysis"], "operationId": "downloadResult",
        "summary": "Download a result raster asset as a Cloud-Optimized GeoTIFF.",
        "parameters": [p("id", "string", "result id"),
                       q("asset", "string", "which raster",
                         ["primary_metric", "sam_angle", "detection_mask", "match_score"])],
        "responses": {"200": {"description": "COG",
                              "content": {"image/tiff; application=geotiff; profile=cloud-optimized":
                                          {"schema": {"type": "string", "format": "binary"}}}},
                      "404": ERRS["404"]}}},
    "/api/results/{id}/tiles/{z}/{x}/{y}.png": {"get": {"tags": ["analysis", "map"],
        "operationId": "getResultTile",
        "summary": "Rendered PNG tile (geographic scheme, 2x1@z0, zxy) for Cesium overlay.",
        "parameters": [p("id", "string", "result id"), p("z", "integer", "zoom"),
                       p("x", "integer", "column"), p("y", "integer", "row (north origin)"),
                       q("colormap", "string", "override colormap"),
                       q("rescale", "string", "override value range 'min,max'")],
        "responses": {"200": {"description": "tile",
                              "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}},
                      "204": {"description": "empty tile (no coverage)"}, "404": ERRS["404"]}}},
    "/api/provenance/{id}": {"get": {"tags": ["analysis"], "operationId": "getProvenance",
        "summary": "Reproducibility record for a result (software versions, source ids, steps).",
        "parameters": [p("id", "string", "provenance id (from AnalysisResult.provenance_id)")],
        "responses": {"200": jresp("Provenance"), "404": ERRS["404"]}}},
}
err_content = {"application/json": {"schema": jref("ErrorResponse")}}
doc = {
    "openapi": "3.1.0",
    "info": {"title": "MarsGIS API", "version": "1.0.0",
             "description": "Shared REST contract for MarsGIS (frontend/backend/engine). "
                            "Coordinates are Mars IAU 2000 degrees, not Earth WGS84. "
                            "Generated from backend/app/schemas (Pydantic) - do not hand-edit components."},
    "servers": [{"url": "http://localhost:8000", "description": "local dev"},
                {"url": "/", "description": "same-origin (containerized)"}],
    "tags": [{"name": "system"}, {"name": "map"}, {"name": "catalog"}, {"name": "analysis"}],
    "paths": paths,
    "components": {
        "schemas": schemas_components,
        "responses": {
            "BadRequest": {"description": "Invalid request", "content": err_content},
            "NotFound": {"description": "Resource not found", "content": err_content},
            "ValidationError": {"description": "Validation failed", "content": err_content},
        },
    },
}

out = REPO / "contracts" / "openapi.yaml"
with open(out, "w") as f:
    f.write("# GENERATED from backend/app/schemas via contracts/gen_openapi.py - do not hand-edit.\n")
    yaml.safe_dump(doc, f, sort_keys=False, width=100, allow_unicode=True)
print("wrote", out, "paths=", len(paths), "schemas=", len(schemas_components))



