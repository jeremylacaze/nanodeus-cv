"""Modèle de contenu du CV.

Chaque texte traduisible existe en paire `_fr` / `_en` ; `_en` peut rester vide,
l'affichage retombe alors sur le français (cv/vue.py). Les listes (missions,
centres d'intérêt) sont stockées une valeur par ligne.
"""
from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
                        LargeBinary, String, Text, UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column

from cv.db import Base

TYPES_ENTREE = ("poste", "formation", "projet")
VOIES = ("principale", "parallele")
STATUTS = ("brouillon", "publiee", "non_listee")
TYPES_ELEMENT = ("entree", "soft_skill", "competence", "chiffre")
STATUTS_DEMANDE = ("en_attente", "envoyee", "echec")
TYPES_VISITE = ("page", "contact", "pdf", "apercu_linkedin")
# Seule définition du slug d'une version (/<slug>) : routes, lien d'autre langue, base.
SLUG = r"[a-z0-9-]{1,40}"


def _dans(colonne: str, valeurs: tuple[str, ...]) -> CheckConstraint:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    return CheckConstraint(f"{colonne} IN ({liste})", name=f"ck_{colonne}")


class Profil(Base):
    """Ligne unique (id = 1)."""
    __tablename__ = "profil"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_complet: Mapped[str] = mapped_column(String(120))
    localisation: Mapped[str] = mapped_column(String(120), default="")
    date_naissance: Mapped[date | None] = mapped_column(Date)
    afficher_age: Mapped[bool] = mapped_column(Boolean, default=False)
    permis: Mapped[str] = mapped_column(String(60), default="")
    interets_fr: Mapped[str] = mapped_column(Text, default="")
    interets_en: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str] = mapped_column(String(300), default="")
    github_url: Mapped[str] = mapped_column(String(300), default="")
    photo_fichier: Mapped[str | None] = mapped_column(String(120))
    ouvert_opportunites: Mapped[bool] = mapped_column(Boolean, default=True)
    # Privés : ne servent qu'au PDF complet de l'admin, jamais au public.
    telephone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))


class Entree(Base):
    """Un élément du parcours : poste, formation ou projet perso."""
    __tablename__ = "entree"
    __table_args__ = (_dans("type", TYPES_ENTREE), _dans("voie", VOIES))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20))
    voie: Mapped[str] = mapped_column(String(20), default="principale")
    intitule_fr: Mapped[str] = mapped_column(String(200))
    intitule_en: Mapped[str | None] = mapped_column(String(200))
    organisation: Mapped[str] = mapped_column(String(200), default="")
    via: Mapped[str | None] = mapped_column(String(200))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    lieu: Mapped[str] = mapped_column(String(120), default="")
    technos: Mapped[str] = mapped_column(String(400), default="")
    missions_fr: Mapped[str] = mapped_column(Text, default="")
    missions_en: Mapped[str | None] = mapped_column(Text)


class SoftSkill(Base):
    __tablename__ = "soft_skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_fr: Mapped[str] = mapped_column(String(120))
    nom_en: Mapped[str | None] = mapped_column(String(120))
    preuve_fr: Mapped[str | None] = mapped_column(Text)
    preuve_en: Mapped[str | None] = mapped_column(Text)


class Competence(Base):
    __tablename__ = "competence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_fr: Mapped[str] = mapped_column(String(120))
    nom_en: Mapped[str | None] = mapped_column(String(120))
    categorie_fr: Mapped[str | None] = mapped_column(String(120))
    categorie_en: Mapped[str | None] = mapped_column(String(120))


class Chiffre(Base):
    """Chiffre clé du bandeau (« 3 ans » · « d'expérience »)."""
    __tablename__ = "chiffre"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    valeur_fr: Mapped[str] = mapped_column(String(40))
    valeur_en: Mapped[str | None] = mapped_column(String(40))
    libelle_fr: Mapped[str] = mapped_column(String(120))
    libelle_en: Mapped[str | None] = mapped_column(String(120))


class Version(Base):
    """Une version du CV, servie sur /<slug>."""
    __tablename__ = "version"
    __table_args__ = (
        _dans("statut", STATUTS),
        # Traduction SQLite de SLUG : 1 à 40 caractères parmi a-z, 0-9 et « - ».
        CheckConstraint("length(slug) BETWEEN 1 AND 40 AND slug NOT GLOB '*[^a-z0-9-]*'",
                        name="ck_slug"),
        # Une seule version par défaut (servie sur /).
        Index("uq_version_par_defaut", "par_defaut", unique=True,
              sqlite_where=text("par_defaut = 1")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")
    par_defaut: Mapped[bool] = mapped_column(Boolean, default=False)
    titre_fr: Mapped[str] = mapped_column(String(200))
    titre_en: Mapped[str | None] = mapped_column(String(200))
    accroche_fr: Mapped[str] = mapped_column(Text, default="")
    accroche_en: Mapped[str | None] = mapped_column(Text)
    prochaine_mission_fr: Mapped[str] = mapped_column(String(200), default="")
    prochaine_mission_en: Mapped[str | None] = mapped_column(String(200))


class VersionElement(Base):
    """Élément du stock coché dans une version, avec son ordre.

    `element_id` désigne une ligne de la table indiquée par `type_element` ;
    `missions_*` surcharge les missions d'une entrée pour cette version.
    """
    __tablename__ = "version_element"
    __table_args__ = (
        _dans("type_element", TYPES_ELEMENT),
        UniqueConstraint("version_id", "type_element", "element_id",
                         name="uq_version_element"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("version.id", ondelete="CASCADE"))
    type_element: Mapped[str] = mapped_column(String(20))
    element_id: Mapped[int] = mapped_column(Integer)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    missions_fr: Mapped[str | None] = mapped_column(Text)
    missions_en: Mapped[str | None] = mapped_column(Text)


class DemandeContact(Base):
    """Demande « Demander l'accès », enregistrée avant tout envoi.

    `empreinte` : HMAC de l'IP avec le sel du jour (cv/journal.py), jamais l'IP.
    `erreur` : détail technique d'un échec d'envoi, visible dans l'admin seulement."""
    __tablename__ = "demande_contact"
    __table_args__ = (_dans("statut", STATUTS_DEMANDE),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, index=True)
    email: Mapped[str] = mapped_column(String(254))
    nom: Mapped[str] = mapped_column(String(100), default="")
    entreprise: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(Text)
    version_slug: Mapped[str] = mapped_column(String(40))
    langue: Mapped[str] = mapped_column(String(2))
    statut: Mapped[str] = mapped_column(String(20), default="en_attente")
    erreur: Mapped[str | None] = mapped_column(String(300))
    envoyee_le: Mapped[datetime | None] = mapped_column(DateTime)
    empreinte: Mapped[str] = mapped_column(String(32), index=True)


class Visite(Base):
    """Une page vue (ou un événement) du site public, sans IP ni cookie."""
    __tablename__ = "visite"
    __table_args__ = (_dans("type", TYPES_VISITE),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime, index=True)
    type: Mapped[str] = mapped_column(String(20))
    version_slug: Mapped[str] = mapped_column(String(40))
    langue: Mapped[str] = mapped_column(String(2))
    source: Mapped[str] = mapped_column(String(100))
    appareil: Mapped[str] = mapped_column(String(12))
    empreinte: Mapped[str] = mapped_column(String(32))


class SelJournalier(Base):
    """Sel aléatoire des empreintes, un par jour (UTC) ; celui de la veille est jeté."""
    __tablename__ = "sel_journalier"

    jour: Mapped[date] = mapped_column(Date, primary_key=True)
    valeur: Mapped[bytes] = mapped_column(LargeBinary(32))
