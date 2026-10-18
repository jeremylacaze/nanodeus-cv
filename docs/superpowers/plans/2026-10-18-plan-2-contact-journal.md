# Plan 2 — Demande de contact et journal des visites · Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le bouton « Demander l'accès » ouvre une modale (ou, sans JavaScript, une
page) qui enregistre la demande en base puis l'envoie par SMTP à la boîte perso de
Jeremy avec `Reply-To` = le recruteur. Elle est protégée par un champ piège, des
limites et un contrôle d'`Origin`. Chaque page vue est journalisée sans IP ni cookie,
et une mention de confidentialité explique ce qui est noté.

**Architecture :**
- Trois tables (`demande_contact`, `visite`, `sel_journalier`) arrivent par la
  migration `0003`.
- `cv/journal.py` gère le sel du jour, l'empreinte HMAC, la classification du
  visiteur et la purge à 6 mois.
- `cv/contact.py` valide, limite, construit le message et l'envoie. Le transport est
  injecté, ce qui permet de le réutiliser pour « Renvoyer » au plan 3.
- `cv/courriel.py` est le transport SMTP générique.
- Les routes s'ajoutent au blueprint public. Un `contact.js` sans framework pilote un
  `<dialog>` déjà présent dans le HTML.

**Tech Stack:** celle du plan 1. Aucune nouvelle dépendance : `smtplib`,
`email.message` et `hmac` viennent de la bibliothèque standard.

**Spec:** `docs/superpowers/specs/2026-10-18-cv-pipeline-design.md` (lire § 5, 7, 8,
11 « Traefik », 12).

## Global Constraints

- **Règle n° 1 :** téléphone et email du **profil** n'apparaissent dans aucune réponse
  publique, y compris les réponses du formulaire (JSON, page de confirmation, erreurs).
  Le destinataire SMTP n'est jamais rendu.
- **Aucun cookie** sur le site public, y compris sur les `POST`. **Aucune IP en
  clair**, ni en base ni dans les logs applicatifs.
- Empreinte visiteur = `HMAC(IP + User-Agent)`, avec pour clé le secret serveur
  `CV_SEL_HMAC` combiné au **sel du jour**. Le sel du jour est aléatoire, stocké en
  base et supprimé dès le lendemain.
- Visites purgées au-delà de **183 jours**. Les demandes de contact sont conservées.
- Limites : **3 demandes/heure** et **10/jour** par visiteur, **50/jour** au total.
- Message : **2000 caractères** au plus. Email : **254**. Nom et entreprise : **100**
  chacun, sur une seule ligne.
- Expéditeur `cv@nanodeus.com` (`CV_EMAIL_EXPEDITEUR`), destinataire
  `CV_EMAIL_DESTINATAIRE`. Ce dernier n'a **pas de valeur par défaut** et ne figure
  jamais dans le dépôt.
- Objet : `[CV · <slug>] Demande de contact — <nom ou email> (<entreprise>)`, la
  parenthèse étant omise sans entreprise.
- **Chaque demande est enregistrée avant l'envoi.** Statut `en_attente` → `envoyee`
  ou `echec`.
- CSP inchangée et bloquante : pas de `style=`, pas de script inline sans nonce. Les
  fetch restent sur `'self'`.
- Tout texte visible passe par `_()`, avec le français comme msgid. Le `.po` anglais
  doit être complet (`tests/test_i18n_catalogue.py`).
- Le corps de l'email adressé à Jeremy est en français, sans `_()`.
- Code, commentaires et commits en français. Branche `feat/contact-journal` depuis
  `develop`. Commits avec l'adresse noreply.

## Décisions prises en écrivant ce plan *(à contester à la relecture)*

- **Adresses du contact :** `GET|POST /<slug>/contact` et `/en/<slug>/contact`. La
  version voulue est portée par l'URL : aucun champ caché à falsifier, et pas de
  collision avec un slug. Le bouton devient un lien vers cette page, que le JS
  intercepte pour ouvrir la modale.
- **Ouverture de la modale journalisée** par `POST …/contact/ouverture` →
  `204`, envoyé par `navigator.sendBeacon`. Sans JS, c'est le `GET` de la page de
  contact qui journalise l'événement.
- **Empreinte d'anti-abus = HMAC(IP seule).** Le User-Agent se change trop
  facilement : avec lui, un robot contournerait la limite par visiteur. Il reste
  utilisé pour l'empreinte des visites, conformément au § 7.
- **`Origin` absent = refus (403)**, pour tout `POST` du service public. Tous les
  navigateurs actuels l'envoient sur un `POST` de même origine.
- **Échec d'envoi :** le recruteur voit « L'envoi n'a pas abouti, mais votre demande
  est bien enregistrée : Jeremy la verra. » La réponse est un `202`. Lui faire
  renvoyer le formulaire créerait des doublons pour rien.
- **Purge** faite à la création du sel du jour, donc une fois par jour, sans cron.
- **Envoi synchrone** dans la requête, avec un timeout SMTP de 10 s. Le trafic est
  faible, une file de tâches serait du poids mort.
- **Date du corps de l'email en UTC**, étiquetée « UTC ». On évite `tzdata` dans
  l'image slim.

## Review Focus

1. **Injection d'en-têtes :** `nom`, `entreprise` ou `email` contenant `\r\n`,
   `Bcc:`, des virgules ou `<…>` → refusé en 400. Le message ne porte qu'un
   `Reply-To` et un destinataire. *(tests Task 3)*
2. **SMTP en panne ou trop lent** (exception, timeout) → la demande existe en base
   en `echec`, avec une erreur technique **jamais renvoyée au public**. La page reste
   sobre. *(tests Task 3 et Task 4)*
3. **Écriture du journal impossible** (base verrouillée, table absente) → la page
   s'affiche quand même en 200, et rien n'est journalisé en clair. *(test Task 2)*
4. **`POST` hostile :** `Origin` d'un autre site, `Origin: null`, `Origin` absent,
   corps de plus de 64 Kio, version brouillon ou inconnue → 403, 413 ou 404, sans
   rien enregistrer. *(tests Task 4)*
5. **Double clic ou double envoi** → bouton désactivé pendant l'envoi. Les limites
   attrapent le reste. *(test Task 4 + vérification manuelle Task 5)*

---

### Task 1: Tables du contact et du journal

**Files:**
- Modify: `cv/models.py`
- Create: `alembic/versions/0003_contact_visites.py` (autogénérée puis relue,
  `down_revision = "0002"`)
- Test: `tests/test_db.py`

**Interfaces:**
- Produces (dans `cv.models`) :
  - `STATUTS_DEMANDE = ("en_attente", "envoyee", "echec")`,
    `TYPES_VISITE = ("page", "contact", "pdf", "apercu_linkedin")`.
  - `DemandeContact` (`demande_contact`) :
    - `id` ;
    - `cree_le: datetime` (UTC naïf, indexé) ;
    - `email: str(254)`, `nom: str(100)=""`, `entreprise: str(100)=""`,
      `message: Text` ;
    - `version_slug: str(40)`, `langue: str(2)` ;
    - `statut: str(20)="en_attente"` (CHECK `ck_statut`) ;
    - `erreur: str(300)|None` (admin seulement) ;
    - `envoyee_le: datetime|None` ;
    - `empreinte: str(32)` (indexée).
  - `Visite` (`visite`) :
    - `id` ;
    - `horodatage: datetime` (indexé) ;
    - `type: str(20)` (CHECK `ck_type`) ;
    - `version_slug: str(40)`, `langue: str(2)` ;
    - `source: str(100)` ;
    - `appareil: str(12)` (`mobile`|`ordinateur`) ;
    - `empreinte: str(32)`.
  - `SelJournalier` (`sel_journalier`) : `jour: date` (clé primaire),
    `valeur: LargeBinary(32)`.
  - Attention : `_dans()` nomme la contrainte `ck_<colonne>`. `Entree` porte déjà un
    `ck_type` : vérifier que SQLite et Alembic acceptent ce nom sur une autre table,
    sinon passer un `name=` explicite.

- [ ] **Step 1: Écrire les tests qui échouent** (dans `tests/test_db.py`)

```python
def test_statut_de_demande_controle(session):
    session.add(DemandeContact(cree_le=datetime(2026, 10, 18), email="r@ex.fr", message="m",
                               version_slug="devops", langue="fr", statut="perdue",
                               empreinte="0" * 32))
    with pytest.raises(IntegrityError):
        session.flush()

def test_type_de_visite_controle(session):
    session.add(Visite(horodatage=datetime(2026, 10, 18), type="clic", version_slug="devops",
                       langue="fr", source="direct", appareil="mobile", empreinte="0" * 32))
    with pytest.raises(IntegrityError):
        session.flush()

def test_un_seul_sel_par_jour(session):
    session.add_all([SelJournalier(jour=date(2026, 10, 18), valeur=b"a" * 32),
                     SelJournalier(jour=date(2026, 10, 18), valeur=b"b" * 32)])
    with pytest.raises(IntegrityError):
        session.flush()
```

`test_migrations_alignees_sur_les_modeles` (déjà présent) couvre la migration.

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_db.py -q`
Expected: FAIL (`ImportError: DemandeContact`).

- [ ] **Step 3: Ajouter les trois modèles, puis générer la migration**
  (`CV_DATA_DIR=<tmp> .venv/bin/alembic upgrade head && … revision --autogenerate -m contact_visites`).
  La relire : contraintes CHECK présentes, index présents, `downgrade` qui supprime
  les trois tables. La renommer en `0003_contact_visites.py`, avec `revision = "0003"`.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: tout passe, `alembic check` compris.

- [ ] **Step 5: Commit** — `FEAT(contact): tables des demandes, des visites et du sel du jour`

---

### Task 2: Journal des visites

**Files:**
- Create: `cv/journal.py`
- Modify: `cv/config.py` (`SEL_HMAC`), `cv/public.py` (`_page` journalise)
- Test: `tests/test_journal.py`

**Interfaces:**
- Consumes : `Visite`, `SelJournalier` (Task 1).
- Produces (dans `cv.journal`) :
  - `Config.SEL_HMAC: str` (env `CV_SEL_HMAC`, défaut `"dev-uniquement"`. Le plan 4
    la rend obligatoire en production).
  - `sel_du_jour(session, maintenant: datetime) -> bytes` :
    - lit ou crée la ligne du jour (`secrets.token_bytes(32)`) ;
    - à la création, supprime les sels antérieurs et les visites de plus de
      183 jours ;
    - en cas de création concurrente (`IntegrityError`), fait un rollback puis
      relit.
  - `empreinte(session, secret: str, *parties: str, maintenant: datetime) -> str` :
    `hmac(secret.encode() + sel_du_jour, "\x1f".join(parties), sha256)`, tronqué à
    32 caractères hexadécimaux.
  - `classer(user_agent: str) -> str | None` :
    - `"apercu_linkedin"` si l'UA contient `LinkedInBot` ;
    - `None` pour tout autre robot : UA vide, ou correspondant au motif insensible
      à la casse
      `bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|curl|wget|python|httpx|go-http|okhttp|java/|scrapy|headless|monitor|uptime` ;
    - `"page"` sinon.
  - `appareil(user_agent: str) -> str` : `"mobile"` si `Mobi|Android|iPhone|iPad|iPod`,
    `"ordinateur"` sinon.
  - `source(req) -> str`, dans cet ordre :
    1. `?src=` nettoyé (minuscules, `[a-z0-9._-]`, 40 caractères au plus) ;
    2. sans `src`, le nom d'hôte du `Referer`, sans `www.`, 100 caractères au plus ;
    3. `"interne"` si cet hôte est celui du site ;
    4. `"direct"` sans Referer.
  - `journaliser(session, req, config, type: str, version_slug: str, langue: str,
    maintenant: datetime | None = None) -> None` :
    - ne fait rien sur `HEAD` ni sur un préchargement (`Purpose`/`Sec-Purpose`
      contenant `prefetch`) ;
    - pour un UA classé `apercu_linkedin`, force ce type ;
    - commit ;
    - sur **toute** exception, fait un rollback et un
      `logger.warning("journal des visites : %s", type(exc).__name__)`, sans IP ni
      détail.
- `_page()` appelle `journaliser(g.db, request, config, "page", vue.slug, g.lang)`
  après le rendu réussi. `VueCV` expose déjà `slug`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
IP, UA = "203.0.113.77", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Mobile/15E148"

def test_visite_journalisee_sans_ip(fabrique_app):
    app = fabrique_app(); c = app.test_client()
    c.get("/devops?src=QR", headers={"User-Agent": UA}, environ_base={"REMOTE_ADDR": IP})
    with app.extensions["cv_sessions"]() as s:
        v = s.scalars(select(Visite)).one()
        dump = "\n".join(s.connection().connection.iterdump())
    assert (v.type, v.version_slug, v.langue, v.source, v.appareil) == \
        ("page", "devops", "fr", "qr", "mobile")
    assert IP not in dump and len(v.empreinte) == 32

def test_meme_visiteur_meme_jour_meme_empreinte(session): ...   # même jour → égales ; autre UA → différentes
def test_empreinte_change_le_lendemain(session): ...            # J et J+1 → différentes ; sel de J supprimé
def test_purge_des_visites_de_plus_de_6_mois(session): ...      # visite J-184 supprimée, J-182 gardée, à la création du sel
def test_sel_concurrent_relu(session, monkeypatch): ...          # IntegrityError simulée → relit le sel existant

@pytest.mark.parametrize("ua, attendu", [
    ("LinkedInBot/1.0 (compatible; Mozilla/5.0)", "apercu_linkedin"),
    ("Googlebot/2.1", None), ("curl/8.0", None), ("", None), (UA, "page")])
def test_classer(ua, attendu): assert classer(ua) == attendu

@pytest.mark.parametrize("src, referer, attendu", [
    (None, "https://www.linkedin.com/feed/", "linkedin.com"), (None, None, "direct"),
    (None, "http://localhost/devops", "interne"), ("<script>", None, "script"),
    ("qr", "https://google.com/", "qr")])
def test_source(app, src, referer, attendu): ...

def test_robot_non_journalise_mais_page_servie(fabrique_app): ...   # Googlebot → 200, 0 visite
def test_head_et_prechargement_non_journalises(fabrique_app): ...
def test_404_non_journalisee(fabrique_app): ...
def test_journal_en_panne_page_servie(fabrique_app, caplog): ...
    # supprimer la table visite (DROP TABLE) → GET /devops == 200 ; IP absente de caplog.text
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_journal.py -q`
Expected: FAIL (`ModuleNotFoundError: cv.journal`).

- [ ] **Step 3: Implémenter `cv/journal.py`, `Config.SEL_HMAC` et l'appel dans `_page()`.**
  `maintenant` vaut `datetime.now(UTC).replace(tzinfo=None)` par défaut.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: tout passe.

- [ ] **Step 5: Commit** — `FEAT(journal): visites journalisées sans IP ni cookie, purge à 6 mois`

---

### Task 3: Domaine du contact et transport SMTP

**Files:**
- Create: `cv/contact.py`, `cv/courriel.py`
- Modify: `cv/config.py`, `cv/app.py` (`app.extensions["cv_envoi"]`)
- Test: `tests/test_contact.py`

**Interfaces:**
- Consumes : `DemandeContact` (Task 1), `empreinte` (Task 2).
- Produces :
  - `Config` :
    - `SMTP_HOTE` (`CV_SMTP_HOTE`, vide = envoi non configuré) ;
    - `SMTP_PORT` (`CV_SMTP_PORT`, défaut 587) ;
    - `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE` ;
    - `SMTP_TLS` (`CV_SMTP_TLS` ∈ `starttls`|`ssl`|`aucun`, défaut `starttls`,
      `ValueError` sinon) ;
    - `EMAIL_EXPEDITEUR` (défaut `cv@nanodeus.com`) ;
    - `EMAIL_DESTINATAIRE` (défaut `""`).
  - `cv.courriel.EnvoiSMTP(config)` avec `envoyer(message: EmailMessage) -> None` :
    - `smtplib.SMTP` ou `SMTP_SSL`, `timeout=10`, `starttls()` selon `SMTP_TLS`,
      `login` si un utilisateur est défini ;
    - lève `EnvoiNonConfigure` si `SMTP_HOTE` ou `EMAIL_DESTINATAIRE` est vide.
  - `cv.contact.Formulaire` (dataclass) : `email`, `message`, `nom`, `entreprise`,
    `piege`.
  - `valider(donnees: Mapping[str, str]) -> tuple[Formulaire, dict[str, str]]` :
    - retourne le formulaire nettoyé (`strip`) et les erreurs par champ, avec des
      messages `_()` ;
    - email : obligatoire, ≤ 254, motif
      `[^@\s<>()\[\],;:"\\]+@[^@\s<>()\[\],;:"\\]+\.[^@\s<>()\[\],;:"\\]+` ;
    - message : obligatoire, ≤ 2000 ;
    - nom et entreprise : ≤ 100, sans caractère de contrôle ;
    - champ piège : `site_web`.
  - `limite_atteinte(session, empreinte: str, maintenant: datetime) -> bool` : ≥ 3 sur
    1 h, ou ≥ 10 sur 24 h pour cette empreinte, ou ≥ 50 sur 24 h au total.
  - `construire_message(demande: DemandeContact, config) -> EmailMessage` :
    - `From` = expéditeur, `To` = destinataire, `Reply-To` = `demande.email` ;
    - objet selon le format des Global Constraints ;
    - corps texte : message, nom, entreprise, email, version, langue, date
      `JJ/MM/AAAA HH:MM UTC`.
  - `envoyer_demande(session, demande, config, envoi) -> bool` :
    - en cas de succès : `envoyee`, `envoyee_le` et `erreur=None` ;
    - sur toute exception : `echec` et `erreur = f"{type(exc).__name__}: {exc}"[:300]` ;
    - commit, puis renvoie le succès. Le plan 3 l'utilisera pour « Renvoyer ».
  - `enregistrer(session, formulaire, version_slug, langue, empreinte, maintenant)
    -> DemandeContact` : commit en `en_attente`.
  - `app.extensions["cv_envoi"] = EnvoiSMTP(config)`, lu à l'appel : les tests le
    remplacent par un faux.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_formulaire_valide(): ...                      # erreurs == {} ; champs strip()és
@pytest.mark.parametrize("email", ["", "pas-un-email", "a@b", "a@b.fr\r\nBcc: x@y.fr",
                                   "a@b.fr, c@d.fr", "Nom <a@b.fr>", "a" * 250 + "@b.fr"])
def test_email_refuse(email): assert "email" in valider({"email": email, "message": "m"})[1]
def test_message_obligatoire_et_borne(): ...           # "" et 2001 caractères refusés, 2000 accepté
def test_nom_sur_une_ligne(): ...                      # "A\r\nBcc: x" et 101 caractères refusés

def test_message_construit(session):
    d = DemandeContact(email="r@ex.fr", nom="Alice", entreprise="ACME", message="Bonjour",
                       version_slug="lead-tech", langue="en", cree_le=datetime(2026, 10, 18, 9, 5))
    m = construire_message(d, config)
    assert m["Reply-To"] == "r@ex.fr" and m["To"] == config.EMAIL_DESTINATAIRE
    assert m["From"] == "cv@nanodeus.com"
    assert m["Subject"] == "[CV · lead-tech] Demande de contact — Alice (ACME)"
    assert "18/10/2026 09:05 UTC" in m.get_content() and "Bonjour" in m.get_content()

def test_objet_sans_nom_ni_entreprise(): ...           # "… — r@ex.fr" sans parenthèse
def test_limites_par_visiteur_et_globale(session): ... # 3 en 1 h → True ; 2 en 1 h + 7 plus tôt → False ; 10/24 h → True ; 50 autres → True
def test_envoi_reussi(session): ...                    # faux envoi → statut envoyee, envoyee_le posé
def test_envoi_en_echec_garde_la_demande(session): ... # faux envoi qui lève TimeoutError → echec, erreur renseignée
def test_envoi_non_configure(session): ...             # EnvoiSMTP sans hôte → echec, "EnvoiNonConfigure"
def test_transport_smtp(monkeypatch): ...              # faux smtplib.SMTP : starttls, login, send_message appelés ; timeout=10
def test_smtp_tls_invalide_refuse(monkeypatch): ...    # CV_SMTP_TLS=oui → ValueError
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_contact.py -q`
Expected: FAIL (`ModuleNotFoundError: cv.contact`).

- [ ] **Step 3: Implémenter `cv/courriel.py`, `cv/contact.py`, la config et l'extension.**

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: tout passe.

- [ ] **Step 5: Commit** — `FEAT(contact): validation, limites et envoi SMTP des demandes`

---

### Task 4: Routes du contact et contrôle d'Origin

**Files:**
- Modify: `cv/public.py`, `cv/securite.py`, `cv/app.py`, `cv/langue.py`
  (`_CHEMIN_DE_PAGE` accepte `/<slug>/contact`)
- Create: `templates/contact.html`, `templates/_formulaire_contact.html`,
  `templates/erreur.html`
- Test: `tests/test_contact_routes.py`, `tests/test_public.py` (URLS et lien d'autre
  langue)

**Interfaces:**
- Consumes : Task 2 et Task 3.
- Produces :
  - `securite.origine_valide(req) -> bool` : `Origin` présent, différent de `null`, et
    `urlsplit(origin).netloc == req.host`. Un `before_request` répond 403 à tout
    `POST`, `PUT`, `PATCH` ou `DELETE` qui échoue à ce contrôle, pour les deux rôles.
  - `MAX_CONTENT_LENGTH = 64 * 1024` → 413.
  - Gestionnaires `403`, `413` et `429` qui rendent `erreur.html` avec un message
    générique `_()`, avec `noindex`.
  - `GET /<slug>/contact` et `/en/<slug>/contact` :
    - version publique (`publiee` ou `non_listee`), 404 sinon ;
    - rend `contact.html` (noindex) avec `_formulaire_contact.html` ;
    - journalise `type="contact"`.
  - `POST` des mêmes adresses :
    1. version publique, sinon 404 ;
    2. `valider` ; champ piège rempli → réponse de succès, rien enregistré ni envoyé ;
    3. erreurs → 400 ;
    4. `empreinte(…, ip)` puis `limite_atteinte` → 429 ;
    5. `enregistrer` puis `envoyer_demande` → 200 si envoyé, 202 si échec ;
    6. `Accept: application/json` → `{"ok": bool, "message": str, "erreurs": {champ: str}}`,
       sinon la page `contact.html` en mode confirmation, ou avec le formulaire
       pré-rempli et ses erreurs.
  - `POST …/contact/ouverture` → 204, journalise `type="contact"` (balise de la
    modale).
  - `_formulaire_contact.html` (variables `action`, `valeurs`, `erreurs`) :
    - champs `email` (type email, required, maxlength 254), `message` (textarea,
      required, maxlength 2000), `nom`, `entreprise` (maxlength 100) ;
    - champ piège `site_web` dans un `<div class="piege" aria-hidden="true">`, avec
      `tabindex="-1" autocomplete="off"` ;
    - zone `<p class="retour" role="status" aria-live="polite">` ;
    - une ligne de confidentialité (« Ces informations ne servent qu'à vous
      répondre. »).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
ORIGINE = {"Origin": "http://localhost"}
OK = {"email": "r@ex.fr", "message": "Bonjour", "nom": "Alice", "entreprise": "ACME"}

def test_demande_envoyee_reply_to(client_et_envoi):
    c, envoi = client_et_envoi
    r = c.post("/lead-tech/contact", data=OK, headers={**ORIGINE, "Accept": "application/json"})
    assert r.status_code == 200 and r.json["ok"] is True
    assert envoi.messages[0]["Reply-To"] == "r@ex.fr"
    assert "[CV · lead-tech]" in envoi.messages[0]["Subject"]
    # demande en base : version lead-tech, langue fr, statut envoyee

def test_langue_anglaise_enregistree(...): ...     # POST /en/devops/contact → langue "en", message JSON en anglais
def test_echec_envoi_202_demande_gardee(...): ...  # faux envoi qui lève → 202, ok False, statut echec, erreur technique absente du corps
def test_champ_piege(...): ...                     # site_web rempli → 200 ok, 0 demande, 0 envoi
def test_erreurs_de_validation_400(...): ...       # email invalide → 400, erreurs["email"], 0 demande
def test_limite_429(...): ...                      # 4e POST de la même IP en 1 h → 429 ; une autre IP passe
@pytest.mark.parametrize("entetes", [{}, {"Origin": "null"}, {"Origin": "https://evil.example"}])
def test_origin_refuse(..., entetes): ...          # 403, 0 demande
def test_corps_trop_gros_413(...): ...             # 70 000 octets → 413
@pytest.mark.parametrize("url", ["/brouillon/contact", "/inconnue/contact", "/Devops/contact"])
def test_version_non_publique_404(..., url): ...   # GET et POST → 404
def test_sans_js_page_de_confirmation(...): ...    # POST sans Accept JSON → 200 HTML « Jeremy vous répondra »
def test_sans_js_erreurs_et_valeurs_conservees(...): ...  # 400 HTML, nom « Alice » re-rendu échappé
def test_page_contact_journalise_et_noindex(...): ...     # GET → 200, noindex, 1 visite type contact
def test_balise_ouverture_204(...): ...            # POST …/contact/ouverture → 204, 1 visite type contact
def test_reponses_sans_fuite_ni_cookie(...): ...   # toutes les réponses ci-dessus : ni EMAIL, ni TELEPHONE, ni destinataire, ni Set-Cookie
```

Dans `tests/test_public.py`, ajouter `"/devops/contact"` et `"/en/devops/contact"` à
`URLS`, puis vérifier `url_autre_langue("/devops/contact") == "/en/devops/contact"`.
La fixture `client_et_envoi` remplace `app.extensions["cv_envoi"]` par un faux qui
garde les messages ou lève sur demande. Elle pose `CV_EMAIL_DESTINATAIRE` à
`dest@test.invalid`.

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_contact_routes.py tests/test_public.py -q`
Expected: FAIL (404 sur `/lead-tech/contact`).

- [ ] **Step 3: Implémenter les routes, le contrôle d'Origin, les gestionnaires d'erreur et les templates.**
  L'IP vient de `request.remote_addr`, que `ProxyFix` corrige quand `TRUST_PROXY=1`.
  Elle n'est jamais stockée ni loguée.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: tout passe.

- [ ] **Step 5: Commit** — `FEAT(contact): formulaire de contact avec et sans JavaScript`

---

### Task 5: Modale, mention de confidentialité, traductions

**Files:**
- Create: `static/contact.js`, `templates/_contact.html` (le `<dialog>`)
- Modify:
  - `templates/_pied.html` : le bouton devient
    `<a class="btn-contact" href="…/contact" data-action="demander-acces">`, et la
    mention de confidentialité est ajoutée ;
  - `templates/cv.html` : inclure `_contact.html` et charger `contact.js`
    (`nonce`, `defer`) ;
  - `static/cv.css`, `translations/en/LC_MESSAGES/messages.po` ;
  - `tests/test_page.py`.

**Interfaces:**
- Consumes : routes et `_formulaire_contact.html` (Task 4).
- `contact.js` :
  - au clic sur `[data-action="demander-acces"]`, si `dialog.showModal` existe :
    `preventDefault`, `showModal()`, `navigator.sendBeacon(<action>/ouverture)`, puis
    focus sur le champ email. Sinon, le lien navigue vers la page de contact ;
  - à l'envoi : `fetch(action, {method: "POST", body: new URLSearchParams(new FormData(form)), headers: {Accept: "application/json"}})`,
    bouton désactivé jusqu'à la réponse ;
  - messages et erreurs posés par `textContent`, jamais par `innerHTML` ;
  - en cas de succès, le formulaire est masqué et la confirmation affichée ;
  - bouton « Fermer », `Échap` natif ;
  - en cas d'erreur réseau, message générique.
- Mention en bas de page :

  > Ce site ne dépose aucun cookie. Chaque visite est notée sans votre adresse IP :
  > date, page, source (LinkedIn, QR code…), type d'appareil et une empreinte anonyme
  > renouvelée chaque jour. Ces visites sont effacées après 6 mois.

  Le texte est en `_()`, avec sa traduction anglaise dans le `.po`.

- [ ] **Step 1: Écrire les tests qui échouent** (dans `tests/test_page.py`)

```python
def test_bouton_contact_fonctionne_sans_js(client):
    html = _html(client, "/lead-tech")
    assert 'class="btn-contact" href="/lead-tech/contact" data-action="demander-acces"' in html
    assert 'href="/en/lead-tech/contact"' in _html(client, "/en/lead-tech")

def test_modale_presente_et_fermee(client):
    html = _html(client)
    assert re.search(r'<dialog[^>]*class="modale-contact"', html) and "<dialog open" not in html
    assert 'action="/devops/contact"' in html and 'name="site_web"' in html
    assert re.search(r'<script src="/static/contact\.js" nonce="[^"]+" defer>', html)

def test_mention_de_confidentialite(client):
    assert "aucun cookie" in _html(client) and "no cookies" in _html(client, "/en/devops")
```

Adapter `test_version_vide_sans_cadre_vide` et `test_secrets_masques` au lien :
l'assertion `data-action="demander-acces"` reste valable.

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_page.py -q`
Expected: FAIL.

- [ ] **Step 3: Implémenter les templates, `contact.js` et le CSS.**
  - `dialog::backdrop` ;
  - la modale tient en pleine largeur à 375 px ;
  - `.piege { position: absolute; left: -10000px; }` ;
  - modale masquée à l'impression.

  Puis lancer `python scripts/i18n.py update`, traduire les nouvelles entrées et
  vérifier qu'il ne reste aucune entrée `fuzzy`.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: tout passe, `test_i18n_catalogue` compris.

- [ ] **Step 5: Vérification manuelle** (Playwright, serveur de dev, faux SMTP absent
  donc en échec)

Sur ordinateur et à 375 px, vérifier :
- la modale s'ouvre, le focus est sur l'email et `Échap` la ferme ;
- un envoi affiche le message d'échec sobre, et un double clic ne crée qu'une
  demande ;
- avec JavaScript coupé, le lien mène à la page et le `POST` à la confirmation ;
- la console ne montre aucune violation CSP ;
- la page ne défile pas horizontalement.

- [ ] **Step 6: Commit** — `FEAT(contact): modale de demande d'accès et mention de confidentialité`
