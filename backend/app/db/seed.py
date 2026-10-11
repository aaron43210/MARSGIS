"""Idempotent, offline startup seeding of catalogue / minerals / map layers.

Rows are validated against the frozen Pydantic contract DTOs before insert and
upserted by id, so repeated startups never create duplicates. All data is
bundled JSON (no network). The CRISM catalogue holds REAL Nili Fossae MTRDR
observation ids/footprints discovered via PDS ODE; the mineral library is a
clearly-labelled SYNTHETIC placeholder (see the file header) and is never
presented as real CRISM MICA data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR, Settings, get_settings
from app.core.constants import GEOGRAPHIC_EXTENT
from app.db.geo import bbox_of, footprint_to_text, polygon_from_bbox
from app.db.models import MapLayerRow, Mineral, Observation
from app.db.session import session_scope
from app.logging import get_logger
from app.schemas import (
    LayerAvailability,
    LayerSource,
    LayerStyle,
    MapLayer,
    ObservationSummary,
    SpectralReference,
)
from app.schemas.enums import AvailabilityStatus, InstrumentType, LayerType, ProductType, TileOrder

_log = get_logger("marsgis.seed")

SEED_DIR = BACKEND_DIR / "app" / "seed"
LOCAL_SEED_DIR = BACKEND_DIR / "app" / "db" / "seeds"

TREK_TILE_TEMPLATE = "https://trek.nasa.gov/tiles/Mars/EQ/{product}/1.0.0//default/default028mm/{{z}}/{{y}}/{{x}}.{ext}"


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Observations (REAL Nili Fossae CRISM MTRDR catalogue)
# --------------------------------------------------------------------------- #
def _build_observation(entry: dict[str, Any], region_name: str) -> Observation:
    obs_id = str(entry["observation_id"])
    bbox = tuple(float(v) for v in entry["bbox_lonlat"])  # (w, s, e, n)
    center = entry.get("center") or [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
    footprint = polygon_from_bbox(bbox)  # type: ignore[arg-type]
    minx, miny, maxx, maxy = bbox_of(footprint)
    acquired = _parse_utc(entry.get("utc_start"))
    title = entry.get("target_comment") or f"CRISM MTRDR {obs_id.upper()}"

    spectral = {
        "band_count": 489,
        "wavelength_min_nm": 1001.0,
        "wavelength_max_nm": 3920.0,
        "wavelength_unit": "nm",
        "sampling_nm": 6.55,
        "ranges": [],
    }
    quality = {
        "has_known_artifacts": False,
        "spike_corrected": True,
        "atmospherically_corrected": True,
        "photometrically_corrected": True,
        "score": 0.9,
        "notes": "MTRDR is analysis-ready (map-projected, atmospherically + photometrically corrected).",
    }

    # Validate the list projection against the frozen contract before persisting.
    ObservationSummary.model_validate(
        {
            "id": obs_id,
            "instrument": InstrumentType.CRISM.value,
            "product_type": ProductType.MTRDR.value,
            "title": title,
            "provider": "PDS Geosciences Node (MRO/CRISM)",
            "region": region_name,
            "bbox": bbox,
            "center": {"lon": float(center[0]), "lat": float(center[1])},
            "footprint": footprint,
            "acquired_at": acquired,
            "resolution_m": 18.0,
            "analysis_suitable": True,
            "thumbnail_url": None,
        }
    )

    return Observation(
        id=obs_id,
        instrument=InstrumentType.CRISM.value,
        product_type=ProductType.MTRDR.value,
        title=title,
        provider="PDS Geosciences Node (MRO/CRISM)",
        region=region_name,
        center_lon=float(center[0]),
        center_lat=float(center[1]),
        minx=minx,
        miny=miny,
        maxx=maxx,
        maxy=maxy,
        footprint_geojson=footprint_to_text(footprint),
        acquired_at=acquired,
        resolution_m=18.0,
        analysis_suitable=True,
        thumbnail_url=None,
        dataset_id="crism_mtrdr_nili_fossae",
        spectral=spectral,
        quality=quality,
        source_url=str(entry.get("dir_url", "")),
        browse_url=None,
    )


async def _seed_observations(session: AsyncSession) -> int:
    path = SEED_DIR / "crism_nili_catalogue.json"
    if not path.exists():
        _log.warning("seed.catalogue_missing", path=str(path))
        return 0
    doc = _load_json(path)
    region_name = (doc.get("region") or {}).get("name", "Nili Fossae")
    existing = set((await session.execute(select(Observation.id))).scalars().all())
    added = 0
    for entry in doc.get("observations", []):
        obs_id = str(entry["observation_id"])
        if obs_id in existing:
            continue
        session.add(_build_observation(entry, region_name))
        added += 1
    return added


# --------------------------------------------------------------------------- #
# Minerals (SYNTHETIC placeholder reference library)
# --------------------------------------------------------------------------- #
async def _seed_minerals(session: AsyncSession) -> int:
    path = LOCAL_SEED_DIR / "mica_minerals.json"
    if not path.exists():
        _log.warning("seed.minerals_missing", path=str(path))
        return 0
    doc = _load_json(path)
    existing = set((await session.execute(select(Mineral.id))).scalars().all())
    added = 0
    for entry in doc.get("minerals", []):
        mid = str(entry["id"])
        if mid in existing:
            continue
        wl = [float(w) for w in entry["wavelength_nm"]]
        refl = [float(r) for r in entry["reflectance"]]
        # Validate the full record (incl. equal-length arrays) against the contract.
        SpectralReference.model_validate(
            {
                "id": mid,
                "mineral": entry["mineral"],
                "mineral_class": entry["mineral_class"],
                "source": entry["source"],
                "source_id": entry.get("source_id"),
                "spectrum_type": entry["spectrum_type"],
                "resampled_to": entry.get("resampled_to"),
                "point_count": entry["point_count"],
                "wavelength_min_nm": entry["wavelength_min_nm"],
                "wavelength_max_nm": entry["wavelength_max_nm"],
                "diagnostic_features_nm": entry.get("diagnostic_features_nm"),
                "color": entry["color"],
                "description": entry.get("description"),
                "created_at": _now(),
                "updated_at": _now(),
                "wavelength": wl,
                "reflectance": refl,
            }
        )
        session.add(
            Mineral(
                id=mid,
                mineral=entry["mineral"],
                mineral_class=entry["mineral_class"],
                source=entry["source"],
                source_id=entry.get("source_id"),
                spectrum_type=entry["spectrum_type"],
                resampled_to=entry.get("resampled_to"),
                point_count=int(entry["point_count"]),
                wavelength_min_nm=float(entry["wavelength_min_nm"]),
                wavelength_max_nm=float(entry["wavelength_max_nm"]),
                diagnostic_features_nm=entry.get("diagnostic_features_nm"),
                color=entry["color"],
                description=entry.get("description"),
                wavelength=wl,
                reflectance=refl,
            )
        )
        added += 1
    return added


# --------------------------------------------------------------------------- #
# Map layers (VERIFIED NASA Trek basemaps/overlays)
# --------------------------------------------------------------------------- #
_DEFAULT_VISIBLE_ROLES = {"basemap_color", "basemap_relief", "elevation_dem", "thermal_day_ir"}
_BASE_ROLES = {"basemap_color", "basemap_relief"}
_ROLE_MAX_ZOOM = {
    "basemap_color": 7,
    "basemap_relief": 6,
    "elevation_dem": 6,
    "thermal_day_ir": 7,
    "thermal_night_ir": 7,
    "surface_roughness": 6,
}
_ROLE_ORDER = {
    "basemap_color": 0,
    "basemap_relief": 1,
    "elevation_dem": 2,
    "thermal_day_ir": 3,
    "thermal_night_ir": 4,
    "surface_roughness": 5,
}


def _build_map_layer(layer: dict[str, Any]) -> MapLayer | None:
    role = layer.get("role", "")
    product = layer["product"]
    ext = layer.get("ext", "png")
    if ext not in ("jpg", "png"):
        return None  # unknown extension => cannot build a tile source
    if role not in _ROLE_MAX_ZOOM:
        return None  # skip products we do not ship (e.g. unconfirmed HRSC blend)

    is_base = role in _BASE_ROLES
    default_visible = role in _DEFAULT_VISIBLE_ROLES
    verified = bool(layer.get("verified", False)) and role in _DEFAULT_VISIBLE_ROLES
    status = AvailabilityStatus.verified if verified else AvailabilityStatus.unconfirmed

    source = LayerSource(
        url_template=TREK_TILE_TEMPLATE.format(product=product, ext=ext),
        tile_order=TileOrder.zyx,
        tile_size=256,
        file_extension=ext,  # type: ignore[arg-type]
        level_zero_tiles_x=2,
        level_zero_tiles_y=1,
        min_zoom=0,
        max_zoom=_ROLE_MAX_ZOOM.get(role, 7),
        tile_matrix_set="default028mm",
        provider="NASA Mars Trek",
    )
    style = LayerStyle(
        opacity=1.0 if is_base else 0.7,
        z_index=0 if is_base else 10,
    )
    availability = LayerAvailability(
        status=status,
        checked_at=_now(),
        sample_tile_url=layer.get("example_tile"),
        http_status=200 if layer.get("verified") else None,
        note=layer.get("note"),
    )
    return MapLayer(
        id=product,
        type=LayerType.basemap if is_base else LayerType.wmts,
        title=layer.get("title", product),
        subtitle=role.replace("_", " ").title(),
        is_base=is_base,
        default_visible=default_visible,
        source=source,
        style=style,
        attribution="NASA/JPL/USGS — Mars Trek (WMTS)",
        availability=availability,
        bounds=tuple(GEOGRAPHIC_EXTENT),
        legend=None,
        created_at=_now(),
        updated_at=_now(),
    )


async def _seed_layers(session: AsyncSession) -> int:
    path = SEED_DIR / "mars_trek_layers.json"
    if not path.exists():
        _log.warning("seed.layers_missing", path=str(path))
        return 0
    doc = _load_json(path)
    existing = set((await session.execute(select(MapLayerRow.id))).scalars().all())
    added = 0
    for layer in doc.get("layers", []):
        ml = _build_map_layer(layer)
        if ml is None or ml.id in existing:
            continue
        session.add(
            MapLayerRow(
                id=ml.id,
                type=ml.type,
                title=ml.title,
                subtitle=ml.subtitle,
                is_base=ml.is_base,
                default_visible=ml.default_visible,
                attribution=ml.attribution,
                sort=_ROLE_ORDER.get(layer.get("role", ""), 99),
                source=ml.source.model_dump(mode="json"),
                style=ml.style.model_dump(mode="json"),
                availability=ml.availability.model_dump(mode="json"),
                bounds=list(ml.bounds) if ml.bounds else None,
                legend=ml.legend.model_dump(mode="json") if ml.legend else None,
            )
        )
        added += 1
    return added


async def seed(settings: Settings | None = None) -> dict[str, int]:
    """Idempotently seed observations, minerals and map layers. Safe to re-run."""
    settings = settings or get_settings()
    if not settings.seed_on_startup:
        _log.info("seed.skipped", reason="SEED_ON_STARTUP=false")
        return {"observations": 0, "minerals": 0, "layers": 0}

    try:
        async with session_scope() as session:
            counts = {
                "observations": await _seed_observations(session),
                "minerals": await _seed_minerals(session),
                "layers": await _seed_layers(session),
            }
    except IntegrityError:
        # Check-then-insert is not atomic across processes: with WEB_CONCURRENCY>1
        # or a separate arq worker, two seeders can both find a table empty and
        # both insert the same ids. The loser hits a unique-id conflict on commit
        # — which simply means the rows are already present, so treat it as a
        # successful (no-op) seed rather than crashing startup.
        _log.info("seed.race_ignored", reason="concurrent seeder committed first")
        return {"observations": 0, "minerals": 0, "layers": 0}
    _log.info("seed.done", **counts)
    return counts
