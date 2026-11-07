"""Admin : suivi des candidatures (lien ?src= par candidature, QR, visites)."""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from cv.admin.candidatures import activite, phrase_activite, source_proposee
from cv.models import Candidature, Visite

ORIGINE = {"Origin": "http://localhost"}
OK = {"entreprise": "Acme Industries", "poste": "Ingénieur DevOps", "version_slug": "devops",
      "langue": "fr", "source": "acme", "statut": "envoyee", "envoyee_le": "2026-11-02",
      "notes": "Contact : RH"}


def _session(admin):
    return admin.application.extensions["cv_sessions"]()


def _creer(admin, **champs):
    r = admin.post("/admin/candidatures/nouvelle", headers=ORIGINE, data={**OK, **champs})
    assert r.status_code == 303, r.get_data(as_text=True)
    with _session(admin) as s:
        return s.scalars(select(Candidature).order_by(Candidature.id.desc())).first().id


def _visite(s, quand, type="page", source="acme", empreinte="e1", appareil="ordinateur"):
    s.add(Visite(horodatage=quand, type=type, version_slug="devops", langue="fr",
                 source=source, appareil=appareil, empreinte=empreinte))


def test_navigation_et_liste_vide(admin):
    html = admin.get("/admin/").get_data(as_text=True)
    assert 'href="/admin/candidatures"' in html
    page = admin.get("/admin/candidatures")
    assert page.status_code == 200 and "Aucune candidature" in page.get_data(as_text=True)
    assert admin.get("/admin/candidatures/nouvelle").status_code == 200


def test_creer_puis_lister(admin):
    id_ = _creer(admin)
    with _session(admin) as s:
        c = s.get(Candidature, id_)
        assert (c.entreprise, c.source, c.envoyee_le) == ("Acme Industries", "acme", date(2026, 11, 2))
    html = admin.get("/admin/candidatures").get_data(as_text=True)
    assert "Acme Industries" in html and "Ingénieur DevOps" in html and "Envoyée" in html


def test_lien_et_qr_de_la_candidature(admin):
    id_ = _creer(admin)
    html = admin.get(f"/admin/candidatures/{id_}").get_data(as_text=True)
    assert "https://cv.nanodeus.com/devops?src=acme" in html
    for fmt, type_mime in (("svg", "image/svg+xml"), ("png", "image/png")):
        r = admin.get(f"/admin/candidatures/{id_}/qr.{fmt}")
        assert r.status_code == 200 and r.mimetype == type_mime
    r = admin.get(f"/admin/candidatures/{id_}/qr.png?telecharger=1")
    assert 'filename="qr-acme.png"' in r.headers["Content-Disposition"]
    assert admin.get(f"/admin/candidatures/{id_}/qr.gif").status_code == 404


def test_lien_en_anglais(admin):
    id_ = _creer(admin, langue="en", source="globex")
    assert "https://cv.nanodeus.com/en/devops?src=globex" in admin.get(
        f"/admin/candidatures/{id_}").get_data(as_text=True)


@pytest.mark.parametrize("source", ["Acme", "a b", "acme!", "x" * 41, "qr", "linkedin.com",
                                    "direct", "interne"])
def test_source_invalide_ou_reservee(admin, source):
    r = admin.post("/admin/candidatures/nouvelle", headers=ORIGINE, data={**OK, "source": source})
    assert r.status_code == 400


def test_source_unique(admin):
    _creer(admin)
    r = admin.post("/admin/candidatures/nouvelle", headers=ORIGINE, data=OK)
    assert r.status_code == 400 and "déjà utilisée" in r.get_data(as_text=True)


def test_source_proposee_depuis_l_entreprise(admin):
    id_ = _creer(admin, source="", entreprise="Société Générale & Fils")
    with _session(admin) as s:
        assert s.get(Candidature, id_).source == "societe-generale-fils"
    # Même entreprise une seconde fois : un suffixe garde la source unique.
    id2 = _creer(admin, source="", entreprise="Société Générale & Fils")
    with _session(admin) as s:
        assert s.get(Candidature, id2).source == "societe-generale-fils-2"


def test_source_proposee_bornee():
    assert len(source_proposee("x" * 100, set())) <= 40
    assert source_proposee("!!!", set()) == "candidature"


@pytest.mark.parametrize("champ, valeur", [("entreprise", ""), ("version_slug", "inconnue"),
                                           ("langue", "de"), ("statut", "perdue"),
                                           ("envoyee_le", "02/11/2026")])
def test_champs_invalides(admin, champ, valeur):
    r = admin.post("/admin/candidatures/nouvelle", headers=ORIGINE, data={**OK, champ: valeur})
    assert r.status_code == 400


def test_modifier(admin):
    id_ = _creer(admin)
    r = admin.post(f"/admin/candidatures/{id_}", headers=ORIGINE,
                   data={**OK, "statut": "entretien"})
    assert r.status_code == 303
    with _session(admin) as s:
        assert s.get(Candidature, id_).statut == "entretien"


def test_modifier_garde_sa_propre_source(admin):
    id_ = _creer(admin)
    assert admin.post(f"/admin/candidatures/{id_}", headers=ORIGINE, data=OK).status_code == 303


def test_supprimer(admin):
    id_ = _creer(admin)
    r = admin.post(f"/admin/candidatures/{id_}/supprimer", headers=ORIGINE)
    assert r.status_code == 303 and "ok=supprime" in r.headers["Location"]
    with _session(admin) as s:
        assert s.get(Candidature, id_) is None


def test_inconnue_404(admin):
    assert admin.get("/admin/candidatures/999").status_code == 404
    assert admin.post("/admin/candidatures/999/supprimer", headers=ORIGINE).status_code == 404


def test_activite_suit_le_visiteur_dans_la_journee(admin):
    id_ = _creer(admin)
    with _session(admin) as s:
        _visite(s, datetime(2026, 11, 3, 9, 14))
        # Même visiteur, même jour : le PDF arrive sans ?src= (lien interne).
        _visite(s, datetime(2026, 11, 3, 9, 16), type="pdf", source="interne")
        # Un autre visiteur, sans lien avec la candidature.
        _visite(s, datetime(2026, 11, 3, 9, 20), type="pdf", source="interne", empreinte="e2")
        _visite(s, datetime(2026, 11, 3, 8, 0), type="apercu_linkedin", empreinte="bot")
        s.commit()
        evenements = activite(s, s.get(Candidature, id_))
    assert [e.type for e in evenements] == ["apercu_linkedin", "page", "pdf"]
    html = admin.get(f"/admin/candidatures/{id_}").get_data(as_text=True)
    assert "a ouvert ton CV" in html and "puis le PDF" in html


def test_phrase_d_activite():
    def v(heure, type):
        return Visite(horodatage=datetime(2026, 11, 3, heure), type=type, source="acme",
                      version_slug="devops", langue="fr", appareil="mobile", empreinte="e")
    assert phrase_activite("Acme", []) == "Acme n'a pas encore ouvert ton CV."
    assert phrase_activite("Acme", [v(9, "page")]) == "Acme a ouvert ton CV mardi 3 novembre."
    assert phrase_activite("Acme", [v(9, "page"), v(9, "pdf")]) == (
        "Acme a ouvert ton CV mardi 3 novembre, puis le PDF.")
    assert phrase_activite("Acme", [v(9, "page"), v(9, "contact"), v(9, "pdf")]) == (
        "Acme a ouvert ton CV mardi 3 novembre, puis le formulaire de contact et le PDF.")
    # Seul l'aperçu LinkedIn : le lien a été collé, personne n'a cliqué.
    assert phrase_activite("Acme", [v(9, "apercu_linkedin")]) == (
        "Le lien a été collé dans LinkedIn mardi 3 novembre ; Acme ne l'a pas encore ouvert.")


def test_liste_resume_l_activite(admin):
    _creer(admin)
    with _session(admin) as s:
        _visite(s, datetime(2026, 11, 3, 9, 14))
        s.commit()
    html = admin.get("/admin/candidatures").get_data(as_text=True)
    assert "a ouvert ton CV" in html


def test_tableau_de_bord_montre_la_derniere_activite(admin):
    _creer(admin)
    with _session(admin) as s:
        _visite(s, datetime(2026, 11, 3, 9, 14))
        s.commit()
    html = admin.get("/admin/").get_data(as_text=True)
    assert "Acme Industries" in html and "a ouvert ton CV" in html


def test_echappement(admin):
    id_ = _creer(admin, entreprise="<script>alert(1)</script>", notes="<b>x</b>")
    html = admin.get(f"/admin/candidatures/{id_}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "<b>x</b>" not in html


def test_route_absente_du_public(fabrique_app):
    assert fabrique_app().test_client().get("/admin/candidatures").status_code == 404
