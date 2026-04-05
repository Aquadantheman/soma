"""Initial schema - baseline snapshot

Revision ID: 0001_initial
Revises: None
Create Date: 2024-01-01 00:00:00.000000

This migration represents the initial database schema as of project inception.
It is a baseline snapshot - the actual tables are created by core/sql/init.sql.
This migration exists to establish a starting point for future schema changes.

If you are setting up a fresh database:
    1. Run core/sql/init.sql first
    2. Then: alembic stamp head

If tables already exist, just stamp:
    alembic stamp head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade database schema.

    Note: This is a baseline migration. The actual schema is created by
    core/sql/init.sql which includes TimescaleDB-specific commands.

    Tables created:
    - biomarker_types: Canonical biomarker registry (25+ types)
    - data_sources: Origin system tracking
    - signals: TimescaleDB hypertable for time-series data
    - baselines: Personal baseline distributions
    - annotations: Life events for correlation
    - ingest_log: Audit trail for imports
    """
    # Check if tables already exist (created by init.sql)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'signals')"
    ))
    exists = result.scalar()

    if exists:
        # Tables already exist - this is a stamp migration
        return

    # If tables don't exist, we need to run the full schema
    # Note: This does NOT include TimescaleDB-specific commands
    # For full setup, use core/sql/init.sql
    raise RuntimeError(
        "Tables do not exist. Please run core/sql/init.sql first, "
        "then run 'alembic stamp head' to mark migrations as applied."
    )


def downgrade() -> None:
    """
    Downgrade database schema.

    WARNING: This will DROP ALL TABLES. Use with extreme caution.
    """
    op.execute("DROP TABLE IF EXISTS ingest_log CASCADE")
    op.execute("DROP TABLE IF EXISTS annotations CASCADE")
    op.execute("DROP TABLE IF EXISTS baselines CASCADE")
    op.execute("DROP TABLE IF EXISTS signals CASCADE")
    op.execute("DROP TABLE IF EXISTS data_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS biomarker_types CASCADE")
