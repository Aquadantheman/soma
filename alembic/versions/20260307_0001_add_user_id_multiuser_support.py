"""Add user_id column for multi-user support

Revision ID: 20260307_0001
Revises: None
Create Date: 2026-03-07

This migration adds user_id to signals, baselines, and annotations tables
to support multi-user deployments. For single-user deployments, a default
user can be created and all existing data assigned to it.

NOTE: This is a significant schema change. For existing deployments:
1. Create a default user UUID before running this migration
2. Update the DEFAULT clause below with that UUID
3. Run the migration
4. Consider removing the DEFAULT after migration
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260307_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default user ID for existing single-user data
# Generate with: SELECT gen_random_uuid();
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_id     TEXT UNIQUE,
            email           TEXT UNIQUE,
            display_name    TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Create default user for existing data
    op.execute(f"""
        INSERT INTO users (id, display_name)
        VALUES ('{DEFAULT_USER_ID}'::uuid, 'Default User')
        ON CONFLICT (id) DO NOTHING;
    """)

    # Add user_id to signals table
    op.execute(f"""
        ALTER TABLE signals
        ADD COLUMN IF NOT EXISTS user_id UUID
        DEFAULT '{DEFAULT_USER_ID}'::uuid
        REFERENCES users(id);
    """)

    # Add user_id to baselines table
    op.execute(f"""
        ALTER TABLE baselines
        ADD COLUMN IF NOT EXISTS user_id UUID
        DEFAULT '{DEFAULT_USER_ID}'::uuid
        REFERENCES users(id);
    """)

    # Add user_id to annotations table
    op.execute(f"""
        ALTER TABLE annotations
        ADD COLUMN IF NOT EXISTS user_id UUID
        DEFAULT '{DEFAULT_USER_ID}'::uuid
        REFERENCES users(id);
    """)

    # Create index for user-scoped queries (most common access pattern)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_user_biomarker_time
        ON signals (user_id, biomarker_slug, time DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_baselines_user_biomarker
        ON baselines (user_id, biomarker_slug, computed_at DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_annotations_user_time
        ON annotations (user_id, time DESC);
    """)

    # Update unique constraint on signals to include user_id
    # First drop the old constraint
    op.execute("""
        DROP INDEX IF EXISTS signals_time_biomarker_slug_source_slug_idx;
    """)

    # Create new unique constraint including user_id
    op.execute("""
        CREATE UNIQUE INDEX signals_user_time_biomarker_source_idx
        ON signals (user_id, time, biomarker_slug, source_slug)
        WHERE raw_source_id IS NOT NULL;
    """)


def downgrade() -> None:
    # Remove new unique constraint
    op.execute("""
        DROP INDEX IF EXISTS signals_user_time_biomarker_source_idx;
    """)

    # Recreate old unique constraint
    op.execute("""
        CREATE UNIQUE INDEX signals_time_biomarker_slug_source_slug_idx
        ON signals (time, biomarker_slug, source_slug)
        WHERE raw_source_id IS NOT NULL;
    """)

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_signals_user_biomarker_time;")
    op.execute("DROP INDEX IF EXISTS idx_baselines_user_biomarker;")
    op.execute("DROP INDEX IF EXISTS idx_annotations_user_time;")

    # Remove user_id columns
    op.execute("ALTER TABLE signals DROP COLUMN IF EXISTS user_id;")
    op.execute("ALTER TABLE baselines DROP COLUMN IF EXISTS user_id;")
    op.execute("ALTER TABLE annotations DROP COLUMN IF EXISTS user_id;")

    # Drop users table
    op.execute("DROP TABLE IF EXISTS users;")
