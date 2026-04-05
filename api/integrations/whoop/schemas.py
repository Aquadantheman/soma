"""Pydantic models for Whoop API responses.

Based on Whoop API v1 documentation:
https://developer.whoop.com/api
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# OAuth2 Responses
# ─────────────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """OAuth2 token response from Whoop."""

    access_token: str
    refresh_token: Optional[str] = None  # Whoop may not always return this
    expires_in: int  # seconds until expiry
    token_type: str = "Bearer"
    scope: Optional[str] = None  # space-separated scopes


# ─────────────────────────────────────────────────────────────────────────────
# User Profile
# ─────────────────────────────────────────────────────────────────────────────


class UserProfile(BaseModel):
    """Basic user profile from Whoop."""

    user_id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class BodyMeasurement(BaseModel):
    """User body measurements."""

    height_meter: Optional[float] = None
    weight_kilogram: Optional[float] = None
    max_heart_rate: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Sleep Data
# ─────────────────────────────────────────────────────────────────────────────


class SleepStage(BaseModel):
    """Individual sleep stage within a sleep record."""

    stage: str  # "awake", "light", "slow_wave_sleep", "rem"
    start_time: datetime
    end_time: datetime


class SleepScore(BaseModel):
    """Sleep quality scores."""

    stage_summary: dict  # Contains time in each stage
    sleep_needed: Optional[dict] = None
    respiratory_rate: Optional[float] = None
    sleep_performance_percentage: Optional[float] = None
    sleep_consistency_percentage: Optional[float] = None
    sleep_efficiency_percentage: Optional[float] = None


class Sleep(BaseModel):
    """Sleep record from Whoop."""

    id: str  # UUID string in v2 API
    user_id: int
    created_at: datetime
    updated_at: datetime
    start: datetime
    end: datetime
    timezone_offset: Optional[str] = None
    nap: bool = False
    score_state: str  # "SCORED", "PENDING_SCORE", etc.
    score: Optional[SleepScore] = None


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Data
# ─────────────────────────────────────────────────────────────────────────────


class RecoveryScore(BaseModel):
    """Recovery metrics from Whoop."""

    user_calibrating: bool = False
    recovery_score: Optional[float] = None  # 0-100
    resting_heart_rate: Optional[float] = None  # bpm
    hrv_rmssd_milli: Optional[float] = None  # ms
    spo2_percentage: Optional[float] = None  # %
    skin_temp_celsius: Optional[float] = None  # delta from baseline


class Recovery(BaseModel):
    """Recovery record from Whoop."""

    cycle_id: str  # UUID string in v2 API
    sleep_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    score_state: str
    score: Optional[RecoveryScore] = None


# ─────────────────────────────────────────────────────────────────────────────
# Cycle (Strain) Data
# ─────────────────────────────────────────────────────────────────────────────


class CycleScore(BaseModel):
    """Strain/cycle metrics from Whoop."""

    strain: Optional[float] = None  # 0-21 scale
    kilojoules: Optional[float] = None
    average_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None


class Cycle(BaseModel):
    """Physiological cycle (day) from Whoop."""

    id: str  # UUID string in v2 API
    user_id: int
    created_at: datetime
    updated_at: datetime
    start: datetime
    end: Optional[datetime] = None
    timezone_offset: Optional[str] = None
    score_state: str
    score: Optional[CycleScore] = None


# ─────────────────────────────────────────────────────────────────────────────
# Workout Data
# ─────────────────────────────────────────────────────────────────────────────


class WorkoutScore(BaseModel):
    """Workout metrics from Whoop."""

    strain: Optional[float] = None
    average_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    kilojoules: Optional[float] = None
    percent_recorded: Optional[float] = None
    distance_meter: Optional[float] = None
    altitude_gain_meter: Optional[float] = None
    altitude_change_meter: Optional[float] = None
    zone_duration: Optional[dict] = None  # time in each HR zone


class Workout(BaseModel):
    """Workout record from Whoop."""

    id: str  # UUID string in v2 API
    user_id: int
    created_at: datetime
    updated_at: datetime
    start: datetime
    end: datetime
    timezone_offset: Optional[str] = None
    sport_id: int  # Still integer
    score_state: str
    score: Optional[WorkoutScore] = None


# ─────────────────────────────────────────────────────────────────────────────
# Paginated Responses
# ─────────────────────────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    """Base for paginated Whoop API responses."""

    next_token: Optional[str] = None


class SleepResponse(PaginatedResponse):
    """Paginated sleep records."""

    records: list[Sleep] = Field(default_factory=list)


class RecoveryResponse(PaginatedResponse):
    """Paginated recovery records."""

    records: list[Recovery] = Field(default_factory=list)


class CycleResponse(PaginatedResponse):
    """Paginated cycle records."""

    records: list[Cycle] = Field(default_factory=list)


class WorkoutResponse(PaginatedResponse):
    """Paginated workout records."""

    records: list[Workout] = Field(default_factory=list)
