"""slug contraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18 23:00:00.000000
"""
from alembic import op


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

# Même règle que cv.models.SLUG : 1 à 40 caractères parmi a-z, 0-9 et « - ».
CONDITION = "length(slug) BETWEEN 1 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'"


def upgrade():
    with op.batch_alter_table('version') as batch_op:
        batch_op.create_check_constraint('ck_slug', CONDITION)


def downgrade():
    with op.batch_alter_table('version') as batch_op:
        batch_op.drop_constraint('ck_slug', type_='check')
