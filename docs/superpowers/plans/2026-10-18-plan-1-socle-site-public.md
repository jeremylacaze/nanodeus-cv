# Plan 1 — Socle et site public en lecture · Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un site Flask qui affiche, à partir d'une base SQLite pré-remplie avec le CV
actuel, la page « pipeline » validée (bandeau, parcours interactif, tests soft skills,
bas de page) en FR et EN, sur ordinateur et téléphone, sans cookie et sans jamais
exposer téléphone ni email.

**Architecture:** Paquet Python `cv/` : modèles SQLAlchemy + Alembic sur SQLite (WAL),
un module de domaine pur qui assemble une `VueCV` (dataclass **sans** champ de
coordonnées) pour une version et une langue, un blueprint public Jinja, un JS sans
framework pour l'interactivité du pipeline. L'app est créée par `create_app(role)` ;
ce plan ne construit que le rôle `public`.

**Tech Stack:** Python 3.12 dans l’image (3.14 en local sur le Mac, code compatible des deux ; `ruff` en `target-version = "py312"`), Flask 3.1, SQLAlchemy 2.1, Alembic, Flask-Babel / Babel,
pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-18-cv-pipeline-design.md` (lire § 1, 3, 4,
10, 12 et l'annexe A ; maquette `docs/maquettes/pipeline-valide.html`).

### Découpage du projet en plans

La spec couvre quatre sous-systèmes ; chacun aura son plan, écrit une fois le
précédent terminé (pour partir du code réel) :

1. **Ce plan** — socle, modèle de contenu, amorçage, site public en lecture.
2. Contact (modale, Brevo/SMTP, anti-abus) + journal des visites + mention de
   confidentialité.
3. Admin Tailscale (édition, versions, photo, QR, PDF public et complet).
4. Livraison : Dockerfile, CI GitHub (dépôt public), déploiement netcup, sauvegarde,
   runbook DNS/Brevo.

## Global Constraints

- **Règle n° 1 :** téléphone et email du profil n'apparaissent dans **aucune** réponse
  publique (HTML, en-têtes, erreurs). `VueCV` n'a pas de champ pour eux.
- **Dépôt public :** ni téléphone, ni email, ni photo, ni IP serveur dans le code, les
  données d'amorçage ou l'historique.
- **Aucun cookie** sur le site public (aucun `Set-Cookie`, pas même de session).
- Langue portée par l'URL : `/…` = FR, `/en/…` = EN. Champ EN vide → repli sur le FR.
- Version `brouillon` → 404 ; `non_listee` → `noindex` ; une seule version `par_defaut`.
- CSP **bloquante dès le départ** : `script-src 'self' 'nonce-…'`, pas d'attribut
  `style=` ni de script inline sans nonce dans les templates.
- Thème de référence (spec § 4.3) : fond `#0d1117`, cartes `#161b22`, bordures
  `#30363d`, vert `#3fb950`, jaune `#d29922`, sélection `#58a6ff` ; animation pulsante
  coupée sous `prefers-reduced-motion`.
- Code, commentaires, commits en **français** ; commits `FEAT(scope):`, `FIX(scope):`,
  `CHORE:`, `DOCS:` ; tout texte visible passe par `_()` (msgid français).
- Versions des dépendances : reprendre celles de `~/Documents/Git/tradln/requirements.txt`
  et `requirements-dev.txt` (Flask 3.1.3, SQLAlchemy 2.1.1, alembic 1.20.0,
  Flask-Babel 4.0.0, Babel 2.18.0, pytest, ruff).
- Travail sur la branche `feat/socle-site-public` créée depuis `develop`.

## Review Focus

1. **Version sans contenu** (aucune entrée, soft skill ou chiffre coché) → la page
   s'affiche, les sections vides sont omises, pas de cadre vide. *(test Task 6)*
2. **Dates incohérentes** (fin avant début, début dans le futur) → durée au minimum
   « 1 m », jamais négative ni plantage. *(test Task 2)*
3. **HTML dans le contenu** (`<script>` tapé plus tard dans l'admin) → échappé par
   Jinja, jamais interprété. *(test Task 6)*
4. **Champ vide en FR et en EN** → chaîne vide, jamais `None` affiché. *(test Task 3)*
5. **Textes très longs** (intitulé de 120 caractères, mission de 2000) → aucun
   défilement horizontal à 375 px. *(vérification manuelle Task 6)*

---

### Task 1: Socle du dépôt, base SQLite et modèles

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `ruff.toml` (copie de celui de
  ReadLN, sans les exclusions propres à ReadLN), `.gitignore` (`.venv/`, `data/`,
  `__pycache__/`, `*.mo`), `pytest.ini`
- Create: `cv/__init__.py`, `cv/config.py`, `cv/db.py`, `cv/models.py`
- Create: `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_contenu.py`
- Test: `tests/conftest.py`, `tests/test_db.py`

**Interfaces:**
- Produces:
  - `cv.config.Config` : `DATA_DIR: Path` (env `CV_DATA_DIR`, défaut `./data`),
    `ROLE: str` (env `CV_ROLE`, `public`|`admin`, défaut `public`), `SECRET_KEY`,
    `TRUST_PROXY: bool` (env `TRUST_PROXY=1`), propriété `DATABASE_URL` =
    `sqlite:///<DATA_DIR>/cv.sqlite3`.
  - `cv.db.creer_moteur(url: str) -> Engine` — pose `PRAGMA journal_mode=WAL` et
    `PRAGMA foreign_keys=ON` à chaque connexion. `cv.db.Base` (DeclarativeBase),
    `cv.db.fabrique_sessions(engine) -> sessionmaker`.
  - `cv.models` (noms de colonnes exacts, tous les textes traduisibles en paire
    `_fr` / `_en`, `_en` nullable) :
    - `Profil` (ligne unique `id=1`) : `nom_complet`, `localisation`,
      `date_naissance: date|None`, `afficher_age: bool=False`, `permis`,
      `interets_fr/_en` (une valeur par ligne), `linkedin_url`, `github_url`,
      `photo_fichier: str|None`, `ouvert_opportunites: bool=True`,
      **`telephone`, `email`** (privés).
    - `Entree` : `type` (`poste`|`formation`|`projet`), `voie`
      (`principale`|`parallele`), `intitule_fr/_en`, `organisation`, `via: str|None`,
      `debut: date`, `fin: date|None` (None = en cours), `lieu`, `technos`,
      `missions_fr/_en` (une mission par ligne).
    - `SoftSkill` : `nom_fr/_en`, `preuve_fr/_en` (nullable).
    - `Competence` : `nom_fr/_en`, `categorie_fr/_en` (nullable).
    - `Chiffre` : `valeur_fr/_en`, `libelle_fr/_en`.
    - `Version` : `slug` (unique, `^[a-z0-9-]{1,40}$`), `statut`
      (`brouillon`|`publiee`|`non_listee`), `par_defaut: bool`, `titre_fr/_en`,
      `accroche_fr/_en`, `prochaine_mission_fr/_en`. **Index unique partiel** sur
      `par_defaut` `WHERE par_defaut = 1`.
    - `VersionElement` : `version_id` (FK, cascade), `type_element`
      (`entree`|`soft_skill`|`competence`|`chiffre`), `element_id: int`,
      `ordre: int`, `missions_fr/_en` (surcharge, nullable, n'a de sens que pour
      `entree`). Unique (`version_id`, `type_element`, `element_id`).
- `tests/conftest.py` fixture `session` : base SQLite dans `tmp_path`, schéma créé par
  `Base.metadata.create_all`.

- [ ] **Step 1: Créer la branche, le venv et les fichiers de dépendances**

Run: `git switch -c feat/socle-site-public && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
Expected: installation sans erreur (`requirements-dev.txt` inclut `-r requirements.txt`).

- [ ] **Step 2: Écrire les tests qui échouent**

```python
# tests/test_db.py
def test_wal_et_cles_etrangeres_actifs(session):
    assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1

def test_une_seule_version_par_defaut(session):
    session.add_all([Version(slug="a", statut="publiee", par_defaut=True, titre_fr="A"),
                     Version(slug="b", statut="publiee", par_defaut=True, titre_fr="B")])
    with pytest.raises(IntegrityError):
        session.flush()

def test_supprimer_version_supprime_ses_elements(session): ...
    # VersionElement d'une version supprimée → plus aucune ligne

def test_migrations_alignees_sur_les_modeles(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
    cfg = alembic.config.Config("alembic.ini")
    alembic.command.upgrade(cfg, "head")
    alembic.command.check(cfg)   # lève si un modèle diverge de la chaîne
```

- [ ] **Step 3: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: cv`).

- [ ] **Step 4: Implémenter `cv/config.py`, `cv/db.py`, `cv/models.py`, `alembic/env.py` (URL lue dans `Config().DATABASE_URL`, `render_as_batch=True` pour SQLite) et générer `0001_contenu.py` par `alembic revision --autogenerate`, relue à la main**

- [ ] **Step 5: Vérifier le succès**

Run: `.venv/bin/pytest tests/test_db.py -v && .venv/bin/ruff check .`
Expected: 4 passed, ruff sans remarque.

- [ ] **Step 6: Commit**

```bash
git add . && git commit -m "FEAT(socle): base SQLite, modèles de contenu et migration initiale"
```

---

### Task 2: Durées et périodes

**Files:**
- Create: `cv/durees.py`
- Test: `tests/test_durees.py`

**Interfaces:**
- Produces:
  - `duree(debut: date, fin: date|None, lang: str, aujourd_hui: date|None = None) -> str`
    — mois = `(fin.année − debut.année) × 12 + (fin.mois − debut.mois)`, **minimum 1** ;
    `fin=None` → `aujourd_hui` (défaut `date.today()`).
  - `periode(debut: date, fin: date|None, lang: str) -> str` — mois abrégé + année
    via `babel.dates.format_date(d, "MMM y", locale=lang)`, séparateur ` → `, fin
    absente → `aujourd'hui` / `present` (passer par `_()`/le catalogue).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
@pytest.mark.parametrize("debut,fin,fr,en", [
    (date(2023,10,1), date(2024,2,1), "4 m", "4 mo"),
    (date(2024,2,1), date(2025,5,1), "1 an 3 m", "1 yr 3 mo"),
    (date(2024,1,1), date(2025,1,1), "1 an", "1 yr"),
    (date(2023,1,1), date(2025,1,1), "2 ans", "2 yrs"),
    (date(2025,5,1), date(2025,5,1), "1 m", "1 mo"),     # même mois
    (date(2025,5,1), date(2024,1,1), "1 m", "1 mo"),     # fin avant début (Review Focus 2)
])
def test_duree(debut, fin, fr, en):
    assert duree(debut, fin, "fr") == fr
    assert duree(debut, fin, "en") == en

def test_duree_en_cours_utilise_aujourdhui():
    assert duree(date(2025,5,1), None, "fr", aujourd_hui=date(2026,10,18)) == "1 an 5 m"

def test_periode():
    assert periode(date(2024,2,1), date(2025,5,1), "fr") == "févr. 2024 → mai 2025"
    assert periode(date(2024,2,1), date(2025,5,1), "en") == "Feb 2024 → May 2025"
    assert periode(date(2025,5,1), None, "fr") == "mai 2025 → aujourd'hui"
```

- [ ] **Step 2: Vérifier l'échec** — Run: `.venv/bin/pytest tests/test_durees.py -v` · Expected: FAIL (import).

- [ ] **Step 3: Implémenter `duree` et `periode` dans `cv/durees.py`**

`periode` en EN doit renvoyer `present` sans catalogue compilé : utiliser un petit
dictionnaire `{"fr": "aujourd'hui", "en": "present"}` (le contenu des dates n'est pas
de l'interface Babel). Même principe pour les unités `m`/`an`/`ans` vs
`mo`/`yr`/`yrs`.

- [ ] **Step 4: Vérifier le succès** — Run: `.venv/bin/pytest tests/test_durees.py -v` · Expected: PASS.

- [ ] **Step 5: Commit** — `git add cv/durees.py tests/test_durees.py && git commit -m "FEAT(contenu): calcul des durées et des périodes"`

---

### Task 3: Assemblage de la vue d'une version

**Files:**
- Create: `cv/vue.py`
- Test: `tests/test_vue.py` (+ fabriques de données dans `tests/fabriques.py`)

**Interfaces:**
- Consumes: modèles (Task 1), `duree`/`periode` (Task 2).
- Produces:
  - `champ(obj, nom: str, lang: str) -> str` — `getattr(obj, f"{nom}_{lang}")`, repli
    sur `_fr` si vide/None, `""` si les deux sont vides.
  - Dataclasses gelées :
    - `Job(cle: str, type: str, voie: str, intitule: str, organisation: str, via: str, periode: str, duree: str, missions: list[str], technos: str, en_cours: bool)` — `cle` = `f"e{id}"`.
    - `VueCV(slug, lang, noindex: bool, nom, titre, accroche, localisation, age: int|None, ouvert: bool, photo_url: str|None, chiffres: list[tuple[str,str]], formations: list[Job], postes: list[Job], projets: list[Job], prochaine_mission: str, soft_skills: list[tuple[str,str]], competences: dict[str, list[str]], interets: list[str], linkedin_url: str, github_url: str)`.
      **Aucun champ téléphone ni email.**
  - `assembler_vue(session, slug: str|None, lang: str, aujourd_hui: date|None = None) -> VueCV|None`
    — `slug=None` → version `par_defaut` ; `None` si version absente ou
    `brouillon`. Seuls les éléments cochés (`VersionElement`) sont repris.
    **Entrées : toujours chronologiques** (`debut` croissant, le pipeline est une
    frise). **Soft skills, compétences, chiffres : ordre `VersionElement.ordre`.**
    Répartition : `type=formation` → `formations` ; sinon `voie=principale` →
    `postes`, `parallele` → `projets`. Missions : surcharge
    de la version si non vide, sinon celles de l'entrée ; une ligne = une mission,
    lignes vides ignorées. Soft skill sans preuve (après repli) **exclue**. `age`
    seulement si `afficher_age` et `date_naissance`. `photo_url` toujours `None` dans
    ce plan (le plan 3 la branche). `noindex = statut == "non_listee"`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_vuecv_na_aucun_champ_de_coordonnees():
    noms = {f.name for f in dataclasses.fields(VueCV)}
    assert not noms & {"telephone", "email", "phone"}

def test_version_par_defaut_et_brouillon(session):          # fabriques : defaut publiee + "brouillon"
    assert assembler_vue(session, None, "fr").slug == "devops"
    assert assembler_vue(session, "brouillon", "fr") is None
    assert assembler_vue(session, "inconnue", "fr") is None

def test_repli_francais_si_anglais_vide(session):
    # Entree intitule_fr="Ingénieur DevOps", intitule_en=None
    assert assembler_vue(session, "devops", "en").postes[0].intitule == "Ingénieur DevOps"

def test_champ_vide_partout_donne_chaine_vide(): # Review Focus 4
    assert champ(SimpleNamespace(titre_fr=None, titre_en=""), "titre", "en") == ""

def test_soft_skill_sans_preuve_exclue(session): ...       # "Autonomie" sans preuve absente
def test_surcharge_des_missions_par_version(session): ...  # missions_fr surchargées l'emportent
def test_ordre_et_repartition_des_voies(session): ...      # formation→formations, parallele→projets, postes triés par debut même si ordre inverse
def test_ordre_des_soft_skills_suit_la_version(session): ...  # ordre 2,1 → affichées dans cet ordre
def test_age_masque_par_defaut(session): ...               # date_naissance posée, afficher_age=False → age None
def test_non_listee_noindex(session): ...
```

- [ ] **Step 2: Vérifier l'échec** — Run: `.venv/bin/pytest tests/test_vue.py -v` · Expected: FAIL.
- [ ] **Step 3: Implémenter `champ`, `Job`, `VueCV`, `assembler_vue` dans `cv/vue.py`**
- [ ] **Step 4: Vérifier le succès** — Run: `.venv/bin/pytest tests/test_vue.py -v` · Expected: PASS.
- [ ] **Step 5: Commit** — `FEAT(contenu): assemblage de la vue d'une version`

---

### Task 4: Amorçage depuis le CV actuel

**Files:**
- Create: `cv/amorcage.py` (logique), `cv/donnees_amorcage.py` (données)
- Test: `tests/test_amorcage.py`

**Interfaces:**
- Consumes: modèles (Task 1).
- Produces: `amorcer(session) -> bool` — `False` et **aucune écriture** si un `Profil`
  existe déjà ; sinon insère tout et renvoie `True`. Commande CLI
  `flask --app cv.app amorcer` branchée en Task 5.

Données (`cv/donnees_amorcage.py`) — FR **verbatim de l'annexe A de la spec** ;
EN = premier jet traduit par l'implémenteur :
- Profil : `nom_complet="Jeremy LACAZE-RUSQUES"`, `localisation="Toulouse, France"`,
  `permis="B / A2"`, intérêts musique / jeux vidéo / dessin, `date_naissance=None`,
  `afficher_age=False`, **`telephone=None`, `email=None`**, liens vides.
- Entrées : les 3 postes (dates au 1er du mois : 2023-10 → 2024-02, 2024-02 → 2025-05,
  2025-05 → en cours ; `via="Astek"` pour les deux premiers), les 2 formations
  (`debut=fin=` année au 1er septembre/juin, *au constructeur*), ReadLN
  (`type=projet`, `voie=parallele`, `debut=2025-01-01` à confirmer par Jeremy dans
  l'admin, en cours).
- Soft skills : « Porteur d'idées » (preuve : « A imaginé, construit et mis en
  production ReadLN seul. »), « Pédagogie » (preuve : « Support direct et
  accompagnement des utilisateurs Jira / Confluence. »), « Autonomie » (**preuve
  vide**).
- Compétences de l'annexe A, catégories `Ops` / `Développement` / `Langues`.
- Chiffres : `3 ans` · d'expérience ; `5` · outils administrés sur Kubernetes ; `1` ·
  projet perso en production ; `Bac+5` · Mastère Ynov.
- Versions : `devops` (`publiee`, `par_defaut`, titre « Administrateur applicatif /
  DevOps », prochaine mission « Administrateur applicatif senior ») et `lead-tech`
  (`non_listee`, titre « Administrateur applicatif / DevOps → Lead tech », prochaine
  mission « Lead tech ») ; accroche commune « Porteur d'idées, autonome, je fais
  grandir les équipes avec pédagogie. » ; les deux cochent tous les éléments.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_amorcer_base_vide(session):
    assert amorcer(session) is True
    vue = assembler_vue(session, None, "fr")
    assert vue.slug == "devops" and len(vue.postes) == 3 and len(vue.projets) == 1
    assert [n for n, _ in vue.soft_skills] == ["Porteur d'idées", "Pédagogie"]

def test_amorcer_ne_reecrit_jamais(session):
    amorcer(session); session.get(Profil, 1).localisation = "Paris"; session.commit()
    assert amorcer(session) is False
    assert session.get(Profil, 1).localisation == "Paris"

def test_donnees_amorcage_sans_coordonnees():
    source = Path("cv/donnees_amorcage.py").read_text()
    assert "@" not in source and not re.search(r"0[67](\s?\d{2}){4}", source)

def test_anglais_rempli_pour_chaque_texte(session): ...  # aucun *_en vide hors preuve d'Autonomie
```

- [ ] **Step 2: Vérifier l'échec** — Run: `.venv/bin/pytest tests/test_amorcage.py -v` · Expected: FAIL.
- [ ] **Step 3: Implémenter `amorcer` et les données**
- [ ] **Step 4: Vérifier le succès** — Run: `.venv/bin/pytest tests/test_amorcage.py -v` · Expected: PASS.
- [ ] **Step 5: Commit** — `FEAT(contenu): amorçage depuis le CV actuel (FR + premier jet EN)`

---

### Task 5: Application, sécurité, langue et routes publiques

**Files:**
- Create: `cv/app.py`, `cv/securite.py`, `cv/public.py`, `cv/langue.py`
- Create: `babel.cfg`, `scripts/i18n.py` (adapté de ReadLN : mots-clés `_`, `gettext`,
  `ngettext:1,2`, projet `nanodeus-cv`), `translations/en/LC_MESSAGES/messages.po`
- Create: `templates/base.html`, `templates/cv.html` (squelette minimal, complété en
  Task 6), `templates/404.html`
- Create: `dev.sh` (`alembic upgrade head`, `flask amorcer`, `flask run --port 5010`,
  `CV_DATA_DIR=./data`)
- Test: `tests/test_public.py`, `tests/test_i18n_catalogue.py` (adapté de ReadLN)

**Interfaces:**
- Consumes: `assembler_vue` (Task 3), `amorcer` (Task 4), `Config` (Task 1).
- Produces:
  - `cv.app.create_app(config: Config|None = None) -> Flask` — enregistre le
    blueprint `public` **seulement si** `ROLE == "public"` (le blueprint admin viendra
    au plan 3) ; commande CLI `amorcer` ; session SQLAlchemy par requête dans
    `g.db`.
  - `cv.securite.init_securite(app)` — nonce CSP par requête (`g.csp_nonce`, exposé
    en Jinja `csp_nonce`), en-têtes : `Content-Security-Policy: default-src 'self';
    script-src 'self' 'nonce-<n>'; style-src 'self'; img-src 'self' data:;
    object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`,
    `X-Content-Type-Options: nosniff`, `Referrer-Policy:
    strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
    `Permissions-Policy: camera=(), microphone=(), geolocation=()`. Un hook
    `after_request` **retire tout `Set-Cookie`** sur le rôle public (filet). `ProxyFix(x_for=1,
    x_proto=1, x_host=1)` si `TRUST_PROXY`.
  - `cv.langue` : `g.lang` déduit du préfixe d'URL ; `locale_selector` Flask-Babel
    qui lit `g.lang` ; `suggerer_anglais(request) -> bool` (vrai si
    `request.accept_languages.best_match(["fr","en"]) == "en"` et page FR).
  - Routes (`cv/public.py`), slug contraint par `^[a-z0-9-]{1,40}$` :
    `GET /`, `GET /<slug>`, `GET /en/`, `GET /en/<slug>` → `cv.html` avec `vue`,
    `url_autre_langue`, `suggestion_en: bool`. `vue is None` → 404. `noindex` → balise
    `<meta name="robots" content="noindex">` **et** en-tête `X-Robots-Tag: noindex`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# fixture `client` : app rôle public, base amorcée, telephone="+33 6 99 88 77 66",
# email="fuite@test.invalid" posés sur le Profil.
URLS = ["/", "/devops", "/lead-tech", "/en/", "/en/devops", "/en/lead-tech", "/inconnue", "/en/inconnue"]

def test_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/inconnue").status_code == 404

def test_brouillon_404(client_avec_brouillon):
    assert client_avec_brouillon.get("/brouillon").status_code == 404

def test_non_listee_noindex(client):
    r = client.get("/lead-tech")
    assert r.headers["X-Robots-Tag"] == "noindex" and b'name="robots"' in r.data

@pytest.mark.parametrize("url", URLS)
def test_aucune_fuite_ni_cookie(client, url):
    r = client.get(url)
    corps = r.get_data(as_text=True) + str(r.headers)
    assert "fuite@test.invalid" not in corps and "99 88 77 66" not in corps
    assert "Set-Cookie" not in r.headers

def test_erreur_500_sans_fuite(client_qui_plante): ...   # route de test qui lève → 500 générique, sans coordonnées

def test_csp_nonce(client):
    r = client.get("/")
    nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
    assert all(f'nonce="{nonce}"' in tag for tag in re.findall(r"<script[^>]*>", r.get_data(as_text=True)))

def test_anglais(client):
    assert 'lang="en"' in client.get("/en/devops").get_data(as_text=True)

def test_suggestion_anglais(client):
    r = client.get("/devops", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert 'href="/en/devops"' in r.get_data(as_text=True)   # bandeau « View in English »

def test_pas_de_route_admin(client):
    assert client.get("/admin").status_code == 404
```

- [ ] **Step 2: Vérifier l'échec** — Run: `.venv/bin/pytest tests/test_public.py -v` · Expected: FAIL.
- [ ] **Step 3: Implémenter app, sécurité, langue, routes, templates minimaux, `dev.sh`**

Le gestionnaire d'erreur 500 rend `404.html`-like générique (`500.html` ou paramètre),
**jamais** de trace ni de contenu du profil.

- [ ] **Step 4: `python scripts/i18n.py update`, traduire le `.po` EN, `compile`**
- [ ] **Step 5: Vérifier le succès** — Run: `.venv/bin/pytest -v && .venv/bin/ruff check .` · Expected: tout PASS.
- [ ] **Step 6: Vérifier à la main** — Run: `./dev.sh` puis `curl -sI http://localhost:5010/ | grep -i -E "content-security|set-cookie"` · Expected: une ligne CSP, aucune `Set-Cookie`.
- [ ] **Step 7: Commit** — `FEAT(public): routes FR/EN, sécurité et langue sans cookie`

---

### Task 6: Page « pipeline » complète (bandeau, parcours, tests, bas de page)

**Files:**
- Modify: `templates/cv.html`
- Create: `templates/_bandeau.html`, `templates/_pipeline.html`, `templates/_tests.html`,
  `templates/_pied.html`
- Create: `static/cv.css`, `static/pipeline.js`
- Modify: `translations/en/LC_MESSAGES/messages.po`
- Test: `tests/test_page.py`

**Interfaces:**
- Consumes: `VueCV` / `Job` (Task 3), contexte de rendu (Task 5).
- Produces (contrat HTML sur lequel s'appuient `pipeline.js` et les plans 2-3) :
  - chaque job : `<button class="job" data-cle="e12" aria-expanded="false"
    aria-controls="detail-e12">`, le dernier job « prochaine mission » :
    `class="job job--en-cours" data-cle="prochaine"` (détail `detail-prochaine`) ;
  - chaque détail : `<section class="detail" id="detail-e12">` rendu **côté serveur
    pour tous les jobs** (lisible sans JS et à l'impression) ; `pipeline.js` masque
    tous les détails sauf le poste le plus récent au chargement ;
  - voie parallèle : conteneur `class="voie voie--parallele"` ;
  - bouton de contact : `<button class="btn-contact" data-action="demander-acces">`
    (inerte dans ce plan ; la modale vient au plan 2) ;
  - lien PDF des Artefacts **absent** tant que le plan 3 n'existe pas.

Rendu attendu : celui de `docs/maquettes/pipeline-valide.html` et de la spec § 4.1-4.3.
Choix fixés ici : point de rupture **720 px** ; en dessous, frise verticale, le plus
récent en haut, détail en accordéon sous le job tapé ; au-dessus, un seul panneau de
détail sous le graphe, qui suit la sélection. Jobs atteignables au Tab, `Entrée`/`Espace`
les ouvrent. Sections sans contenu (chiffres, soft skills, compétences, projets)
omises. Le panneau « Stack » liste aussi les centres d'intérêt. Bas de page : « Secrets » (`🔒 PHONE ***`, `🔒 EMAIL ***`, bouton « Demander
l'accès ») et « Artefacts » (LinkedIn/GitHub s'ils sont renseignés). Sélecteur FR / EN
dans l'en-tête. **Open Graph** (spec § 4.5) : `og:title` = « nom — titre »,
`og:description` = accroche, `og:url`, `og:locale` ; pas d'`og:image` avant le plan 3.
**Impression** : `@media print` clair, tous les détails dépliés, sans boutons.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_un_bouton_et_un_detail_par_job(client):
    html = client.get("/devops").get_data(as_text=True)
    cles = re.findall(r'data-cle="(e\d+)"', html)
    assert len(cles) == 6          # 2 formations + 3 postes + ReadLN
    assert all(f'id="detail-{c}"' in html for c in cles)
    assert "job--en-cours" in html and "voie--parallele" in html

def test_version_vide_sans_cadre_vide(client_version_vide):   # Review Focus 1
    html = client_version_vide.get("/vide").get_data(as_text=True)
    assert "voie--parallele" not in html and 'class="tests' not in html

def test_html_du_contenu_echappe(client_mission_script):       # Review Focus 3
    html = client_mission_script.get("/devops").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html

def test_secrets_masques(client):
    html = client.get("/devops").get_data(as_text=True)
    assert "***" in html and 'data-action="demander-acces"' in html

def test_open_graph(client):
    html = client.get("/devops").get_data(as_text=True)
    assert 'property="og:title"' in html and 'property="og:description"' in html

def test_aucun_attribut_style(client):
    assert " style=" not in client.get("/devops").get_data(as_text=True)
```

- [ ] **Step 2: Vérifier l'échec** — Run: `.venv/bin/pytest tests/test_page.py -v` · Expected: FAIL.
- [ ] **Step 3: Implémenter templates, `cv.css`, `pipeline.js`**
- [ ] **Step 4: Vérifier le succès** — Run: `.venv/bin/pytest -v && .venv/bin/ruff check .` · Expected: tout PASS.
- [ ] **Step 5: Vérifier le rendu à la main** (`./dev.sh`, http://localhost:5010)
  - à 1280 px : comparable à la maquette ; clic sur chaque job → le panneau suit ;
  - à 375 px : frise verticale, plus récent en haut, accordéon, **aucun défilement
    horizontal**, y compris après avoir temporairement allongé un intitulé à 120
    caractères et une mission à 2000 dans `data/cv.sqlite3` (Review Focus 5) ;
  - JS désactivé : tous les détails visibles ;
  - `prefers-reduced-motion` émulé : le job « en cours » ne pulse plus ;
  - console du navigateur : aucune violation CSP.
- [ ] **Step 6: i18n** — Run: `python scripts/i18n.py update`, traduire, `.venv/bin/pytest tests/test_i18n_catalogue.py` · Expected: PASS.
- [ ] **Step 7: Commit** — `FEAT(public): page pipeline interactive, version téléphone`
