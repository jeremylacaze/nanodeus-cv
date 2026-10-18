"""Petites fabriques de contenu pour les tests."""
from datetime import date

from cv.models import (Chiffre, Competence, Entree, Profil, SoftSkill, Version,
                       VersionElement)


def profil(session, **champs):
    p = Profil(id=1, nom_complet="Jeremy LACAZE-RUSQUES", localisation="Toulouse, France",
               **champs)
    session.add(p)
    session.flush()
    return p


def entree(session, **champs):
    valeurs = dict(type="poste", voie="principale", intitule_fr="Poste",
                   debut=date(2024, 1, 1))
    valeurs.update(champs)
    e = Entree(**valeurs)
    session.add(e)
    session.flush()
    return e


def soft_skill(session, **champs):
    s = SoftSkill(**{"nom_fr": "Pédagogie", **champs})
    session.add(s)
    session.flush()
    return s


def competence(session, **champs):
    c = Competence(**{"nom_fr": "Docker", **champs})
    session.add(c)
    session.flush()
    return c


def chiffre(session, **champs):
    c = Chiffre(**{"valeur_fr": "3 ans", "libelle_fr": "d'expérience", **champs})
    session.add(c)
    session.flush()
    return c


def version(session, slug="devops", statut="publiee", par_defaut=False, elements=(), **champs):
    """`elements` : objets du stock à cocher, dans l'ordre voulu."""
    v = Version(slug=slug, statut=statut, par_defaut=par_defaut,
                **{"titre_fr": "Administrateur applicatif / DevOps", **champs})
    session.add(v)
    session.flush()
    for ordre, obj in enumerate(elements):
        cocher(session, v, obj, ordre)
    return v


_TYPES = {Entree: "entree", SoftSkill: "soft_skill", Competence: "competence",
          Chiffre: "chiffre"}


def cocher(session, v, obj, ordre=0, **surcharge):
    ve = VersionElement(version_id=v.id, type_element=_TYPES[type(obj)],
                        element_id=obj.id, ordre=ordre, **surcharge)
    session.add(ve)
    session.flush()
    return ve


class FauxEnvoi:
    """Transport d'email de test : garde les messages, ou lève `erreur` si posée."""

    def __init__(self, erreur: Exception | None = None):
        self.messages, self.erreur = [], erreur

    def envoyer(self, message):
        if self.erreur is not None:
            raise self.erreur
        self.messages.append(message)
