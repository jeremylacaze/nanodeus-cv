"""Journal des visites : empreinte du jour, sans IP ni cookie, purge à 6 mois."""
import logging
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

from cv import journal
from cv.journal import appareil, classer, empreinte, maintenant_utc, purger, sel_du_jour, source
from cv.models import SelJournalier, Visite

IP, UA = "203.0.113.77", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Mobile/15E148"
T = datetime(2026, 10, 18, 9, 0)


def _visites(app):
    with app.extensions["cv_sessions"]() as s:
        return s.scalars(select(Visite)).all()


def _visite(horodatage):
    return Visite(horodatage=horodatage, type="page", version_slug="devops", langue="fr",
                  source="direct", appareil="mobile", empreinte="0" * 32)


def test_visite_journalisee_sans_ip(fabrique_app):
    app = fabrique_app()
    app.test_client().get("/devops?src=QR", headers={"User-Agent": UA},
                          environ_base={"REMOTE_ADDR": IP})
    with app.extensions["cv_sessions"]() as s:
        v = s.scalars(select(Visite)).one()
        dump = "\n".join(s.connection().connection.iterdump())
    assert (v.type, v.version_slug, v.langue, v.source, v.appareil) == \
        ("page", "devops", "fr", "qr", "mobile")
    assert IP not in dump and len(v.empreinte) == 32


def test_accueil_journalise_la_version_par_defaut(fabrique_app):
    app = fabrique_app()
    app.test_client().get("/en/", headers={"User-Agent": "Mozilla/5.0 (X11; Linux)"})
    (v,) = _visites(app)
    assert (v.version_slug, v.langue, v.appareil, v.source) == \
        ("devops", "en", "ordinateur", "direct")


def test_meme_visiteur_meme_jour_meme_empreinte(session):
    a = empreinte(session, "secret", IP, UA, maintenant=T)
    assert a == empreinte(session, "secret", IP, UA, maintenant=T + timedelta(hours=5))
    assert a != empreinte(session, "secret", IP, "Autre navigateur", maintenant=T)
    assert a != empreinte(session, "autre-secret", IP, UA, maintenant=T)


def test_empreinte_change_le_lendemain(session):
    hier = empreinte(session, "secret", IP, UA, maintenant=T)
    assert hier != empreinte(session, "secret", IP, UA, maintenant=T + timedelta(days=1))
    assert [s.jour for s in session.scalars(select(SelJournalier))] == [(T + timedelta(days=1)).date()]


def test_purge_des_visites_de_plus_de_6_mois(session):
    session.add_all([_visite(T - timedelta(days=184)), _visite(T - timedelta(days=182))])
    session.commit()
    sel_du_jour(session, T)
    assert [v.horodatage for v in session.scalars(select(Visite))] == [T - timedelta(days=182)]


def test_purger_sans_visite(session):
    # Sans visite le lendemain, le sel de la veille resterait en base : la purge
    # planifiée le jette quand même, avec les visites de plus de 6 mois.
    session.add_all([SelJournalier(jour=(T - timedelta(days=1)).date(), valeur=b"h" * 32),
                     SelJournalier(jour=T.date(), valeur=b"j" * 32),
                     _visite(T - timedelta(days=184)), _visite(T - timedelta(days=182))])
    session.commit()
    purger(session, T)
    session.expire_all()
    assert [s.jour for s in session.scalars(select(SelJournalier))] == [T.date()]
    assert [v.horodatage for v in session.scalars(select(Visite))] == [T - timedelta(days=182)]


def test_commande_purger(fabrique_app):
    app = fabrique_app()
    hier = maintenant_utc() - timedelta(days=1)
    with app.extensions["cv_sessions"]() as s:
        s.add_all([SelJournalier(jour=hier.date(), valeur=b"h" * 32),
                   _visite(hier - timedelta(days=200))])
        s.commit()
    r = app.test_cli_runner().invoke(args=["purger"])
    assert r.exit_code == 0 and "Purge faite." in r.output
    with app.extensions["cv_sessions"]() as s:
        assert s.scalars(select(SelJournalier)).all() == []
        assert s.scalars(select(Visite)).all() == []

def test_sel_concurrent_relu(session, monkeypatch):
    # Un autre processus a créé le sel du jour entre la lecture et l'écriture.
    session.add(SelJournalier(jour=T.date(), valeur=b"x" * 32))
    session.commit()
    vrai_lire, appels = journal._lire_sel, []

    def lire(s, jour):
        appels.append(jour)
        return None if len(appels) == 1 else vrai_lire(s, jour)

    monkeypatch.setattr(journal, "_lire_sel", lire)
    assert sel_du_jour(session, T) == b"x" * 32


@pytest.mark.parametrize("ua, attendu", [
    ("LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient)", "apercu_linkedin"),
    ("Mozilla/5.0 (compatible; Googlebot/2.1)", None), ("curl/8.0", None), ("", None),
    ("python-requests/2.32", None), (UA, "page")])
def test_classer(ua, attendu):
    assert classer(ua) == attendu


def test_appareil():
    assert appareil(UA) == "mobile"
    assert appareil("Mozilla/5.0 (Linux; Android 14)") == "mobile"
    assert appareil("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "ordinateur"


@pytest.mark.parametrize("src, referer, attendu", [
    (None, "https://www.linkedin.com/feed/", "linkedin.com"), (None, None, "direct"),
    (None, "http://localhost/devops", "interne"), ("<script>", None, "script"),
    ("qr", "https://google.com/", "qr"), ("", "https://google.com/", "google.com"),
    (None, "pas une url", "direct")])
def test_source(fabrique_app, src, referer, attendu):
    app = fabrique_app()
    entetes = {"Referer": referer} if referer else {}
    with app.test_request_context("/devops", query_string={"src": src} if src is not None else {},
                                  headers=entetes):
        from flask import request
        assert source(request) == attendu


def test_robot_non_journalise_mais_page_servie(fabrique_app):
    app = fabrique_app()
    r = app.test_client().get("/devops", headers={"User-Agent": "Googlebot/2.1"})
    assert r.status_code == 200 and _visites(app) == []


def test_apercu_linkedin_journalise_a_part(fabrique_app):
    app = fabrique_app()
    app.test_client().get("/devops", headers={"User-Agent": "LinkedInBot/1.0"})
    assert [v.type for v in _visites(app)] == ["apercu_linkedin"]


def test_head_et_prechargement_non_journalises(fabrique_app):
    app = fabrique_app()
    c = app.test_client()
    c.head("/devops", headers={"User-Agent": UA})
    c.get("/devops", headers={"User-Agent": UA, "Sec-Purpose": "prefetch;prerender"})
    c.get("/devops", headers={"User-Agent": UA, "Purpose": "prefetch"})
    assert _visites(app) == []


def test_404_non_journalisee(fabrique_app):
    app = fabrique_app()
    app.test_client().get("/inconnue", headers={"User-Agent": UA})
    assert _visites(app) == []


def test_journal_en_panne_page_servie(fabrique_app, caplog):
    app = fabrique_app()
    with app.extensions["cv_moteur"].begin() as cx:
        cx.execute(text("DROP TABLE visite"))
    with caplog.at_level(logging.WARNING):
        r = app.test_client().get("/devops", headers={"User-Agent": UA},
                                  environ_base={"REMOTE_ADDR": IP})
    assert r.status_code == 200
    assert "journal des visites" in caplog.text and IP not in caplog.text
