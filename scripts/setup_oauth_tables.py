"""Set up OAuth tables for Whoop integration."""

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://postgres:soma_dev@127.0.0.1:5432/soma"

def main():
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Create users table if not exists
        print("Creating users table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                external_id     TEXT UNIQUE,
                email           TEXT UNIQUE,
                display_name    TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

        # Create default user
        print("Creating default user...")
        conn.execute(text("""
            INSERT INTO users (id, display_name)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'Default User')
            ON CONFLICT (id) DO NOTHING
        """))

        # Create user_oauth_connections table
        print("Creating user_oauth_connections table...")
        conn.execute(text("""
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
                UNIQUE (user_id, provider_slug)
            )
        """))

        # Create indexes
        print("Creating indexes...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider
            ON user_oauth_connections (provider_slug, user_id)
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_oauth_connections_expiry
            ON user_oauth_connections (token_expires_at)
            WHERE token_expires_at IS NOT NULL
        """))

        conn.commit()
        print("Done! OAuth tables created successfully.")

if __name__ == "__main__":
    main()
