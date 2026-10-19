"""Admin : mise en page commune, libellés lisibles, tableau de bord et graphiques."""
import re
from datetime import date, datetime

import pytest
from sqlalchemy import select

from cv.admin.suivi import serie_jours
from cv.models import DemandeContact, Version
from tests.test_admin_visites import _visite

ORIGINE = {"Origin": "http://localhost"}


def _corps(admin, chemin):
    r = admin.get(chemin)
    assert r.status_code == 200, chemin
    return r.get_data(as_text=True)


def _id(admin, slug):
    with admin.application.extensions["cv_sessions"]() as s:
        return s.scalar(select(Version.id).where(Version.slug == slug))


def _pages(admin):
    return ["/admin/", "/admin/profil", "/admin/stock/parcours", "/admin/stock/parcours/nouveau",
            "/admin/versions", "/admin/versions/nouvelle", f"/admin/versions/{_id(admin, 'devops')}",
            "/admin/demandes", "/admin/visites"]


def _actifs(corps):
    return re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', corps)


@pytest.mark.parametrize("chemin, actif", [
    ("/admin/", "/admin/"),
    ("/admin/versions", "/admin/versions"),
    ("/admin/versions/nouvelle", "/admin/versions"),
    ("/admin/stock/parcours/nouveau", "/admin/stock/parcours"),
    ("/admin/stock/soft-skills", "/admin/stock/soft-skills"),
    ("/admin/visites", "/admin/visites"),
])
def test_un_seul_lien_actif_dans_la_navigation(admin, chemin, actif):
    assert _actifs(_corps(admin, chemin)) == [actif]


def test_aucun_style_en_ligne(admin):
    # La CSP n'autorise que les feuilles servies (style-src 'self').
    for chemin in _pages(admin):
        assert " style=" not in _corps(admin, chemin), chemin


def test_selecteur_de_theme_comme_le_site_public(admin):
    corps = _corps(admin, "/admin/")
    tete = corps[:corps.index("</head>")]
    assert re.search(r'<script src="/static/theme.js" nonce="[^"]+"></script>', tete)
    assert '<div class="theme" hidden>' in corps and 'data-action="theme"' in corps
    assert admin.get("/static/theme.js").status_code == 200


def test_lien_vers_le_site_public(admin):
    site = admin.application.config["CV"].URL_SITE
    assert f'href="{site}/"' in _corps(admin, "/admin/")


def test_statuts_lisibles(admin):
    corps = _corps(admin, "/admin/versions")
    assert ">Publiée<" in corps and ">Brouillon<" in corps
    assert ">publiee<" not in corps


def test_choix_affiches_avec_leur_libelle(admin):
    corps = _corps(admin, f"/admin/versions/{_id(admin, 'devops')}")
    assert '<option value="publiee" selected>Publiée</option>' in corps
    assert '<option value="non_listee">Non listée</option>' in corps
    corps = _corps(admin, "/admin/stock/parcours/nouveau")
    assert '<option value="parallele">Parallèle</option>' in corps


def test_champs_fr_et_en_cote_a_cote(admin):
    corps = _corps(admin, f"/admin/versions/{_id(admin, 'devops')}")
    paires = corps.split('<div class="paire">')[1:]
    assert len(paires) == 3  # titre, accroche, prochaine mission
    # La paire se ferme après le champ EN (deux </div> de suite : champ puis paire).
    fermeture = re.search(r"</div>\s*</div>", paires[0]).start()
    assert paires[0].index('name="titre_fr"') < paires[0].index('name="titre_en"') < fermeture


def test_paire_retablie_apres_une_erreur(admin):
    # Une erreur sur le champ FR ne casse pas le regroupement.
    r = admin.post("/admin/versions/nouvelle", headers=ORIGINE,
                   data={"slug": "x", "statut": "brouillon", "titre_fr": ""})
    corps = r.get_data(as_text=True)
    assert r.status_code == 400 and corps.count('<div class="paire">') == 3


def test_parcours_affiche_ses_dates(admin):
    corps = _corps(admin, "/admin/stock/parcours")
    assert re.search(r"\d{2}/\d{4} – (en cours|\d{2}/\d{4})", corps)


def test_compteur_de_composition(admin):
    corps = _corps(admin, f"/admin/versions/{_id(admin, 'devops')}")
    compteurs = re.findall(r'<span class="compte" data-compte>(\d+) / (\d+)</span>', corps)
    assert len(compteurs) == 4
    assert all(int(a) <= int(b) for a, b in compteurs)


def test_demandes_en_cartes(admin):
    with admin.application.extensions["cv_sessions"]() as s:
        for nom in ("Alice", "Bob"):
            s.add(DemandeContact(cree_le=datetime(2026, 10, 1), nom=nom,
                                 email=f"{nom.lower()}@ex.fr", message="Bonjour",
                                 version_slug="devops", langue="fr", empreinte="a" * 32,
                                 statut="echec", erreur="OSError"))
        s.commit()
    corps = _corps(admin, "/admin/demandes")
    assert corps.count('<article class="demande">') == 2
    assert ">Échec<" in corps


def test_tableau_de_bord(admin):
    from cv.journal import maintenant_utc
    with admin.application.extensions["cv_sessions"]() as s:
        for i in range(5):
            s.add(DemandeContact(nom=f"Personne {i}", email=f"p{i}@ex.fr", message="Bonjour",
                                 version_slug="devops", langue="fr", empreinte="a" * 32,
                                 cree_le=datetime(2026, 10, 1 + i)))
        _visite(s, maintenant_utc(), version="devops")
        s.commit()
    corps = _corps(admin, "/admin/")
    # Les versions et leurs aperçus, à un clic.
    assert f'href="/admin/versions/{_id(admin, "devops")}/apercu"' in corps
    # Les trois dernières demandes seulement, la plus récente d'abord.
    assert "Personne 4" in corps and "Personne 2" in corps and "Personne 1" not in corps
    assert corps.index("Personne 4") < corps.index("Personne 2")
    # Visiteurs des 14 derniers jours : une barre par jour.
    graphique = corps[corps.index('<svg class="histogramme"'):]
    graphique = graphique[:graphique.index("</svg>")]
    assert graphique.count("<rect") == 14


def test_graphique_des_visites(admin):
    corps = _corps(admin, "/admin/visites?du=2026-10-01&au=2026-10-10")
    graphique = corps[corps.index('<svg class="histogramme"'):]
    assert graphique[:graphique.index("</svg>")].count("<rect") == 10


def test_serie_jours_complete_les_trous():
    serie = serie_jours(date(2026, 10, 1), date(2026, 10, 4),
                        [(date(2026, 10, 3), 5), (date(2026, 10, 1), 2)])
    assert serie == [(date(2026, 10, 1), 2), (date(2026, 10, 2), 0),
                     (date(2026, 10, 3), 5), (date(2026, 10, 4), 0)]


def test_serie_jours_bornee():
    # Une période d'un an reste lisible : les jours au-delà de la borne sont coupés
    # par le début, la fin (aujourd'hui) reste.
    serie = serie_jours(date(2025, 1, 1), date(2026, 1, 1), [], borne=90)
    assert len(serie) == 90 and serie[-1][0] == date(2026, 1, 1)
