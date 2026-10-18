"""Visites du site public : filtres et totaux pour l'admin."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import distinct, func, select

from cv.models import TYPES_VISITE, Visite

PERIODE = timedelta(days=29)  # 30 jours, aujourd'hui compris


@dataclass(frozen=True)
class Filtres:
    du: date
    au: date  # inclus
    version: str
    source: str
    type: str  # vide = tous


@dataclass
class Totaux:
    total: int
    uniques_par_jour: list[tuple[date, int]]
    par_source: list[tuple[str, int]]
    apercus_linkedin: int


def _date(texte: str | None) -> date | None:
    texte = (texte or "").strip()
    if len(texte) != 10:
        return None
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


def lire_filtres(args: Mapping[str, str], aujourd_hui: date) -> Filtres:
    """Filtres de la page ; une valeur illisible reprend sa valeur par défaut."""
    du = _date(args.get("du")) or aujourd_hui - PERIODE
    au = _date(args.get("au")) or aujourd_hui
    if du > au:
        du, au = au, du
    type_ = (args.get("type") or "").strip()
    return Filtres(du, au, (args.get("version") or "").strip(),
                   (args.get("source") or "").strip(), type_ if type_ in TYPES_VISITE else "")


def _conditions(filtres: Filtres) -> list:
    conditions = [Visite.horodatage >= datetime.combine(filtres.du, time()),
                  Visite.horodatage < datetime.combine(filtres.au + timedelta(days=1), time())]
    for colonne, valeur in ((Visite.version_slug, filtres.version),
                            (Visite.source, filtres.source), (Visite.type, filtres.type)):
        if valeur:
            conditions.append(colonne == valeur)
    return conditions


def visites(session, filtres: Filtres, limite: int = 200) -> list[Visite]:
    return list(session.scalars(select(Visite).where(*_conditions(filtres))
                                .order_by(Visite.horodatage.desc(), Visite.id.desc())
                                .limit(limite)))


def totaux(session, filtres: Filtres) -> Totaux:
    conditions = _conditions(filtres)
    total = session.scalar(select(func.count()).select_from(Visite).where(*conditions))
    jour = func.date(Visite.horodatage)
    # Un aperçu LinkedIn est un robot : il ne fait pas un visiteur.
    uniques = session.execute(
        select(jour, func.count(distinct(Visite.empreinte)))
        .where(*conditions, Visite.type != "apercu_linkedin")
        .group_by(jour).order_by(jour.desc())).all()
    nombre = func.count().label("nombre")
    par_source = session.execute(
        select(Visite.source, nombre).where(*conditions)
        .group_by(Visite.source).order_by(nombre.desc(), Visite.source)).all()
    apercus = session.scalar(select(func.count()).select_from(Visite)
                             .where(*conditions, Visite.type == "apercu_linkedin"))
    return Totaux(total, [(date.fromisoformat(j), n) for j, n in uniques],
                  [(s, n) for s, n in par_source], apercus)


def valeurs_presentes(session) -> tuple[list[str], list[str]]:
    """Slugs et sources déjà vus, pour les listes déroulantes des filtres."""
    return tuple(list(session.scalars(select(colonne).distinct().order_by(colonne)))
                 for colonne in (Visite.version_slug, Visite.source))
