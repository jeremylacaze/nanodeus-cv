"""suivi des candidatures

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('candidature',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('entreprise', sa.String(length=120), nullable=False),
    sa.Column('poste', sa.String(length=160), nullable=False),
    sa.Column('version_slug', sa.String(length=40), nullable=False),
    sa.Column('langue', sa.String(length=2), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('envoyee_le', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.CheckConstraint("statut IN ('preparee', 'envoyee', 'relancee', 'entretien', 'refusee', 'offre')", name='ck_statut'),
    sa.CheckConstraint("langue IN ('fr', 'en')", name='ck_langue'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source')
    )
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visite_source'), ['source'], unique=False)


def downgrade():
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visite_source'))

    op.drop_table('candidature')
