"""The analysis job body — shared by the in-process and arq backends.

Loads the job + observation + reference, stages the input cube, invokes the
engine through the adapter (CPU-bound call offloaded to a worker thread), then
persists an AnalysisResult + Provenance and marks the job succeeded/failed. All
DB writes happen on the event loop; only the engine call runs off-thread.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
from sqlalchemy import update

from app.config import Settings, get_settings
from app.core.colormaps import build_legend
from app.core.constants import DISCLAIMER, SAM_ANGLE_COLORMAP
from app.db.models import (
    AnalysisJobRow,
    AnalysisResultRow,
    Mineral,
    Observation,
    ProvenanceRow,
    utcnow,
)
from app.db.session import session_scope
from app.errors import EngineError
from app.logging import get_logger
from app.schemas import (
    AnalysisResult,
    JobError,
    LayerAvailability,
    LayerSource,
    LayerStyle,
    MapLayer,
    Provenance,
    ProvenanceStep,
    RasterAsset,
    ResultRasters,
    SoftwareComponent,
    SummaryStats,
)
from app.schemas.enums import (
    AnalysisAlgorithm,
    AssetRole,
    AvailabilityStatus,
    JobStatus,
    LayerType,
    TileOrder,
)
from app.services import raster, storage
from app.services.engine_adapter import EngineAdapter, EngineRequest, EngineResult
from app.services.jobs.progress import make_progress_cb, update_progress

_log = get_logger("marsgis.tasks")
_COG_MEDIA = "image/tiff; application=geotiff; profile=cloud-optimized"


@dataclass
class _JobInputs:
    job_id: str
    observation_id: str
    reference_id: str
    algorithm: str
    threshold_rad: float
    continuum_removed: bool
    wavelength_subset_nm: tuple[float, float] | None
    mineral_name: str
    mineral_class: str
    obs_source_url: str
    obs_bbox: tuple[float, float, float, float] | None = None


def stage_cube(settings: Settings, inputs: _JobInputs) -> tuple[Path, bool]:
    """Return (cube_path, is_synthetic). Default 'sample' uses the bundled cube."""
    if settings.engine_cube_source == "sample":
        cube = settings.sample_cube_abspath
        if not cube.exists():
            raise EngineError(
                "sample cube not found",
                detail=f"Expected bundled synthetic cube at {cube}.",
            )
        return cube, True

    # archive mode: stream a bounded AOI subset of the real MTRDR cube from the
    # PDS archive (via /vsicurl range reads — never a bulk download), or reuse a
    # pre-staged full cube if present. Never silently substitute synthetic data.
    cubes_dir = settings.storage_path / "cubes"
    staged = cubes_dir / f"{inputs.observation_id}.img"
    if staged.exists():
        return staged, False
    if inputs.obs_bbox is None:
        raise EngineError(
            "archive cube unavailable",
            detail=f"No footprint bbox for {inputs.observation_id} to locate its MTRDR cube.",
        )
    from app.services.cube_fetch import fetch_subset_cube

    subset = fetch_subset_cube(settings, inputs.observation_id, inputs.obs_bbox, cubes_dir)
    if subset is not None:
        return subset, False
    raise EngineError(
        "could not stream the MTRDR cube from the archive",
        detail=(
            f"ENGINE_CUBE_SOURCE=archive but the PDS cube for {inputs.observation_id} "
            "could not be resolved/streamed. Use ENGINE_CUBE_SOURCE=sample for the "
            "offline synthetic demo."
        ),
    )


def _raster_meta(path: Path) -> tuple[int | None, int | None, int | None]:
    try:
        import rasterio

        with rasterio.open(path) as ds:
            w, h = ds.width, ds.height
        return int(w), int(h), int(path.stat().st_size)
    except Exception:
        try:
            return None, None, int(path.stat().st_size)
        except OSError:
            return None, None, None


def _build_rasters(
    result_id: str,
    value_range: tuple[float, float],
    angle_path: Path,
    mask_path: Path,
) -> ResultRasters:
    aw, ah, asize = _raster_meta(angle_path)
    mw, mh, msize = _raster_meta(mask_path)
    base = f"/api/results/{result_id}/download"
    angle_asset = RasterAsset(
        href=f"{base}?asset=sam_angle",
        role=AssetRole.sam_angle,
        media_type=_COG_MEDIA,
        units="radians",
        value_range=value_range,
        nodata=None,
        width=aw,
        height=ah,
        size_bytes=asize,
    )
    primary_asset = RasterAsset(
        href=f"{base}?asset=primary_metric",
        role=AssetRole.primary_metric,
        media_type=_COG_MEDIA,
        units="radians",
        value_range=value_range,
        nodata=None,
        width=aw,
        height=ah,
        size_bytes=asize,
    )
    mask_asset = RasterAsset(
        href=f"{base}?asset=detection_mask",
        role=AssetRole.detection_mask,
        media_type=_COG_MEDIA,
        units="class (0=non-match, 1=candidate)",
        value_range=(0.0, 1.0),
        nodata=255.0,
        width=mw,
        height=mh,
        size_bytes=msize,
    )
    return ResultRasters(cog=primary_asset, angle=angle_asset, mask=mask_asset, score=None)


def _build_map_layer(
    result_id: str,
    *,
    title: str,
    bounds: tuple[float, float, float, float],
    value_range: tuple[float, float],
    legend,
    now: datetime,
) -> MapLayer:
    source = LayerSource(
        url_template=f"/api/results/{result_id}/tiles/{{z}}/{{x}}/{{y}}.png",
        tile_order=TileOrder.zxy,
        tile_size=256,
        file_extension="png",
        level_zero_tiles_x=2,
        level_zero_tiles_y=1,
        min_zoom=0,
        max_zoom=8,
        tile_matrix_set="MarsEQC",
        provider="MarsGIS",
    )
    style = LayerStyle(
        opacity=0.85,
        colormap=SAM_ANGLE_COLORMAP,
        value_range=value_range,
        z_index=100,
    )
    availability = LayerAvailability(
        status=AvailabilityStatus.verified,
        checked_at=now,
        note="Server-rendered result overlay (on-the-fly rio-tiler).",
    )
    return MapLayer(
        id=f"result-{result_id}",
        type=LayerType.result_tiles,
        title=title,
        subtitle="SAM candidate overlay",
        is_base=False,
        default_visible=True,
        source=source,
        style=style,
        attribution="MarsGIS SAM analysis",
        availability=availability,
        bounds=bounds,
        legend=legend,
        created_at=now,
        updated_at=now,
    )


def _build_provenance(
    *,
    provenance_id: str,
    result_id: str,
    inputs: _JobInputs,
    engine_result: EngineResult,
    params: dict[str, Any],
    now: datetime,
    started: datetime,
) -> Provenance:
    eng_prov = engine_result.provenance or {}
    software = [SoftwareComponent(name="marsgis-engine", version=engine_result.engine_version)]
    for comp in engine_result.software:
        try:
            software.append(SoftwareComponent.model_validate(comp))
        except Exception:
            continue

    steps: list[ProvenanceStep] = [
        ProvenanceStep(
            order=0,
            name="sam_analysis",
            software="marsgis-engine",
            version=engine_result.engine_version,
            params=params,
            started_at=started,
            finished_at=now,
            status="succeeded",
            message=(
                "SYNTHETIC sample cube — NOT a real archive observation."
                if engine_result.is_synthetic
                else "SAM run over staged MTRDR cube."
            ),
        )
    ]
    source_urls = [inputs.obs_source_url] if inputs.obs_source_url else []
    prov_params = dict(params)
    prov_params["cube_source"] = "sample" if engine_result.is_synthetic else "archive"
    prov_params["synthetic_input"] = engine_result.is_synthetic
    return Provenance(
        id=provenance_id,
        result_id=result_id,
        job_id=inputs.job_id,
        observation_id=inputs.observation_id,
        reference_id=inputs.reference_id,
        engine_image=engine_result.engine_image,
        engine_version=engine_result.engine_version,
        software=software,
        source_ids=[inputs.observation_id, inputs.reference_id],
        source_urls=source_urls,
        steps=steps,
        params=prov_params,
        inputs_checksums=eng_prov.get("inputs_checksums") if isinstance(eng_prov, dict) else None,
        outputs_checksums=eng_prov.get("outputs_checksums") if isinstance(eng_prov, dict) else None,
        started_at=started,
        finished_at=now,
        timestamp=now,
        caveat=DISCLAIMER,
    )


async def _load_inputs(session, job: AnalysisJobRow) -> _JobInputs:
    obs = await session.get(Observation, job.observation_id)
    mineral = await session.get(Mineral, job.reference_id)
    params = job.params or {}
    subset = params.get("wavelength_subset_nm")
    subset_t = tuple(subset) if subset and len(subset) == 2 else None
    return _JobInputs(
        job_id=job.id,
        observation_id=job.observation_id,
        reference_id=job.reference_id,
        algorithm=job.algorithm,
        threshold_rad=float(params.get("threshold_rad", 0.10)),
        continuum_removed=bool(params.get("continuum_removed", False)),
        wavelength_subset_nm=subset_t,
        mineral_name=mineral.mineral if mineral else job.reference_id,
        mineral_class=mineral.mineral_class if mineral else "other",
        obs_source_url=obs.source_url if obs else "",
        obs_bbox=(obs.minx, obs.miny, obs.maxx, obs.maxy) if obs else None,
    )


async def _fail_job(job_id: str, exc: Exception) -> None:
    code = getattr(exc, "code", "engine_error")
    retriable = isinstance(exc, EngineError)
    async with session_scope() as session:
        job = await session.get(AnalysisJobRow, job_id)
        if job is None or JobStatus(job.status) in (JobStatus.succeeded, JobStatus.failed):
            return
        job.status = JobStatus.failed.value
        job.error = JobError(
            code=code, message=str(exc), detail=getattr(exc, "detail", None), retriable=retriable
        ).model_dump(mode="json")
        job.message = "failed"
        job.finished_at = utcnow()
        job.updated_at = utcnow()
        session.add(job)
    _log.warning("job.failed", job_id=job_id, error=str(exc))


async def _claim_job(job_id: str, *, started: datetime, reclaim_running: bool) -> bool:
    """Atomically move the job to ``running``; True only for the single winner.

    A compare-and-swap ``UPDATE ... WHERE status IN (...)`` rather than
    read-then-write, so when several processes hold the same id (e.g. every
    uvicorn worker re-enqueues ``queued`` rows at startup, or a duplicate
    enqueue) exactly one executes it. ``reclaim_running`` additionally lets an
    arq retry pick up a job whose previous worker died mid-run.
    """
    claimable = [JobStatus.queued.value]
    if reclaim_running:
        claimable.append(JobStatus.running.value)
    async with session_scope() as session:
        res = await session.execute(
            update(AnalysisJobRow)
            .where(AnalysisJobRow.id == job_id)
            .where(AnalysisJobRow.status.in_(claimable))
            .values(
                status=JobStatus.running.value,
                started_at=started,
                progress=0.05,
                message="starting",
                updated_at=utcnow(),
            )
        )
        return res.rowcount == 1


async def run_analysis_job(
    job_id: str,
    *,
    adapter: EngineAdapter,
    settings: Settings | None = None,
    reclaim_running: bool = False,
) -> None:
    settings = settings or get_settings()
    started = utcnow()

    # 1. Claim the job (atomic) + snapshot inputs (ORM objects never cross the thread).
    if not await _claim_job(job_id, started=started, reclaim_running=reclaim_running):
        _log.info("job.not_claimed", job_id=job_id)
        return
    async with session_scope() as session:
        job = await session.get(AnalysisJobRow, job_id)
        if job is None:
            _log.warning("job.missing", job_id=job_id)
            return
        inputs = await _load_inputs(session, job)

    try:
        if inputs.algorithm != AnalysisAlgorithm.SAM.value:
            raise EngineError(f"algorithm '{inputs.algorithm}' not implemented")

        result_id = uuid.uuid4().hex
        provenance_id = uuid.uuid4().hex
        out_dir = storage.result_dir(result_id, create=True, settings=settings)
        cube_path, is_synthetic = await anyio.to_thread.run_sync(stage_cube, settings, inputs)

        request = EngineRequest(
            job_id=job_id,
            result_id=result_id,
            observation_id=inputs.observation_id,
            reference_id=inputs.reference_id,
            mineral_name=inputs.mineral_name,
            mineral_class=inputs.mineral_class,
            cube_path=cube_path,
            threshold_rad=inputs.threshold_rad,
            continuum_removed=inputs.continuum_removed,
            wavelength_subset_nm=inputs.wavelength_subset_nm,
            out_dir=out_dir,
            is_synthetic=is_synthetic,
            timestamp=None,
        )

        progress_cb = make_progress_cb(job_id)
        engine_result: EngineResult = await anyio.to_thread.run_sync(
            lambda: adapter.analyze(request, progress_cb)
        )

        await update_progress(job_id, 0.9, "rendering result metadata")
        await _persist_result(
            inputs=inputs,
            result_id=result_id,
            provenance_id=provenance_id,
            engine_result=engine_result,
            started=started,
        )
        # Only running -> succeeded: a job already failed elsewhere (timeout,
        # restart recovery) must never flip back to succeeded.
        async with session_scope() as session:
            res = await session.execute(
                update(AnalysisJobRow)
                .where(AnalysisJobRow.id == job_id)
                .where(AnalysisJobRow.status == JobStatus.running.value)
                .values(
                    status=JobStatus.succeeded.value,
                    progress=1.0,
                    message="succeeded",
                    result_id=result_id,
                    finished_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
        if res.rowcount != 1:
            _log.warning("job.finished_after_terminal", job_id=job_id, result_id=result_id)
            return
        _log.info("job.succeeded", job_id=job_id, result_id=result_id, synthetic=is_synthetic)
    except Exception as exc:  # noqa: BLE001 - map every failure onto job state
        await _fail_job(job_id, exc)


async def _persist_result(
    *,
    inputs: _JobInputs,
    result_id: str,
    provenance_id: str,
    engine_result: EngineResult,
    started: datetime,
) -> None:
    now = utcnow()
    angle_path = engine_result.angle_path
    mask_path = engine_result.mask_path
    threshold = inputs.threshold_rad
    value_range = (0.0, threshold)

    # Heavy raster reads off the loop.
    bounds = await anyio.to_thread.run_sync(raster.geographic_bounds, angle_path)
    raw_stats = await anyio.to_thread.run_sync(
        lambda: raster.compute_summary_stats(angle_path, mask_path, threshold_rad=threshold)
    )

    legend = build_legend(
        value_range=value_range,
        threshold_rad=threshold,
        mineral=inputs.mineral_name,
        reference_id=inputs.reference_id,
    )

    summary = SummaryStats(
        pixel_count=raw_stats["pixel_count"],
        valid_pixel_count=raw_stats["valid_pixel_count"],
        detected_pixel_count=raw_stats["detected_pixel_count"],
        detected_fraction=raw_stats["detected_fraction"],
        min=raw_stats.get("min"),
        max=raw_stats.get("max"),
        mean=raw_stats.get("mean"),
        median=raw_stats.get("median"),
        std=raw_stats.get("std"),
        threshold_rad=threshold,
        reference_id=inputs.reference_id,
        mineral=inputs.mineral_name,
        histogram=raw_stats.get("histogram"),
        caveat=DISCLAIMER,
    )

    angle_name = angle_path.name
    mask_name = mask_path.name
    rasters = _build_rasters(result_id, value_range, angle_path, mask_path)
    map_layer = _build_map_layer(
        result_id,
        title=f"SAM: {inputs.mineral_name}",
        bounds=bounds,
        value_range=value_range,
        legend=legend,
        now=now,
    )

    result = AnalysisResult(
        id=result_id,
        job_id=inputs.job_id,
        observation_id=inputs.observation_id,
        algorithm=AnalysisAlgorithm.SAM,
        reference_id=inputs.reference_id,
        mineral=inputs.mineral_name,
        rasters=rasters,
        bounds=bounds,
        value_range=value_range,
        legend=legend,
        summary_stats=summary,
        map_layer=map_layer,
        provenance_id=provenance_id,
        caveat=DISCLAIMER,
        created_at=now,
        updated_at=now,
    )

    params = {
        "threshold_rad": threshold,
        "continuum_removed": inputs.continuum_removed,
        "wavelength_subset_nm": list(inputs.wavelength_subset_nm)
        if inputs.wavelength_subset_nm
        else None,
    }
    provenance = _build_provenance(
        provenance_id=provenance_id,
        result_id=result_id,
        inputs=inputs,
        engine_result=engine_result,
        params=params,
        now=now,
        started=started,
    )

    async with session_scope() as session:
        session.add(
            AnalysisResultRow(
                id=result_id,
                job_id=inputs.job_id,
                observation_id=inputs.observation_id,
                reference_id=inputs.reference_id,
                mineral=inputs.mineral_name,
                provenance_id=provenance_id,
                caveat=DISCLAIMER,
                doc=result.model_dump(mode="json"),
                bounds=list(bounds),
                angle_path=angle_name,
                mask_path=mask_name,
                score_path=None,
            )
        )
        session.add(
            ProvenanceRow(
                id=provenance_id,
                result_id=result_id,
                job_id=inputs.job_id,
                observation_id=inputs.observation_id,
                reference_id=inputs.reference_id,
                doc=provenance.model_dump(mode="json"),
            )
        )
