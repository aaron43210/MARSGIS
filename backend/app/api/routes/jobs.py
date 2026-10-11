"""Analysis job submission / listing / polling."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisJobRow, Mineral, Observation, utcnow
from app.deps import client_fingerprint, get_job_runner, get_session, require_api_key
from app.errors import NotFoundError, ValidationErrorApp
from app.schemas import AnalysisJob, AnalysisJobCreate, JobListResponse, SamParams
from app.schemas.enums import IMPLEMENTED_ALGORITHMS_V1, AnalysisAlgorithm, JobStatus
from app.services import quota

router = APIRouter()

_IMPLEMENTED = {a.value for a in IMPLEMENTED_ALGORITHMS_V1}


def job_to_dto(row: AnalysisJobRow) -> AnalysisJob:
    return AnalysisJob.model_validate(
        {
            "id": row.id,
            "observation_id": row.observation_id,
            "algorithm": row.algorithm,
            "reference_id": row.reference_id,
            "params": row.params or {},
            "status": row.status,
            "progress": row.progress,
            "message": row.message,
            "result_id": row.result_id,
            "error": row.error,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
    )


@router.post("/analysis-jobs", response_model=None, status_code=202)
async def create_job(
    body: AnalysisJobCreate,
    response: Response,
    request_fp: str = Depends(client_fingerprint),
    _auth: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
    runner=Depends(get_job_runner),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AnalysisJob:
    algorithm = body.algorithm.value if hasattr(body.algorithm, "value") else str(body.algorithm)

    # 1. Algorithm must be implemented in v1 (SID / BAND_RATIO -> 422).
    if algorithm not in _IMPLEMENTED:
        raise ValidationErrorApp(
            f"algorithm '{algorithm}' is not implemented in v1",
            detail=f"Implemented: {sorted(_IMPLEMENTED)}.",
        )

    # 2. Observation must exist and be analysis-suitable.
    obs = await session.get(Observation, body.observation_id)
    if obs is None:
        stmt = select(Observation).where(Observation.id == body.observation_id)
        obs = (await session.execute(stmt)).scalars().first()
    if obs is None:
        raise NotFoundError(f"observation '{body.observation_id}' not found")
    if not obs.analysis_suitable:
        raise ValidationErrorApp(f"observation '{body.observation_id}' is not analysis_suitable")

    # 3. Reference mineral must exist.
    mineral = await session.get(Mineral, body.reference_id)
    if mineral is None:
        raise NotFoundError(f"reference '{body.reference_id}' not found")

    # 4. Idempotency: dedupe to a recent job with the same key.
    if idempotency_key:
        since = utcnow() - timedelta(hours=1)
        dup_stmt = (
            select(AnalysisJobRow)
            .where(AnalysisJobRow.idempotency_key == idempotency_key)
            .where(AnalysisJobRow.client_fingerprint == request_fp)
            .where(AnalysisJobRow.created_at >= since)
            .order_by(AnalysisJobRow.created_at.desc())
        )
        existing = (await session.execute(dup_stmt)).scalars().first()
        if existing is not None:
            response.status_code = 202
            response.headers["Location"] = f"/api/analysis-jobs/{existing.id}"
            return job_to_dto(existing)

    # 5. Quota.
    await quota.check_quota(session, request_fp)

    # 6. Create + enqueue.
    params = (body.params or SamParams()).model_dump(mode="json")
    import uuid

    job = AnalysisJobRow(
        id=uuid.uuid4().hex,
        observation_id=body.observation_id,
        algorithm=AnalysisAlgorithm.SAM.value,
        reference_id=body.reference_id,
        params=params,
        status=JobStatus.queued.value,
        progress=0.0,
        message="queued",
        client_fingerprint=request_fp,
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    await runner.enqueue(job.id)

    response.status_code = 202
    response.headers["Location"] = f"/api/analysis-jobs/{job.id}"
    return job_to_dto(job)


@router.get("/analysis-jobs", response_model=None)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    observation_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    from sqlalchemy import func

    where = []
    if status:
        where.append(AnalysisJobRow.status == status)
    if observation_id:
        where.append(AnalysisJobRow.observation_id == observation_id)

    count_stmt = select(func.count()).select_from(AnalysisJobRow)
    data_stmt = select(AnalysisJobRow)
    for clause in where:
        count_stmt = count_stmt.where(clause)
        data_stmt = data_stmt.where(clause)
    data_stmt = data_stmt.order_by(AnalysisJobRow.created_at.desc()).limit(limit).offset(offset)

    total = int((await session.execute(count_stmt)).scalar_one())
    rows = (await session.execute(data_stmt)).scalars().all()
    next_offset = offset + limit if (offset + limit) < total else None
    return JobListResponse(
        items=[job_to_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


@router.get("/analysis-jobs/{job_id}", response_model=None)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> AnalysisJob:
    row = await session.get(AnalysisJobRow, job_id)
    if row is None:
        raise NotFoundError(f"job '{job_id}' not found")
    return job_to_dto(row)
