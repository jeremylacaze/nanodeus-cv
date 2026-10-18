"""Pré-remplissage d'une base vide avec le CV actuel."""
from sqlalchemy import select

from cv import donnees_amorcage as d
from cv.models import (Chiffre, Competence, Entree, Profil, SoftSkill, Version,
                       VersionElement)


def amorcer(session) -> bool:
    """Remplit une base vide ; ne touche à rien si un profil existe déjà."""
    if session.scalars(select(Profil)).first() is not None:
        return False
    session.add(Profil(id=1, **d.PROFIL))
    elements = []
    for type_element, modele, lignes in (
            ("entree", Entree, d.ENTREES), ("soft_skill", SoftSkill, d.SOFT_SKILLS),
            ("competence", Competence, d.COMPETENCES), ("chiffre", Chiffre, d.CHIFFRES)):
        objets = [modele(**ligne) for ligne in lignes]
        session.add_all(objets)
        elements += [(type_element, obj) for obj in objets]
    versions = [Version(**v) for v in d.VERSIONS]
    session.add_all(versions)
    session.flush()
    # Les deux versions cochent tout, dans l'ordre du stock.
    for version in versions:
        session.add_all(VersionElement(version_id=version.id, type_element=t,
                                       element_id=obj.id, ordre=i)
                        for i, (t, obj) in enumerate(elements))
    session.commit()
    return True
