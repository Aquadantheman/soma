"""Compute personal baselines for all biomarkers with data."""

import sys
sys.path.insert(0, "C:/Users/Linde/Dev/soma/science")

import pandas as pd
from sqlalchemy import create_engine, text
from soma.baseline.model import compute_baseline

DATABASE_URL = "postgresql://postgres:soma_dev@127.0.0.1:5432/soma"

def main():
    engine = create_engine(DATABASE_URL)

    print("Loading signals...")
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT time, biomarker_slug, value FROM signals WHERE value IS NOT NULL",
            conn
        )

    # Convert timezone-aware timestamps to UTC and then to naive
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)

    print(f"Loaded {len(df):,} signals")

    biomarkers = df["biomarker_slug"].unique()
    print(f"Computing baselines for {len(biomarkers)} biomarkers...")

    baselines_computed = 0

    with engine.connect() as conn:
        for slug in biomarkers:
            baseline = compute_baseline(df, slug, window_days=90)

            if baseline is None:
                print(f"  {slug}: insufficient data")
                continue

            # Store in database
            conn.execute(
                text("""
                    INSERT INTO baselines
                        (biomarker_slug, computed_at, window_days, mean, std_dev,
                         p10, p25, p50, p75, p90, sample_count)
                    VALUES
                        (:slug, :computed_at, :window_days, :mean, :std_dev,
                         :p10, :p25, :p50, :p75, :p90, :sample_count)
                """),
                {
                    "slug": baseline.biomarker_slug,
                    "computed_at": baseline.computed_at,
                    "window_days": baseline.window_days,
                    "mean": baseline.mean,
                    "std_dev": baseline.std,
                    "p10": baseline.p10,
                    "p25": baseline.p25,
                    "p50": baseline.median,
                    "p75": baseline.p75,
                    "p90": baseline.p90,
                    "sample_count": baseline.sample_count,
                },
            )
            conn.commit()

            print(f"  {slug}: mean={baseline.mean:.2f}, std={baseline.std:.2f}, n={baseline.sample_count}")
            baselines_computed += 1

    print(f"\nComputed {baselines_computed} baselines!")

if __name__ == "__main__":
    main()
