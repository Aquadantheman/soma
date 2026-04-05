"""Redis Queue management for background jobs.

Provides queue access and job management utilities.
"""

import os
import threading
from datetime import timedelta
from typing import Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import redis
    from rq import Queue, Retry
    from rq.job import Job

    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False

from ..observability import get_logger

logger = get_logger("jobs")


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

_redis_conn: Optional["redis.Redis"] = None
_redis_conn_lock = threading.Lock()


def get_connection() -> Optional["redis.Redis"]:
    """Get Redis connection for job queue (thread-safe).

    Security: Supports password authentication and connection timeouts.
    """
    global _redis_conn

    if not RQ_AVAILABLE:
        logger.warning("rq_not_installed")
        return None

    if _redis_conn is None:
        with _redis_conn_lock:
            # Double-check after acquiring lock
            if _redis_conn is None:
                redis_url = os.getenv("SOMA_REDIS_URL")
                if not redis_url:
                    logger.debug("redis_not_configured_for_jobs")
                    return None

                redis_password = os.getenv("SOMA_REDIS_PASSWORD")

                try:
                    # Security: Use timeouts to prevent hanging connections
                    conn = redis.from_url(
                        redis_url,
                        password=redis_password,
                        socket_connect_timeout=5,  # 5 second connection timeout
                        socket_timeout=30,  # 30 second operation timeout (jobs may take longer)
                        retry_on_timeout=True,
                    )
                    conn.ping()
                    _redis_conn = conn
                    # Log without exposing password
                    safe_url = (
                        redis_url.split("@")[-1] if "@" in redis_url else redis_url
                    )
                    logger.info(
                        "job_queue_connected",
                        url=safe_url,
                        has_password=bool(redis_password),
                    )
                except redis.ConnectionError as e:
                    logger.warning("job_queue_unavailable", error=str(e))
                    return None
                except redis.AuthenticationError:
                    logger.error("job_queue_auth_failed")
                    return None

    return _redis_conn


# ─────────────────────────────────────────────────────────────────────────────
# QUEUE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────


class QueueName:
    """Queue names for different job types."""

    DEFAULT = "soma:default"
    HIGH = "soma:high"
    LOW = "soma:low"
    SCHEDULED = "soma:scheduled"


_queues: dict = {}


def get_queue(name: str = QueueName.DEFAULT) -> Optional["Queue"]:
    """Get a job queue by name."""
    if not RQ_AVAILABLE:
        return None

    conn = get_connection()
    if conn is None:
        return None

    if name not in _queues:
        _queues[name] = Queue(name, connection=conn)

    return _queues[name]


# ─────────────────────────────────────────────────────────────────────────────
# JOB STATUS
# ─────────────────────────────────────────────────────────────────────────────


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    DEFERRED = "deferred"
    SCHEDULED = "scheduled"
    STOPPED = "stopped"
    CANCELED = "canceled"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


@dataclass
class JobInfo:
    """Job information container."""

    job_id: str
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    func_name: Optional[str] = None


def get_job_status(job_id: str) -> JobInfo:
    """Get status of a job by ID."""
    conn = get_connection()
    if conn is None:
        return JobInfo(job_id=job_id, status=JobStatus.UNAVAILABLE)

    try:
        job = Job.fetch(job_id, connection=conn)
        status_map = {
            "queued": JobStatus.QUEUED,
            "started": JobStatus.STARTED,
            "finished": JobStatus.FINISHED,
            "failed": JobStatus.FAILED,
            "deferred": JobStatus.DEFERRED,
            "scheduled": JobStatus.SCHEDULED,
            "stopped": JobStatus.STOPPED,
            "canceled": JobStatus.CANCELED,
        }
        return JobInfo(
            job_id=job_id,
            status=status_map.get(job.get_status(), JobStatus.QUEUED),
            result=job.result if job.is_finished else None,
            error=str(job.exc_info) if job.is_failed else None,
            enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else None,
            started_at=job.started_at.isoformat() if job.started_at else None,
            ended_at=job.ended_at.isoformat() if job.ended_at else None,
            func_name=job.func_name,
        )
    except Exception:
        return JobInfo(job_id=job_id, status=JobStatus.NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# JOB ENQUEUEING
# ─────────────────────────────────────────────────────────────────────────────


def enqueue_job(
    func: Callable,
    *args,
    queue_name: str = QueueName.DEFAULT,
    job_timeout: int = 600,
    retry: int = 0,
    **kwargs,
) -> Optional[str]:
    """Enqueue a job for background processing.

    Args:
        func: The function to execute
        *args: Positional arguments for the function
        queue_name: Which queue to use (default, high, low)
        job_timeout: Maximum execution time in seconds
        retry: Number of retry attempts on failure
        **kwargs: Keyword arguments for the function

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    queue = get_queue(queue_name)
    if queue is None:
        logger.warning("job_queue_unavailable", func=func.__name__)
        return None

    try:
        retry_config = Retry(max=retry) if retry > 0 else None
        job = queue.enqueue(
            func, *args, job_timeout=job_timeout, retry=retry_config, **kwargs
        )
        logger.info("job_enqueued", job_id=job.id, func=func.__name__, queue=queue_name)
        return job.id
    except Exception as e:
        logger.error("job_enqueue_failed", func=func.__name__, error=str(e))
        return None


def enqueue_in(
    delay_seconds: int,
    func: Callable,
    *args,
    queue_name: str = QueueName.SCHEDULED,
    **kwargs,
) -> Optional[str]:
    """Schedule a job to run after a delay.

    Args:
        delay_seconds: Seconds to wait before execution
        func: The function to execute
        *args: Positional arguments
        queue_name: Queue to use
        **kwargs: Keyword arguments

    Returns:
        Job ID if scheduled successfully, None otherwise
    """
    queue = get_queue(queue_name)
    if queue is None:
        return None

    try:
        job = queue.enqueue_in(timedelta(seconds=delay_seconds), func, *args, **kwargs)
        logger.info(
            "job_scheduled",
            job_id=job.id,
            func=func.__name__,
            delay_seconds=delay_seconds,
        )
        return job.id
    except Exception as e:
        logger.error("job_schedule_failed", func=func.__name__, error=str(e))
        return None
