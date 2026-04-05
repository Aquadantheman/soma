"""Shared utilities for analysis routers."""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd


def load_signals(
    db: Session,
    biomarker_slugs: Optional[list[str]] = None,
    days: Optional[int] = None,
) -> pd.DataFrame:
    """Load signals into a DataFrame with optional filtering.

    Args:
        db: Database session
        biomarker_slugs: Optional list of biomarker slugs to filter by.
                        If None, loads all biomarkers.
        days: Optional number of days of history to load.
              If None, loads all available data.

    Returns:
        DataFrame with columns: time, biomarker_slug, value
    """
    # Build query with optional filters
    query = "SELECT time, biomarker_slug, value FROM signals WHERE value IS NOT NULL"
    params = {}

    if biomarker_slugs:
        # Use parameterized query for safety
        placeholders = ", ".join([f":slug_{i}" for i in range(len(biomarker_slugs))])
        query += f" AND biomarker_slug IN ({placeholders})"
        for i, slug in enumerate(biomarker_slugs):
            params[f"slug_{i}"] = slug

    if days:
        cutoff = datetime.now() - timedelta(days=days)
        query += " AND time >= :cutoff"
        params["cutoff"] = cutoff

    query += " ORDER BY time"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame(columns=["time", "biomarker_slug", "value"])

    return pd.DataFrame(rows, columns=["time", "biomarker_slug", "value"])
