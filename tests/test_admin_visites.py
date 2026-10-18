"""Admin : visites filtrables et totaux."""
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from cv.admin.suivi import Filtres, lire_filtres, totaux, valeurs_presentes, visites
from cv.models import Visite

J = date(2026, 10, 18)


def _visite(session, quand: datetime, empreinte="a" * 32, type="page", version="devops",
            source="direct", langue="fr"):
    session.add(Visite(horodatage=quand, type=type, version_slug=version, langue=langue,
                       source=source, appareil="ordinateur", empreinte=empreinte))


def _a(jour: date, h=12, m=0) -> datetime:
    return datetime.combine(jour, time(h, m))


def _tout(**champs) -> Filtres:
    return Filtres(**{"du": J - timedelta(days=29), "au": J, "version": "", "source": "",
                      "type": "", **champs})


def test_totaux(session):
    for e in ("a", "a", "b"):
        _visite(session, _a(J), empreinte=e * 32)
    _visite(session, _a(J), empreinte="c" * 32, type="apercu_linkedin")
    _visite(session, _a(J - timedelta(days=1)), empreinte="a" * 32, type="pdf")
    session.commit()
    t = totaux(session, _tout())
    assert t.uniques_par_jour == [(J, 2), (J - timedelta(days=1), 1)]
    assert t.apercus_linkedin == 1 and t.total == 4


def test_par_source_trie(session):
    for source in ("linkedin.com", "qr", "qr", "direct", "linkedin.com", "qr"):
        _visite(session, _a(J), source=source)
    session.commit()
    assert totaux(session, _tout()).par_source == [("qr", 3), ("linkedin.com", 2), ("direct", 1)]


def test_par_source_egalite_par_nom(session):
    for source in ("zeta", "alpha"):
        _visite(session, _a(J), source=source)
    session.commit()
    assert totaux(session, _tout()).par_source == [("alpha", 1), ("zeta", 1)]


def test_filtres_version_source_type_periode(session):
    au = J - timedelta(days=3)
    _visite(session, _a(au, 23, 59), source="qr")                          # comptée
    _visite(session, _a(au + timedelta(days=1), 0, 0), source="qr")       # après « au »
    _visite(session, _a(au - timedelta(days=1)), source="qr", version="lead-tech")
    _visite(session, _a(au - timedelta(days=1)), source="direct", type="contact")
    _visite(session, _a(au - timedelta(days=40)), source="qr")             # avant « du »
    session.commit()
    filtres = _tout(au=au, du=au - timedelta(days=29))
    assert len(visites(session, filtres)) == 3
    assert [v.version_slug for v in visites(session, _tout(au=au, version="lead-tech"))] \
        == ["lead-tech"]
    assert len(visites(session, _tout(au=au, source="qr"))) == 2
    assert [v.type for v in visites(session, _tout(au=au, type="contact"))] == ["contact"]
    assert totaux(session, _tout(au=au, source="qr")).total == 2


def test_visites_recentes_d_abord_et_limite(session):
    for i in range(5):
        _visite(session, _a(J, 10 + i))
    session.commit()
    liste = visites(session, _tout(), limite=3)
    assert [v.horodatage.hour for v in liste] == [14, 13, 12]


@pytest.mark.parametrize("args, attendu", [
    ({}, (J - timedelta(days=29), J)),
    ({"du": "n'importe", "au": ""}, (J - timedelta(days=29), J)),
    ({"du": "2026-10-10", "au": "2026-10-01"}, (date(2026, 10, 1), date(2026, 10, 10))),
    ({"du": "2026-10-01T00:00"}, (J - timedelta(days=29), J))])
def test_lire_filtres_dates(args, attendu):
    f = lire_filtres(args, J)
    assert (f.du, f.au) == attendu


def test_lire_filtres_type_inconnu():
    assert lire_filtres({"type": "x"}, J).type == ""
    assert lire_filtres({"type": "pdf", "version": " devops ", "source": "qr"}, J) \
        == Filtres(J - timedelta(days=29), J, "devops", "qr", "pdf")


def test_valeurs_presentes(session):
    _visite(session, _a(J), version="lead-tech", source="qr")
    _visite(session, _a(J), version="devops", source="direct")
    _visite(session, _a(J), version="devops", source="qr")
    session.commit()
    assert valeurs_presentes(session) == (["devops", "lead-tech"], ["direct", "qr"])


def test_page_visites(admin):
    from cv.journal import maintenant_utc
    with admin.application.extensions["cv_sessions"]() as s:
        maintenant = maintenant_utc()
        _visite(s, maintenant, empreinte="d" * 32, version="devops")
        _visite(s, maintenant, empreinte="e" * 32, version="lead-tech", source="qr")
        s.commit()
        assert len(s.scalars(select(Visite)).all()) == 2
    r = admin.get("/admin/visites?version=devops")
    corps = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "d" * 32 not in corps and "e" * 32 not in corps
    assert '<option value="lead-tech"' in corps and '<option value="devops" selected' in corps
    tableau = corps[corps.index("<tbody>"):]
    assert "devops" in tableau and "lead-tech" not in tableau
    assert "200 dernières" not in corps


def test_page_visites_filtres_invalides(admin):
    assert admin.get("/admin/visites?du=x&au=2026-99-99&type=zzz").status_code == 200


@pytest.mark.parametrize("requete", ["au=9999-12-31", "du=9999-12-31", "du=0001-01-01"])
def test_dates_extremes_sans_erreur(admin, requete):
    # Le sélecteur de date laisse saisir l'an 9999 : au + 1 jour ne doit pas déborder.
    assert admin.get(f"/admin/visites?{requete}").status_code == 200


def test_apercus_hors_total_et_sources(session):
    # Comme l'accueil : un aperçu LinkedIn a son propre compteur, il ne fait pas une visite.
    _visite(session, _a(J), source="linkedin.com")
    _visite(session, _a(J), source="linkedin.com", type="apercu_linkedin")
    session.commit()
    t = totaux(session, _tout())
    assert (t.total, t.par_source, t.apercus_linkedin) == (1, [("linkedin.com", 1)], 1)
    t = totaux(session, _tout(type="apercu_linkedin"))
    assert (t.total, t.par_source) == (1, [("linkedin.com", 1)])
