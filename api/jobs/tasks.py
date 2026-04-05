"""Background task definitions for Soma.

These functions are designed to be executed by RQ workers.
They should be self-contained and import their dependencies internally.
"""

from typing import Optional, List
from ..observability import get_logger

logger = get_logger("jobs.tasks")


def recompute_baseline(biomarker_slug: str) -> dict:
    """Recompute baseline for a specific biomarker.

    This is a CPU-intensive operation that benefits from
    background processing.

    Args:
        biomarker_slug: The biomarker to recompute (e.g., "heart_rate")

    Returns:
        Dict with computation result and timing info
    """
    import time
    from ..database import get_db
    from ..cache import invalidate_baseline_cache

    start_time = time.perf_counter()
    logger.info("baseline_recompute_started", biomarker=biomarker_slug)

    try:
        # Import science layer
        from soma.baseline.model import compute_baseline

        # Get database session
        db = next(get_db())

        try:
            # Load signals for this biomarker
            from sqlalchemy import text
            query = text("""
                SELECT s.recorded_at, s.value
                FROM signals s
                JOIN biomarkers b ON s.biomarker_id = b.id
                WHERE b.slug = :slug
                AND s.recorded_at >= NOW() - INTERVAL '90 days'
                ORDER BY s.recorded_at
            """)
            result = db.execute(query, {"slug": biomarker_slug})
            rows = result.fetchall()

            if len(rows) < 30:
                logger.warning(
                    "insufficient_data_for_baseline",
                    biomarker=biomarker_slug,
                    count=len(rows)
                )
                return {
                    "status": "skipped",
                    "reason": "insufficient_data",
                    "count": len(rows)
                }

            # Convert to arrays
            import numpy as np
            values = np.array([row[1] for row in rows])

            # Compute baseline
            baseline = compute_baseline(values)

            # Store baseline
            upsert_query = text("""
                INSERT INTO baselines (biomarker_id, computed_at, mean, std, p05, p25, p50, p75, p95, n_samples)
                SELECT b.id, NOW(), :mean, :std, :p05, :p25, :p50, :p75, :p95, :n_samples
                FROM biomarkers b
                WHERE b.slug = :slug
                ON CONFLICT (biomarker_id)
                DO UPDATE SET
                    computed_at = EXCLUDED.computed_at,
                    mean = EXCLUDED.mean,
                    std = EXCLUDED.std,
                    p05 = EXCLUDED.p05,
                    p25 = EXCLUDED.p25,
                    p50 = EXCLUDED.p50,
                    p75 = EXCLUDED.p75,
                    p95 = EXCLUDED.p95,
                    n_samples = EXCLUDED.n_samples
            """)
            db.execute(upsert_query, {
                "slug": biomarker_slug,
                "mean": float(baseline.mean),
                "std": float(baseline.std),
                "p05": float(baseline.p05),
                "p25": float(baseline.p25),
                "p50": float(baseline.median),
                "p75": float(baseline.p75),
                "p95": float(baseline.p95),
                "n_samples": len(rows)
            })
            db.commit()

            # Invalidate cache
            invalidate_baseline_cache(biomarker_slug)

            duration = time.perf_counter() - start_time
            logger.info(
                "baseline_recompute_completed",
                biomarker=biomarker_slug,
                n_samples=len(rows),
                duration_ms=round(duration * 1000, 2)
            )

            return {
                "status": "success",
                "biomarker": biomarker_slug,
                "n_samples": len(rows),
                "duration_ms": round(duration * 1000, 2)
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(
            "baseline_recompute_failed",
            biomarker=biomarker_slug,
            error=str(e)
        )
        raise


def recompute_all_baselines() -> dict:
    """Recompute baselines for all biomarkers.

    Returns:
        Dict with results for each biomarker
    """
    import time
    from ..database import get_db

    start_time = time.perf_counter()
    logger.info("all_baselines_recompute_started")

    db = next(get_db())
    try:
        from sqlalchemy import text
        query = text("SELECT slug FROM biomarkers WHERE is_active = true")
        result = db.execute(query)
        biomarkers = [row[0] for row in result.fetchall()]
    finally:
        db.close()

    results = {}
    for slug in biomarkers:
        try:
            results[slug] = recompute_baseline(slug)
        except Exception as e:
            results[slug] = {"status": "failed", "error": str(e)}

    duration = time.perf_counter() - start_time
    logger.info(
        "all_baselines_recompute_completed",
        count=len(biomarkers),
        duration_ms=round(duration * 1000, 2)
    )

    return {
        "status": "completed",
        "biomarkers": results,
        "duration_ms": round(duration * 1000, 2)
    }


def invalidate_caches(patterns: Optional[List[str]] = None) -> dict:
    """Invalidate Redis caches.

    Args:
        patterns: Specific patterns to invalidate, or None for all

    Returns:
        Dict with invalidation counts
    """
    from ..cache import cache_invalidate_pattern, CacheKeys

    if patterns is None:
        patterns = [f"{CacheKeys.PREFIX}*"]

    results = {}
    total = 0
    for pattern in patterns:
        count = cache_invalidate_pattern(pattern)
        results[pattern] = count
        total += count

    logger.info("caches_invalidated", patterns=patterns, total=total)

    return {
        "status": "completed",
        "invalidated": results,
        "total": total
    }


def run_batch_analysis(
    analysis_type: str,
    biomarker_slugs: Optional[List[str]] = None,
    days: int = 30
) -> dict:
    """Run batch analysis for multiple biomarkers.

    Args:
        analysis_type: Type of analysis (circadian, trend, etc.)
        biomarker_slugs: List of biomarkers, or None for all
        days: Number of days to analyze

    Returns:
        Dict with analysis results
    """
    import time
    from ..database import get_db

    start_time = time.perf_counter()
    logger.info(
        "batch_analysis_started",
        analysis_type=analysis_type,
        biomarkers=biomarker_slugs,
        days=days
    )

    db = next(get_db())
    try:
        from sqlalchemy import text

        # Get biomarkers to analyze
        if biomarker_slugs:
            query = text("""
                SELECT slug FROM biomarkers
                WHERE slug = ANY(:slugs) AND is_active = true
            """)
            result = db.execute(query, {"slugs": biomarker_slugs})
        else:
            query = text("SELECT slug FROM biomarkers WHERE is_active = true")
            result = db.execute(query)

        slugs = [row[0] for row in result.fetchall()]

        results = {}
        for slug in slugs:
            try:
                # This would call the appropriate analysis function
                # For now, just mark as processed
                results[slug] = {"status": "processed"}
            except Exception as e:
                results[slug] = {"status": "failed", "error": str(e)}

    finally:
        db.close()

    duration = time.perf_counter() - start_time
    logger.info(
        "batch_analysis_completed",
        analysis_type=analysis_type,
        count=len(slugs),
        duration_ms=round(duration * 1000, 2)
    )

    return {
        "status": "completed",
        "analysis_type": analysis_type,
        "results": results,
        "duration_ms": round(duration * 1000, 2)
    }
