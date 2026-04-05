"""Add body composition biomarkers.

Revision ID: 20240105_0004
Revises: 20240104_0003
Create Date: 2024-01-05

Adds biomarkers for body composition tracking:
- body_mass: Weight in kg
- body_fat_percentage: Body fat %
- lean_body_mass: Lean mass in kg
- body_mass_index: BMI (kg/m^2)
- height: Height in meters
- waist_circumference: Waist in cm
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20240105_0004'
down_revision = '20240104_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
        -- Body Composition
        ('body_mass',           'Body Mass',              'body_composition', 'kg',     'wearable', 'Body weight in kilograms'),
        ('body_fat_percentage', 'Body Fat Percentage',    'body_composition', 'pct',    'wearable', 'Body fat as percentage of total mass'),
        ('lean_body_mass',      'Lean Body Mass',         'body_composition', 'kg',     'wearable', 'Lean mass (total mass minus fat mass)'),
        ('body_mass_index',     'Body Mass Index',        'body_composition', 'kg/m2',  'wearable', 'BMI = weight(kg) / height(m)^2'),
        ('height',              'Height',                 'body_composition', 'm',      'wearable', 'Standing height in meters'),
        ('waist_circumference', 'Waist Circumference',    'body_composition', 'cm',     'wearable', 'Waist circumference in centimeters')
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM biomarker_types
        WHERE slug IN (
            'body_mass',
            'body_fat_percentage',
            'lean_body_mass',
            'body_mass_index',
            'height',
            'waist_circumference'
        )
    """)
