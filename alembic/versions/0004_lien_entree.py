"""lien d'une entrée du parcours (dépôt ou démo)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('entree', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lien', sa.String(length=300), nullable=True))


def downgrade():
    with op.batch_alter_table('entree', schema=None) as batch_op:
        batch_op.drop_column('lien')
