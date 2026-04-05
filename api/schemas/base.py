"""Base schemas for core API entities.

Includes biomarkers, signals, baselines, annotations, and status.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


# ─────────────────────────────────────────
# BIOMARKER TYPES
# ─────────────────────────────────────────
class BiomarkerType(BaseModel):
    """A registered biomarker type."""

    id: int
    slug: str
    name: str
    category: str
    unit: str
    source_type: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────
# DATA SOURCES
# ─────────────────────────────────────────
class DataSource(BaseModel):
    """A data source (wearable, app, etc.)."""

    id: int
    slug: str
    name: str
    version: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────
class Signal(BaseModel):
    """A single biosignal measurement."""

    time: datetime
    biomarker_slug: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    source_slug: str
    window_seconds: Optional[int] = None
    quality: int = 100
    meta: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class SignalCreate(BaseModel):
    """Schema for creating a new signal."""

    time: datetime
    biomarker_slug: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    source_slug: str = "manual"
    window_seconds: Optional[int] = None
    quality: int = 100
    meta: Optional[dict[str, Any]] = None


class SignalQuery(BaseModel):
    """Query parameters for filtering signals."""

    biomarker_slug: Optional[str] = None
    source_slug: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, le=1000)
    offset: int = 0


# ─────────────────────────────────────────
# BASELINES
# ─────────────────────────────────────────
class Baseline(BaseModel):
    """Personal baseline for a biomarker."""

    id: int
    biomarker_slug: str
    computed_at: datetime
    window_days: int
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    sample_count: Optional[int] = None

    class Config:
        from_attributes = True


class BaselineCompute(BaseModel):
    """Request to compute baselines."""

    biomarker_slugs: Optional[list[str]] = None  # None = all biomarkers with data
    window_days: int = 90


class DeviationCheck(BaseModel):
    """Request to check deviation from baseline."""

    biomarker_slug: str
    value: float


class DeviationResult(BaseModel):
    """Result of deviation check."""

    biomarker_slug: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    percentile: float
    deviation_pct: float
    is_notable: bool
    is_significant: bool
    direction: str
    clinical_note: Optional[str] = None


# ─────────────────────────────────────────
# ANNOTATIONS
# ─────────────────────────────────────────
class Annotation(BaseModel):
    """An event annotation."""

    id: int
    time: datetime
    duration_s: Optional[int] = None
    category: str
    label: str
    notes: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class AnnotationCreate(BaseModel):
    """Schema for creating an annotation."""

    time: datetime
    duration_s: Optional[int] = None
    category: str
    label: str
    notes: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


# ─────────────────────────────────────────
# STATUS & STATS
# ─────────────────────────────────────────
class IngestRun(BaseModel):
    """Summary of an ingest run."""

    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    source_slug: str
    file_path: Optional[str] = None
    records_parsed: int = 0
    records_written: int = 0
    records_skipped: int = 0
    errors: int = 0
    status: str = "running"

    class Config:
        from_attributes = True


class SystemStatus(BaseModel):
    """System health and statistics."""

    status: str
    total_signals: int
    biomarkers_tracked: int
    sources_active: int
    baselines_computed: int
    latest_ingest: Optional[IngestRun] = None
    date_range: Optional[dict[str, datetime]] = None


# ─────────────────────────────────────────
# COMMON STATISTICAL TYPES
# ─────────────────────────────────────────
class ConfidenceIntervalSchema(BaseModel):
    """A value with its 95% confidence interval."""

    mean: float
    ci_lower: float
    ci_upper: float
    n: int
    is_reliable: bool  # True if n >= 100
