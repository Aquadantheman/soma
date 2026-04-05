"""Job queue infrastructure for Soma API.

Provides background task processing using Redis Queue (RQ).
Used for long-running operations like:
- Baseline recomputation
- Batch signal ingestion
- Periodic analysis refresh
"""

from .queue import (
    get_queue,
    get_connection,
    enqueue_job,
    get_job_status,
    JobStatus,
)
from .tasks import (
    recompute_baseline,
    recompute_all_baselines,
    invalidate_caches,
    run_batch_analysis,
)

__all__ = [
    # Queue management
    "get_queue",
    "get_connection",
    "enqueue_job",
    "get_job_status",
    "JobStatus",
    # Tasks
    "recompute_baseline",
    "recompute_all_baselines",
    "invalidate_caches",
    "run_batch_analysis",
]
