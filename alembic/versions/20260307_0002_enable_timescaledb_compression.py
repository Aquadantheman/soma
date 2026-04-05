"""Enable TimescaleDB compression for signals table

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07

Enables automatic compression for the signals hypertable:
- Compresses data older than 30 days
- Reduces storage by 5-10x for historical data
- No performance impact on recent data queries

TimescaleDB compression uses columnar storage and type-specific algorithms
for significant storage savings on time-series data.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0002"
down_revision: Union[str, None] = "20260307_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable compression on signals hypertable
    # Segment by biomarker_slug for efficient queries
    # Order by time DESC for time-series access patterns
    op.execute("""
        ALTER TABLE signals SET (
            timescaledb.compress = true,
            timescaledb.compress_segmentby = 'biomarker_slug, source_slug',
            timescaledb.compress_orderby = 'time DESC'
        );
    """)

    # Add compression policy: compress chunks older than 30 days
    # This runs automatically via TimescaleDB background workers
    op.execute("""
        SELECT add_compression_policy('signals', INTERVAL '30 days',
            if_not_exists => true);
    """)

    # Add retention policy for ingest_log: delete entries older than 180 days
    # This is an audit table that doesn't need to retain forever
    op.execute("""
        DO $$
        BEGIN
            -- Only add if ingest_log is a hypertable (it might not be)
            IF EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'ingest_log'
            ) THEN
                PERFORM add_retention_policy('ingest_log', INTERVAL '180 days',
                    if_not_exists => true);
            END IF;
        END $$;
    """)

    # Create continuous aggregate for daily signal summaries (optional optimization)
    # This materializes daily statistics for faster dashboard queries
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS signals_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS day,
            biomarker_slug,
            source_slug,
            COUNT(*) AS measurement_count,
            AVG(value) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value
        FROM signals
        WHERE value IS NOT NULL
        GROUP BY day, biomarker_slug, source_slug
        WITH NO DATA;
    """)

    # Add refresh policy for continuous aggregate
    op.execute("""
        SELECT add_continuous_aggregate_policy('signals_daily',
            start_offset => INTERVAL '7 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => true);
    """)


def downgrade() -> None:
    # Remove continuous aggregate refresh policy and view
    op.execute("""
        SELECT remove_continuous_aggregate_policy('signals_daily', if_exists => true);
    """)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS signals_daily;")

    # Remove retention policy
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'ingest_log'
            ) THEN
                PERFORM remove_retention_policy('ingest_log', if_exists => true);
            END IF;
        END $$;
    """)

    # Remove compression policy
    op.execute("""
        SELECT remove_compression_policy('signals', if_exists => true);
    """)

    # Decompress all chunks (may take a while for large tables)
    op.execute("""
        SELECT decompress_chunk(c, if_compressed => true)
        FROM show_chunks('signals') c;
    """)

    # Disable compression
    op.execute("""
        ALTER TABLE signals SET (timescaledb.compress = false);
    """)
