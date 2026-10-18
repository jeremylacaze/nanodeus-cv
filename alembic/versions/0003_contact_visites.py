"""contact et journal des visites

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18 20:12:45.959394
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('demande_contact',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('entreprise', sa.String(length=100), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('version_slug', sa.String(length=40), nullable=False),
    sa.Column('langue', sa.String(length=2), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('erreur', sa.String(length=300), nullable=True),
    sa.Column('envoyee_le', sa.DateTime(), nullable=True),
    sa.Column('empreinte', sa.String(length=32), nullable=False),
    sa.CheckConstraint("statut IN ('en_attente', 'envoyee', 'echec')", name='ck_statut'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('demande_contact', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_demande_contact_cree_le'), ['cree_le'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_contact_empreinte'), ['empreinte'], unique=False)

    op.create_table('sel_journalier',
    sa.Column('jour', sa.Date(), nullable=False),
    sa.Column('valeur', sa.LargeBinary(length=32), nullable=False),
    sa.PrimaryKeyConstraint('jour')
    )
    op.create_table('visite',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('horodatage', sa.DateTime(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('version_slug', sa.String(length=40), nullable=False),
    sa.Column('langue', sa.String(length=2), nullable=False),
    sa.Column('source', sa.String(length=100), nullable=False),
    sa.Column('appareil', sa.String(length=12), nullable=False),
    sa.Column('empreinte', sa.String(length=32), nullable=False),
    sa.CheckConstraint("type IN ('page', 'contact', 'pdf', 'apercu_linkedin')", name='ck_type'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visite_horodatage'), ['horodatage'], unique=False)



def downgrade():
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visite_horodatage'))

    op.drop_table('visite')
    op.drop_table('sel_journalier')
    with op.batch_alter_table('demande_contact', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_demande_contact_empreinte'))
        batch_op.drop_index(batch_op.f('ix_demande_contact_cree_le'))

    op.drop_table('demande_contact')
