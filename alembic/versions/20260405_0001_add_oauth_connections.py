"""Add OAuth connections table for external service integrations

Revision ID: 20260405_0001
Revises: 20260307_0002
Create Date: 2026-04-05

This migration adds support for OAuth2 integrations with external services
like Whoop, Oura, Garmin, etc. Stores tokens and sync state per user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260405_0001"
down_revision: Union[str, None] = "20260307_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_oauth_connections table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_oauth_connections (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_slug       TEXT NOT NULL,
            access_token        TEXT NOT NULL,
            refresh_token       TEXT,
            token_expires_at    TIMESTAMPTZ,
            external_user_id    TEXT,
            scopes              TEXT[],
            last_sync_at        TIMESTAMPTZ,
            sync_cursor         TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- One connection per provider per user
            UNIQUE (user_id, provider_slug)
        );
    """)

    # Index for quick lookup by provider
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider
        ON user_oauth_connections (provider_slug, user_id);
    """)

    # Index for finding connections needing token refresh
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_oauth_connections_expiry
        ON user_oauth_connections (token_expires_at)
        WHERE token_expires_at IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_oauth_connections_expiry;")
    op.execute("DROP INDEX IF EXISTS idx_oauth_connections_provider;")
    op.execute("DROP TABLE IF EXISTS user_oauth_connections;")
