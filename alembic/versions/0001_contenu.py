"""contenu

Revision ID: 0001
Revises: 
Create Date: 2026-10-18 19:11:32.531697
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table('chiffre',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('valeur_fr', sa.String(length=40), nullable=False),
    sa.Column('valeur_en', sa.String(length=40), nullable=True),
    sa.Column('libelle_fr', sa.String(length=120), nullable=False),
    sa.Column('libelle_en', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('competence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom_fr', sa.String(length=120), nullable=False),
    sa.Column('nom_en', sa.String(length=120), nullable=True),
    sa.Column('categorie_fr', sa.String(length=120), nullable=True),
    sa.Column('categorie_en', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('entree',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('voie', sa.String(length=20), nullable=False),
    sa.Column('intitule_fr', sa.String(length=200), nullable=False),
    sa.Column('intitule_en', sa.String(length=200), nullable=True),
    sa.Column('organisation', sa.String(length=200), nullable=False),
    sa.Column('via', sa.String(length=200), nullable=True),
    sa.Column('debut', sa.Date(), nullable=False),
    sa.Column('fin', sa.Date(), nullable=True),
    sa.Column('lieu', sa.String(length=120), nullable=False),
    sa.Column('technos', sa.String(length=400), nullable=False),
    sa.Column('missions_fr', sa.Text(), nullable=False),
    sa.Column('missions_en', sa.Text(), nullable=True),
    sa.CheckConstraint("type IN ('poste', 'formation', 'projet')", name='ck_type'),
    sa.CheckConstraint("voie IN ('principale', 'parallele')", name='ck_voie'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('profil',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom_complet', sa.String(length=120), nullable=False),
    sa.Column('localisation', sa.String(length=120), nullable=False),
    sa.Column('date_naissance', sa.Date(), nullable=True),
    sa.Column('afficher_age', sa.Boolean(), nullable=False),
    sa.Column('permis', sa.String(length=60), nullable=False),
    sa.Column('interets_fr', sa.Text(), nullable=False),
    sa.Column('interets_en', sa.Text(), nullable=True),
    sa.Column('linkedin_url', sa.String(length=300), nullable=False),
    sa.Column('github_url', sa.String(length=300), nullable=False),
    sa.Column('photo_fichier', sa.String(length=120), nullable=True),
    sa.Column('ouvert_opportunites', sa.Boolean(), nullable=False),
    sa.Column('telephone', sa.String(length=40), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('soft_skill',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom_fr', sa.String(length=120), nullable=False),
    sa.Column('nom_en', sa.String(length=120), nullable=True),
    sa.Column('preuve_fr', sa.Text(), nullable=True),
    sa.Column('preuve_en', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('version',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=40), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('par_defaut', sa.Boolean(), nullable=False),
    sa.Column('titre_fr', sa.String(length=200), nullable=False),
    sa.Column('titre_en', sa.String(length=200), nullable=True),
    sa.Column('accroche_fr', sa.Text(), nullable=False),
    sa.Column('accroche_en', sa.Text(), nullable=True),
    sa.Column('prochaine_mission_fr', sa.String(length=200), nullable=False),
    sa.Column('prochaine_mission_en', sa.String(length=200), nullable=True),
    sa.CheckConstraint("statut IN ('brouillon', 'publiee', 'non_listee')", name='ck_statut'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    with op.batch_alter_table('version', schema=None) as batch_op:
        batch_op.create_index('uq_version_par_defaut', ['par_defaut'], unique=True, sqlite_where=sa.text('par_defaut = 1'))

    op.create_table('version_element',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.Column('type_element', sa.String(length=20), nullable=False),
    sa.Column('element_id', sa.Integer(), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.Column('missions_fr', sa.Text(), nullable=True),
    sa.Column('missions_en', sa.Text(), nullable=True),
    sa.CheckConstraint("type_element IN ('entree', 'soft_skill', 'competence', 'chiffre')", name='ck_type_element'),
    sa.ForeignKeyConstraint(['version_id'], ['version.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'type_element', 'element_id', name='uq_version_element')
    )



def downgrade():

    op.drop_table('version_element')
    with op.batch_alter_table('version', schema=None) as batch_op:
        batch_op.drop_index('uq_version_par_defaut', sqlite_where=sa.text('par_defaut = 1'))

    op.drop_table('version')
    op.drop_table('soft_skill')
    op.drop_table('profil')
    op.drop_table('entree')
    op.drop_table('competence')
    op.drop_table('chiffre')

