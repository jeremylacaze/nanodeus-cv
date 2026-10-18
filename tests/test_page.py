"""Page « pipeline » : contrat HTML, sections vides omises, échappement."""
import re

import pytest
from sqlalchemy import select

from cv.models import Entree, Profil, Version


@pytest.fixture
def client(fabrique_app):
    return fabrique_app().test_client()


def _html(client, url="/devops"):
    r = client.get(url)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_un_bouton_et_un_detail_par_job(client):
    html = _html(client)
    cles = re.findall(r'data-cle="(e\d+)"', html)
    assert len(cles) == 6          # 2 formations + 3 postes + ReadLN
    assert all(f'id="detail-{c}"' in html and f'aria-controls="detail-{c}"' in html
               for c in cles)
    # Sans JS tous les détails sont lisibles : aria-expanded n'est posé que par le JS.
    assert "aria-expanded" not in html
    assert 'class="job job--en-cours" data-cle="prochaine"' in html
    assert 'id="detail-prochaine"' in html
    assert "voie voie--parallele" in html


def test_details_lisibles_sans_js(client):
    for section in re.findall(r'<section class="detail"[^>]*>', _html(client)):
        assert "hidden" not in section


def test_poste_le_plus_recent_choisi_au_chargement(fabrique_app):
    app = fabrique_app()
    html = _html(app.test_client())
    with app.extensions["cv_sessions"]() as s:
        recent = s.scalars(select(Entree).where(Entree.intitule_fr == "Administrateur applicatif")).one()
    assert f'data-initial="e{recent.id}"' in html


def test_contenu_du_detail(client):
    html = _html(client)
    assert "Astek → SQLI · ADS" in html
    assert "Le tout déployé sous un environnement Kubernetes" in html
    assert "Objectif : Administrateur applicatif senior" in html
    assert "2020" in html and "2023" in html


def test_soft_skills_et_stack(client):
    html = _html(client)
    assert 'class="tests' in html and "2/2" in html
    assert "Porteur d&#39;idées" in html and "Kubernetes" in html
    assert "Jeux vidéo" in html


def test_version_vide_sans_cadre_vide(fabrique_app):
    def vide(s):
        s.add(Version(slug="vide", statut="publiee", titre_fr="Vide"))
    html = _html(fabrique_app(modifier=vide).test_client(), "/vide")
    assert "voie--parallele" not in html and 'class="tests' not in html
    assert 'class="pipeline' not in html and 'class="chiffres' not in html
    # Les centres d'intérêt viennent du profil : seuls eux restent dans « Stack ».
    assert "Kubernetes" not in html and "Jeux vidéo" in html
    assert 'data-action="demander-acces"' in html     # le contact reste possible


def test_html_du_contenu_echappe(fabrique_app):
    def script(s):
        e = s.scalars(select(Entree).where(Entree.intitule_fr == "Administrateur applicatif")).one()
        e.missions_fr = "<script>alert(1)</script>"
        e.intitule_fr = '<img src=x onerror="alert(2)">'
    html = _html(fabrique_app(modifier=script).test_client())
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "<img src=x" not in html


def test_secrets_masques(client):
    html = _html(client)
    assert html.count("***") == 2 and 'data-action="demander-acces"' in html
    assert 'class="btn-contact" href="/devops/contact" data-action="demander-acces"' in html


def _artefacts(html):
    return re.search(r'<section class="artefacts.*?</section>', html, re.S).group(0)


def test_artefacts_toujours_la_avec_le_pdf_en_premier(client):
    # Ni LinkedIn ni GitHub dans le profil amorcé : le PDF suffit à montrer la section.
    section = _artefacts(_html(client))
    premier = re.search(r'<a [^>]*href="([^"]+)"', section).group(1)
    assert premier == "/devops.pdf" and "CV · PDF" in section and "Télécharger" in section
    assert "linkedin" not in section.lower()


def test_artefacts_pdf_en_anglais(client):
    section = _artefacts(_html(client, "/en/devops"))
    assert 'href="/en/devops.pdf"' in section and "Download" in section


def test_artefacts_avec_lien(fabrique_app):
    def liens(s):
        s.get(Profil, 1).linkedin_url = "https://www.linkedin.com/in/exemple"
    section = _artefacts(_html(fabrique_app(modifier=liens).test_client()))
    assert section.index('href="/devops.pdf"') < section.index(
        'href="https://www.linkedin.com/in/exemple"')


def test_open_graph(client):
    html = _html(client)
    assert ('<meta property="og:title" content="Jeremy LACAZE-RUSQUES — '
            'Administrateur applicatif / DevOps">') in html
    assert 'property="og:description" content="Porteur d&#39;idées' in html
    assert '<meta property="og:url" content="http://localhost/devops">' in html
    assert 'property="og:locale" content="fr_FR"' in html
    assert 'property="og:locale" content="en_US"' in _html(client, "/en/devops")
    assert 'og:image' not in html


def test_og_url_sans_parametre(client):
    html = _html(client, "/devops?src=qr")
    assert '<meta property="og:url" content="http://localhost/devops">' in html


def test_script_et_feuille_de_style(client):
    html = _html(client)
    assert re.search(r'<script src="/static/pipeline\.js" nonce="[^"]+" defer>', html)
    assert 'href="/static/cv.css"' in html
    assert client.get("/static/pipeline.js").status_code == 200
    assert client.get("/static/cv.css").status_code == 200


@pytest.mark.parametrize("url", ["/devops", "/en/devops", "/inconnue"])
def test_aucun_attribut_style(client, url):
    assert " style=" not in client.get(url).get_data(as_text=True)


def test_page_anglaise(client):
    html = _html(client, "/en/devops")
    assert "Application administrator" in html and "Parcours" not in html
    assert "Request access" in html


def test_libelle_de_la_prochaine_mission_visible_sans_clic(client):
    # Spec § 4.1 : le libellé dépend de la version, lisible sur le graphe même.
    html = _html(client, "/lead-tech")
    bouton = re.search(r'<button[^>]*data-cle="prochaine".*?</button>', html, re.S).group(0)
    assert "Lead tech" in bouton


def test_bouton_contact_fonctionne_sans_js(client):
    html = _html(client, "/lead-tech")
    assert 'class="btn-contact" href="/lead-tech/contact" data-action="demander-acces"' in html
    assert 'href="/en/lead-tech/contact"' in _html(client, "/en/lead-tech")


def test_modale_presente_et_fermee(client):
    html = _html(client)
    assert re.search(r'<dialog[^>]*class="modale-contact"', html) and "<dialog open" not in html
    assert 'action="/devops/contact"' in html and 'name="site_web"' in html
    assert re.search(r'<script src="/static/contact\.js" nonce="[^"]+" defer>', html)
    assert 'action="/en/devops/contact"' in _html(client, "/en/devops")


def test_mention_de_confidentialite(client):
    assert "aucun cookie" in _html(client) and "no cookies" in _html(client, "/en/devops")


def test_mention_couvre_les_demandes_de_contact(client):
    # Une empreinte HMAC salée est pseudonyme, pas anonyme ; et les demandes de
    # contact, gardées jusqu'à suppression, doivent être annoncées.
    html, en = _html(client), _html(client, "/en/devops")
    assert "anonyme" not in html and "pseudonyme" in html
    assert "demande de contact" in html and "contact request" in en
