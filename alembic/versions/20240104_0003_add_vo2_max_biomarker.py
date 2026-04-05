"""Add VO2 Max biomarker.

Revision ID: 20240104_0003
Revises: 20240103_0002
Create Date: 2024-01-04 00:03:00.000000

Adds VO2 Max (maximal oxygen uptake) - the gold standard measure of
cardiorespiratory fitness with decades of peer-reviewed validation.
"""
from alembic import op
import sqlalchemy as sa


revision = '20240104_0003'
down_revision = '20240103_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description)
        VALUES
            ('vo2_max', 'VO2 Max', 'fitness', 'mL/kg/min', 'wearable',
             'Maximal oxygen uptake - gold standard cardiorespiratory fitness')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM biomarker_types WHERE slug = 'vo2_max'
    """)
