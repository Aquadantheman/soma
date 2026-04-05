"""Add daylight, mobility, and extended activity biomarkers.

Revision ID: 20240103_0002
Revises: 20240102_0001
Create Date: 2024-01-03 00:02:00.000000

Adds biomarkers from Apple Health for:
- Time in daylight (circadian rhythm research)
- Walking/gait metrics (mobility tracking)
- Extended activity metrics (basal energy, exercise time, etc.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240103_0002'
down_revision = '20240102_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add extended activity biomarkers
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description)
        VALUES
            ('basal_energy', 'Basal Energy', 'activity', 'kcal', 'wearable',
             'Basal metabolic calories burned'),
            ('stand_time', 'Stand Time', 'activity', 'min', 'wearable',
             'Minutes standing'),
            ('exercise_time', 'Exercise Time', 'activity', 'min', 'wearable',
             'Minutes of exercise activity'),
            ('flights_climbed', 'Flights Climbed', 'activity', 'count', 'wearable',
             'Number of floor equivalents climbed'),
            ('physical_effort', 'Physical Effort', 'activity', 'score', 'wearable',
             'Apple Physical Effort metric')
        ON CONFLICT (slug) DO NOTHING
    """)

    # Add mobility/gait biomarkers
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description)
        VALUES
            ('walking_speed', 'Walking Speed', 'mobility', 'm/s', 'wearable',
             'Average walking speed'),
            ('walking_step_length', 'Walking Step Length', 'mobility', 'm', 'wearable',
             'Average step length while walking'),
            ('walking_asymmetry', 'Walking Asymmetry', 'mobility', 'pct', 'wearable',
             'Percentage difference between left/right steps'),
            ('walking_double_support', 'Walking Double Support', 'mobility', 'pct', 'wearable',
             'Percentage of time with both feet on ground')
        ON CONFLICT (slug) DO NOTHING
    """)

    # Add circadian/daylight biomarker
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description)
        VALUES
            ('time_in_daylight', 'Time in Daylight', 'circadian', 'min', 'wearable',
             'Minutes exposed to outdoor daylight')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM biomarker_types
        WHERE slug IN (
            'basal_energy', 'stand_time', 'exercise_time', 'flights_climbed',
            'physical_effort', 'walking_speed', 'walking_step_length',
            'walking_asymmetry', 'walking_double_support', 'time_in_daylight'
        )
    """)
