"""Pytest configuration and shared fixtures."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add science layer to path
science_path = Path(__file__).parent.parent / "science"
sys.path.insert(0, str(science_path))


@pytest.fixture
def sample_hr_data() -> pd.DataFrame:
    """Generate sample heart rate data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=365 * 24, freq="H")

    # Simulate circadian pattern: lower at night, higher during day
    hours = np.array(dates.hour)
    base_hr = 70
    circadian_variation = 10 * np.sin((hours - 4) * np.pi / 12)
    noise = np.random.normal(0, 5, len(dates))
    hr_values = base_hr + circadian_variation + noise
    hr_values = np.clip(hr_values, 40, 120)

    return pd.DataFrame({
        "time": dates,
        "biomarker_slug": "heart_rate",
        "value": hr_values
    })


@pytest.fixture
def sample_steps_data() -> pd.DataFrame:
    """Generate sample step count data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=365, freq="D")

    # Simulate weekly pattern: more active on weekdays
    day_of_week = np.array(dates.dayofweek)
    base_steps = 8000
    weekly_variation = np.where(day_of_week < 5, 2000, -2000)  # Weekday vs weekend
    noise = np.random.normal(0, 1500, len(dates))
    step_values = base_steps + weekly_variation + noise
    step_values = np.clip(step_values, 0, 25000)

    return pd.DataFrame({
        "time": dates,
        "biomarker_slug": "steps",
        "value": step_values
    })


@pytest.fixture
def sample_hrv_data() -> pd.DataFrame:
    """Generate sample HRV SDNN data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=365, freq="D")

    # Simulate HRV with some variation
    base_hrv = 50
    noise = np.random.normal(0, 10, len(dates))
    hrv_values = base_hrv + noise
    hrv_values = np.clip(hrv_values, 10, 100)

    return pd.DataFrame({
        "time": dates,
        "biomarker_slug": "hrv_sdnn",
        "value": hrv_values
    })


@pytest.fixture
def sample_rhr_data() -> pd.DataFrame:
    """Generate sample resting heart rate data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=365, freq="D")

    # Simulate RHR with some variation
    base_rhr = 60
    noise = np.random.normal(0, 3, len(dates))
    rhr_values = base_rhr + noise
    rhr_values = np.clip(rhr_values, 45, 80)

    return pd.DataFrame({
        "time": dates,
        "biomarker_slug": "heart_rate_resting",
        "value": rhr_values
    })


@pytest.fixture
def combined_signals_df(
    sample_hr_data, sample_steps_data, sample_hrv_data, sample_rhr_data
) -> pd.DataFrame:
    """Combine all sample data into a single DataFrame."""
    return pd.concat([
        sample_hr_data,
        sample_steps_data,
        sample_hrv_data,
        sample_rhr_data
    ], ignore_index=True)


@pytest.fixture
def minimal_signals_df() -> pd.DataFrame:
    """Minimal data that should fail most analyses."""
    return pd.DataFrame({
        "time": [datetime.now()],
        "biomarker_slug": ["heart_rate"],
        "value": [70.0]
    })


@pytest.fixture
def empty_signals_df() -> pd.DataFrame:
    """Empty DataFrame for edge case testing."""
    return pd.DataFrame(columns=["time", "biomarker_slug", "value"])
