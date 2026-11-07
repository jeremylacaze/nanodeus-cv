"""Suivi des candidatures : un lien `?src=<source>` par entreprise, et ce qu'en ont
fait ses visiteurs, d'après le journal des visites (cv/journal.py)."""
import re
import unicodedata
from datetime import datetime

from babel.dates import format_date
from sqlalchemy import or_, select

from cv.admin.formulaires import MAX_TEXTE, Champ
from cv.models import LANGUES, STATUTS_CANDIDATURE, Candidature, Version, Visite

# Plus strict que le journal ([a-z0-9._-]) : sans point, une source ne peut pas se
# confondre avec le domaine d'un Referer (linkedin.com…).
SOURCE = re.compile(r"[a-z0-9-]{1,40}")
# Sources que le journal pose lui-même : une candidature ne peut pas les prendre.
RESERVEES = {"qr", "direct", "interne"}
ROBOT = "apercu_linkedin"
SUITES = {"pdf": "le PDF", "contact": "le formulaire de contact"}


def champs(session) -> tuple[Champ, ...]:
    """La liste des versions change : les champs sont construits à chaque requête."""
    slugs = tuple(session.scalars(select(Version.slug).order_by(Version.par_defaut.desc(),
                                                                Version.slug)))
    return (
        Champ("entreprise", "Entreprise", max=120, requis=True),
        Champ("poste", "Poste", max=160),
        Champ("version_slug", "Version envoyée", type="choix", choix=slugs, requis=True),
        Champ("langue", "Langue", type="choix", choix=LANGUES, requis=True),
        Champ("source", "Source du lien", max=40,
              aide="Ce qui suit ?src= : minuscules, chiffres et tirets. "
                   "Vide = tirée du nom de l'entreprise."),
        Champ("statut", "Statut", type="choix", choix=STATUTS_CANDIDATURE, requis=True),
        Champ("envoyee_le", "Envoyée le", type="date"),
        Champ("notes", "Notes", type="texte", max=MAX_TEXTE,
              aide="Privé : contact, relances, étapes de l'entretien…"),
    )


def source_proposee(entreprise: str, prises: set[str]) -> str:
    """« Société Générale & Fils » → « societe-generale-fils », suffixée si déjà prise."""
    ascii_ = unicodedata.normalize("NFKD", entreprise).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:34].strip("-")
    if not base or base in RESERVEES:
        base = "candidature"
    source, n = base, 1
    while source in prises:
        n += 1
        source = f"{base}-{n}"
    return source


def verifier(session, valeurs: dict, candidature: Candidature | None) -> dict[str, str]:
    """Pose la source proposée si elle est vide ; renvoie les erreurs par champ."""
    autres = set(session.scalars(select(Candidature.source).where(
        Candidature.id != (candidature.id if candidature else -1))))
    source = valeurs.get("source") or ""
    if not source:
        valeurs["source"] = source_proposee(valeurs.get("entreprise") or "", autres)
        return {}
    if not SOURCE.fullmatch(source):
        return {"source": "Minuscules, chiffres et tirets seulement (40 au plus)."}
    if source in RESERVEES:
        return {"source": "Source réservée au journal des visites."}
    if source in autres:
        return {"source": "Source déjà utilisée par une autre candidature."}
    return {}


def activite(session, candidature: Candidature) -> list[Visite]:
    """Visites venues du lien, plus celles du même visiteur le même jour (l'empreinte
    change chaque jour) : le PDF, ouvert depuis la page, arrive sans ?src=."""
    directes = list(session.scalars(select(Visite).where(Visite.source == candidature.source)))
    # Un robot partage son empreinte avec tous les robots : elle ne relie rien.
    empreintes = {v.empreinte for v in directes if v.type != ROBOT}
    conditions = [Visite.source == candidature.source]
    if empreintes:
        conditions.append(Visite.empreinte.in_(empreintes) & (Visite.type != ROBOT))
    return list(session.scalars(select(Visite).where(or_(*conditions))
                                .order_by(Visite.horodatage, Visite.id)))


def _jour(visite: Visite) -> str:
    return format_date(visite.horodatage, "EEEE d MMMM", locale="fr")


def phrase_activite(entreprise: str, evenements: list[Visite]) -> str:
    """« Acme a ouvert ton CV mardi 3 novembre, puis le PDF. »"""
    humains = [e for e in evenements if e.type != ROBOT]
    if not humains:
        if evenements:
            return (f"Le lien a été collé dans LinkedIn {_jour(evenements[0])} ; "
                    f"{entreprise} ne l'a pas encore ouvert.")
        return f"{entreprise} n'a pas encore ouvert ton CV."
    suites = []
    for e in humains[1:]:
        if e.type in SUITES and e.type != humains[0].type and SUITES[e.type] not in suites:
            suites.append(SUITES[e.type])
    phrase = f"{entreprise} a ouvert ton CV {_jour(humains[0])}"
    if suites:
        phrase += ", puis " + " et ".join(suites)
    jours = {e.horodatage.date() for e in humains}
    if len(jours) > 1:
        phrase += f". Revenu {len(jours) - 1} autre(s) jour(s), dernier : {_jour(humains[-1])}"
    return phrase + "."


def resumes(session, candidatures) -> dict[int, tuple[str, datetime | None]]:
    """Par candidature : la phrase d'activité et l'heure de sa dernière visite humaine."""
    resultat = {}
    for c in candidatures:
        evenements = activite(session, c)
        humains = [e for e in evenements if e.type != ROBOT]
        resultat[c.id] = (phrase_activite(c.entreprise, evenements),
                          humains[-1].horodatage if humains else None)
    return resultat


def dernieres_actives(session, nombre: int = 3) -> list[tuple[Candidature, str]]:
    """Les candidatures dont un visiteur a ouvert le lien, la plus récente d'abord."""
    candidatures = session.scalars(select(Candidature)).all()
    faits = resumes(session, candidatures)
    actives = sorted((c for c in candidatures if faits[c.id][1]),
                     key=lambda c: faits[c.id][1], reverse=True)
    return [(c, faits[c.id][0]) for c in actives[:nombre]]
