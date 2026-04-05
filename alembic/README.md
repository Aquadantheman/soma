# Database Migrations

Soma uses Alembic for database schema migrations.

## Setup

### New Database
```bash
# 1. Run initial schema (includes TimescaleDB setup)
psql -d soma -f core/sql/init.sql

# 2. Mark migrations as applied
alembic stamp head
```

### Existing Database
```bash
# Mark current state as baseline
alembic stamp head
```

## Common Commands

```bash
# Check current revision
alembic current

# Show migration history
alembic history

# Create new migration
alembic revision -m "add_user_preferences_table"

# Apply all pending migrations
alembic upgrade head

# Apply next migration only
alembic upgrade +1

# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 0001_initial

# Show SQL without applying
alembic upgrade head --sql
```

## Writing Migrations

Migrations live in `alembic/versions/`. Each migration has:
- `upgrade()` - Apply the change
- `downgrade()` - Revert the change

### Example Migration

```python
def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('preference', sa.Text(), nullable=False),
        sa.Column('value', sa.JSON()),
    )

def downgrade() -> None:
    op.drop_table('user_preferences')
```

## TimescaleDB Considerations

TimescaleDB hypertables require special handling:

```python
def upgrade() -> None:
    # Create regular table first
    op.create_table(
        'sensor_readings',
        sa.Column('time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('sensor_id', sa.Text(), nullable=False),
        sa.Column('value', sa.Float()),
    )
    # Convert to hypertable
    op.execute("SELECT create_hypertable('sensor_readings', 'time')")

def downgrade() -> None:
    op.drop_table('sensor_readings')
```

## Environment

Alembic reads the database URL from `api/config.py`, which loads from:
1. Environment variable: `SOMA_DATABASE_URL`
2. `.env` file
3. Default: `postgresql+psycopg2://postgres:soma_dev@127.0.0.1:5432/soma`
