"""Job management API endpoints.

Provides REST API access to background job status and management.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..jobs import (
    get_job_status,
    enqueue_job,
    JobStatus,
    recompute_baseline,
    recompute_all_baselines,
    invalidate_caches,
)
from ..jobs.queue import get_queue, QueueName
from ..auth import require_auth, AuthContext

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    """Response for job submission."""

    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    func_name: Optional[str] = None


class QueueStatsResponse(BaseModel):
    """Response for queue statistics."""

    queues: dict
    total_jobs: int
    workers: int


class RecomputeBaselineRequest(BaseModel):
    """Request to recompute baselines."""

    biomarker_slugs: Optional[List[str]] = None


class InvalidateCacheRequest(BaseModel):
    """Request to invalidate caches."""

    patterns: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    auth: AuthContext = Depends(require_auth),
):
    """Get status of a background job."""
    info = get_job_status(job_id)

    if info.status == JobStatus.UNAVAILABLE:
        raise HTTPException(status_code=503, detail="Job queue is unavailable")

    return JobStatusResponse(
        job_id=info.job_id,
        status=info.status.value,
        result=info.result,
        error=info.error,
        enqueued_at=info.enqueued_at,
        started_at=info.started_at,
        ended_at=info.ended_at,
        func_name=info.func_name,
    )


@router.get("/", response_model=QueueStatsResponse)
def get_queue_stats(
    auth: AuthContext = Depends(require_auth),
):
    """Get queue statistics."""
    try:
        from rq import Worker
        from ..jobs.queue import get_connection
    except ImportError:
        raise HTTPException(status_code=503, detail="Job queue (rq) is not installed")

    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Job queue is unavailable")

    queue_names = [
        QueueName.HIGH,
        QueueName.DEFAULT,
        QueueName.LOW,
        QueueName.SCHEDULED,
    ]
    queues_info = {}
    total = 0

    for name in queue_names:
        queue = get_queue(name)
        if queue:
            count = len(queue)
            queues_info[name] = {
                "pending": count,
                "failed": len(queue.failed_job_registry),
                "finished": len(queue.finished_job_registry),
            }
            total += count

    workers = Worker.count(connection=conn)

    return QueueStatsResponse(queues=queues_info, total_jobs=total, workers=workers)


@router.post("/recompute-baselines", response_model=JobResponse)
def trigger_baseline_recomputation(
    request: RecomputeBaselineRequest,
    auth: AuthContext = Depends(require_auth),
):
    """Trigger baseline recomputation as a background job.

    If biomarker_slugs is provided, only those baselines are recomputed.
    Otherwise, all active biomarkers are recomputed.
    """
    if request.biomarker_slugs:
        # Queue individual jobs for each biomarker
        job_ids = []
        for slug in request.biomarker_slugs:
            job_id = enqueue_job(recompute_baseline, slug, queue_name=QueueName.DEFAULT)
            if job_id:
                job_ids.append(job_id)

        if not job_ids:
            raise HTTPException(
                status_code=503, detail="Failed to enqueue jobs - queue unavailable"
            )

        return JobResponse(
            job_id=job_ids[0],  # Return first job ID
            status="queued",
            message=f"Queued {len(job_ids)} baseline recomputation jobs",
        )
    else:
        # Queue single job to recompute all
        job_id = enqueue_job(
            recompute_all_baselines,
            queue_name=QueueName.LOW,
            job_timeout=3600,  # 1 hour for full recomputation
        )

        if not job_id:
            raise HTTPException(
                status_code=503, detail="Failed to enqueue job - queue unavailable"
            )

        return JobResponse(
            job_id=job_id, status="queued", message="Queued full baseline recomputation"
        )


@router.post("/invalidate-caches", response_model=JobResponse)
def trigger_cache_invalidation(
    request: InvalidateCacheRequest,
    auth: AuthContext = Depends(require_auth),
):
    """Trigger cache invalidation as a background job."""
    job_id = enqueue_job(invalidate_caches, request.patterns, queue_name=QueueName.HIGH)

    if not job_id:
        raise HTTPException(
            status_code=503, detail="Failed to enqueue job - queue unavailable"
        )

    return JobResponse(
        job_id=job_id, status="queued", message="Queued cache invalidation"
    )
