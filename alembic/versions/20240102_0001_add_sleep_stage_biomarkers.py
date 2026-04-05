"""Add sleep stage biomarkers.

Revision ID: 20240102_0001
Revises: 20240101_0000
Create Date: 2024-01-02 00:01:00.000000

Adds individual sleep stage duration biomarkers to enable
sleep architecture analysis (REM%, Deep%, Efficiency, etc.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240102_0001'
down_revision = '20240101_0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add raw sleep stage duration biomarkers
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description)
        VALUES
            ('sleep_rem', 'REM Sleep Duration', 'sleep', 'min', 'wearable',
             'Minutes in REM sleep stage'),
            ('sleep_deep', 'Deep Sleep Duration', 'sleep', 'min', 'wearable',
             'Minutes in deep/N3 sleep stage'),
            ('sleep_core', 'Core Sleep Duration', 'sleep', 'min', 'wearable',
             'Minutes in core/N2 sleep stage'),
            ('sleep_in_bed', 'Time In Bed', 'sleep', 'min', 'wearable',
             'Total minutes in bed (may not be asleep)'),
            ('sleep_core_pct', 'Core Sleep Percentage', 'sleep', 'pct', 'wearable',
             'Percentage of sleep in core/N2 stage')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM biomarker_types
        WHERE slug IN ('sleep_rem', 'sleep_deep', 'sleep_core', 'sleep_in_bed', 'sleep_core_pct')
    """)
