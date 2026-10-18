# Plan 3b : photo, QR code, PDF et lien « Artefacts »

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la photo du profil (EXIF retiré), le QR code de chaque version, le PDF public
et le PDF complet, et le lien « CV · PDF » dans les Artefacts.

**Architecture:** deux modules nouveaux. `cv/medias.py` traite la photo (Pillow) et
fabrique les QR codes (segno). `cv/pdf.py` rend un template dédié et le convertit en PDF
(WeasyPrint), avec un cache sur disque indexé par le contenu. Les fichiers vivent dans
`CV_DATA_DIR` (`photos/`, `cache-pdf/`), jamais dans le dépôt. Aucune migration :
`profil.photo_fichier` existe depuis 0001.

**Tech Stack:** Pillow 13.0.0, segno 1.6.6, WeasyPrint 70.0 (Pango système : `brew
install pango` en local, paquets Debian au plan 4), pypdf 6.21.1 pour les tests.

**Spec:** `docs/superpowers/specs/2026-10-18-cv-pipeline-design.md` (§ 1 QR imprimé,
§ 3 pile, § 4.1 Artefacts, § 4.4 adresses, § 4.5 Open Graph, § 6 PDF, § 9 Profil et
Versions, § 10 photo, § 12 test anti-fuite).

## Global Constraints

- **Règle n° 1** : ni téléphone ni email dans une réponse publique, PDF public et
  métadonnées du PDF compris. Seul le PDF complet de l'admin les porte.
- **Dépôt public** : aucune photo commitée. Les images de test sont fabriquées en
  mémoire par Pillow dans les tests.
- **Photo** : JPEG carré 512 × 512, réencodé, **sans aucune métadonnée** (ni EXIF, ni
  GPS, ni profil ICC, ni commentaire). L'orientation EXIF est appliquée avant d'être
  jetée.
- **WeasyPrint ne va rien chercher** : `URLFetcher(allowed_protocols=("data",))`. La
  photo et le QR sont incorporés en `data:`, la feuille de style est dans le template.
- **Le PDF complet n'est jamais écrit sur disque** (ni cache ni fichier temporaire).
- CSP inchangée (`img-src 'self' data:`), aucun cookie, l'admin reste en français, et
  tout texte public passe par `_()` (catalogue anglais complet, sans `fuzzy`).
- Adresse imprimée (QR, lien du PDF) : `CV_URL_PUBLIQUE`, sinon
  `https://cv.nanodeus.com`. Jamais l'hôte de la requête : en admin, ce serait
  l'adresse du tailnet.
- Dépendances épinglées à la version exacte. `pypdf` va dans `requirements-dev.txt`
  seulement.

## Review Focus

- **Fichier envoyé qui n'est pas une image** : texte renommé en `.jpg`, JPEG tronqué,
  image de 20 000 × 20 000 (bombe de décompression), GIF. Attendu : 400 avec un message
  clair. Rien n'est écrit sur disque et la photo actuelle reste en place.
- **Remplacement de la photo** : l'ancien fichier est supprimé et son URL répond 404 ;
  seule la photo courante est servie. Un nom forgé (`../cv.sqlite3`, `abc.jpg`) répond
  aussi 404.
- **Cache du PDF périmé** : après une modification de l'accroche, le PDF servi change
  (autre ETag, nouveau texte). Un PDF ancien n'est jamais resservi.
- **Routage `/<slug>.pdf`** : `/devops.pdf` et `/en/devops.pdf` donnent un PDF.
  `/brouillon.pdf`, `/inconnue.pdf`, `/Devops.pdf`, `/devops.PDF` et `/devops.pdf/x`
  répondent 404. `/devops` reste la page.
- **Fuite dans le PDF** : le texte extrait du PDF public, FR et EN, ne contient ni le
  téléphone ni l'email. Témoin positif : le PDF complet contient les deux, ce qui prouve
  que l'extraction fonctionne.

---

### Task 1: Dépendances et photo du profil

**Files:**
- Modify: `requirements.txt`, `requirements-dev.txt`
- Create: `cv/medias.py`, `tests/test_medias.py`, `tests/test_admin_photo.py`
- Modify: `cv/config.py` (dossiers), `cv/app.py` (`MAX_CONTENT_LENGTH` admin),
  `cv/vue.py`, `cv/public.py`, `cv/admin/vues_contenu.py`, `cv/admin/__init__.py`
  (`MESSAGES`), `cv/admin/versions.py` (`SLUGS_RESERVES`),
  `templates/admin/profil.html`, `templates/cv.html` (og:image), `static/cv.css`

**Interfaces:**
- Produces :
  - `cv.medias` : `TAILLE_PHOTO = 512`, `PIXELS_MAX = 40_000_000`,
    `NOM_PHOTO = re.compile(r"[0-9a-f]{16}\.jpg")` ;
    `class PhotoInvalide(ValueError)` ;
    `traiter_photo(donnees: bytes) -> bytes` ;
    `enregistrer_photo(dossier: Path, donnees: bytes) -> str` (renvoie le nom) ;
    `chemin_photo(config, nom: str | None) -> Path | None` (fichier existant ou None).
  - `Config.DOSSIER_PHOTOS = DATA_DIR / "photos"`, `Config.DOSSIER_CACHE_PDF =
    DATA_DIR / "cache-pdf"`.
  - `assembler_vue(..., prefixe_medias: str = "")` : `photo_url =
    f"{prefixe_medias}/photo/{nom}"` si une photo est posée, sinon `None`.

- [ ] **Step 1: Dépendances**

`requirements.txt` : `Pillow==13.0.0`, `segno==1.6.6`, `weasyprint==70.0`.
`requirements-dev.txt` : `pypdf==6.21.1`. Puis `.venv/bin/pip install -r
requirements-dev.txt`.

- [ ] **Step 2: Write the failing tests** (`tests/test_medias.py`)

Fabrique `_image(format="JPEG", taille=(400, 200), exif=None) -> bytes` avec Pillow
(moitié gauche rouge, moitié droite bleue).

```python
def test_photo_carree_jpeg_sans_metadonnees():
    exif = Image.Exif(); exif[0x0110] = "Appareil"; exif[0x8825] = {2: (43.0, 36.0, 0.0)}
    sortie = traiter_photo(_image(exif=exif.tobytes()))
    img = Image.open(BytesIO(sortie))
    assert img.format == "JPEG" and img.size == (512, 512)
    assert len(img.getexif()) == 0 and "icc_profile" not in img.info
    assert b"Exif" not in sortie and b"Appareil" not in sortie

def test_orientation_appliquee():
    exif = Image.Exif(); exif[0x0112] = 6   # à tourner de 90° dans le sens horaire
    img = Image.open(BytesIO(traiter_photo(_image(exif=exif.tobytes()))))
    assert _rouge(img.getpixel((256, 40))) and _bleu(img.getpixel((256, 470)))

def test_png_transparent_sur_fond_blanc(): ...   # pixel transparent → (≥250, ≥250, ≥250)

@pytest.mark.parametrize("donnees", [b"pas une image", _image()[:200], _image("GIF")])
def test_photo_invalide(donnees):
    with pytest.raises(PhotoInvalide): traiter_photo(donnees)

def test_bombe_de_decompression():   # PNG 20000 × 20000 en mode "1" (fichier minuscule)
    with pytest.raises(PhotoInvalide): traiter_photo(_bombe())

def test_nom_derive_du_contenu(tmp_path):
    nom = enregistrer_photo(tmp_path, b"x")
    assert NOM_PHOTO.fullmatch(nom) and (tmp_path / nom).read_bytes() == b"x"
    assert enregistrer_photo(tmp_path, b"x") == nom
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_medias.py`
Expected: FAIL (`ModuleNotFoundError: cv.medias`)

- [ ] **Step 4: Implement `cv/medias.py` (partie photo)**

- La taille est contrôlée avant tout décodage (`Image.open` est paresseux) :
  `largeur × hauteur > PIXELS_MAX` → `PhotoInvalide`. Seuls JPEG, PNG et WEBP sont admis.
- `OSError`, `SyntaxError`, `ValueError` et `Image.DecompressionBombError` deviennent
  `PhotoInvalide` (le message ne cite pas l'exception).
- Ensuite : `ImageOps.exif_transpose`, un fond blanc si l'image a de la transparence,
  `ImageOps.fit` en 512 × 512 (LANCZOS, centré), puis une copie dans une
  `Image.new("RGB", …)` neuve, dont `info` est vide. Pillow peut sinon reprendre le
  profil ICC de `img.info`. Enregistrement en JPEG `quality=85, optimize=True`.
- `enregistrer_photo` : nom `sha256(donnees)[:16] + ".jpg"`, écriture dans un fichier
  temporaire du même dossier, puis `os.replace`. Le dossier est créé au besoin.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/test_medias.py`
Expected: PASS

- [ ] **Step 6: Write the failing tests** (`tests/test_admin_photo.py`)

```python
def test_envoi_photo(admin): # POST multipart /admin/profil/photo, Origin localhost
    # → 303 vers /admin/profil?ok=photo-enregistree ; profil.photo_fichier posé ;
    #   fichier présent dans DATA_DIR/photos ; GET /admin/photo/<nom> → 200 image/jpeg
def test_remplacement_supprime_l_ancienne(admin): # 2 envois → 1 seul fichier ; ancien nom 404
def test_suppression_photo(admin):   # POST /admin/profil/photo/supprimer → fichier et champ effacés
@pytest.mark.parametrize("fichier", [None, b"pas une image"])
def test_envoi_refuse_400(admin, fichier):  # message « Ce fichier n'est pas une photo… »,
    # photo actuelle inchangée, aucun nouveau fichier
def test_photo_de_8_mio_acceptee(admin):   # MAX_CONTENT_LENGTH admin relevé à 16 Mio
def test_photo_publique(fabrique_app):     # public : GET /photo/<nom> → 200, image/jpeg,
    # Cache-Control contient "immutable" et "max-age=31536000", aucun Set-Cookie ;
    # page /devops : <img class="photo" src="/photo/<nom>"> et
    # <meta property="og:image" content="http://localhost/photo/<nom>">
@pytest.mark.parametrize("nom", ["abc.jpg", "../cv.sqlite3", "0123456789abcdef.png",
                                 "<autre-nom-valide-non-posé>.jpg"])
def test_photo_inconnue_404(fabrique_app, nom): ...
def test_apercu_admin_photo(admin): # /admin/versions/<id>/apercu → src="/admin/photo/<nom>"
def test_slug_photo_reserve(admin): # créer une version de slug "photo" → 400
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_admin_photo.py`
Expected: FAIL (404 sur `/admin/profil/photo`)

- [ ] **Step 8: Implement**

- `Config` : `DOSSIER_PHOTOS` et `DOSSIER_CACHE_PDF`. En rôle admin,
  `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` : une photo de téléphone dépasse 1 Mio.
- `POST /admin/profil/photo`, champ `photo` (`request.files`), formulaire
  `enctype="multipart/form-data"` sur `profil.html` :
  - si `PhotoInvalide`, ou s'il n'y a ni fichier ni profil, la page profil est rendue
    en 400 avec `erreur_photo`, au texte « Ce fichier n'est pas une photo lisible (JPEG,
    PNG ou WEBP, 40 mégapixels au plus). » ;
  - sinon, `enregistrer_photo`, `photo_fichier = nom`, commit, puis suppression de
    l'ancien fichier s'il est différent, et `ok("/admin/profil", "photo-enregistree")`.
- `POST /admin/profil/photo/supprimer` : champ vidé, commit, fichier supprimé, puis
  `ok(…, "photo-supprimee")`.
- `MESSAGES` : « Photo enregistrée. » et « Photo supprimée. ».
- La page profil affiche la photo actuelle (`<img src="/admin/photo/<nom>">`), le
  formulaire d'envoi et le bouton Supprimer (`data-confirmer`).
- Service du fichier : une fonction partagée par `GET /photo/<nom>` (public) et
  `GET /admin/photo/<nom>` (admin). Elle répond 404 sauf si
  `NOM_PHOTO.fullmatch(nom)`, si `nom == profil.photo_fichier` et si le fichier
  existe, puis `send_file(…, mimetype="image/jpeg", max_age=31536000)` avec
  `immutable` dans `Cache-Control`. Le nom dérive du contenu : une nouvelle photo change
  d'URL. Aucune journalisation.
- `assembler_vue(prefixe_medias=…)` : le public passe `""`, l'aperçu admin `"/admin"`.
- `og:image` : seulement en public et si une photo est posée, en URL absolue
  (`CV_URL_PUBLIQUE` ou `request.host_url`, comme `og:url`).
- `SLUGS_RESERVES` reçoit `"photo"`.
- `static/cv.css` : `img.photo` garde `object-fit: cover` (déjà là). Vérifier qu'il
  n'y a pas de fond visible derrière.

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS, ruff propre.

- [ ] **Step 10: Commit**

```bash
git add requirements*.txt cv tests templates static
git commit -m "FEAT(medias): photo du profil, redimensionnée et sans métadonnées"
```

---

### Task 2: QR code des versions

**Files:**
- Modify: `cv/config.py`, `cv/medias.py`, `cv/admin/vues_contenu.py`,
  `templates/admin/version.html`, `static_admin/admin.css`
- Test: `tests/test_medias.py`, `tests/test_admin_qr.py`

**Interfaces:**
- Consumes : `cv.medias` (Task 1).
- Produces :
  - `URL_PAR_DEFAUT = "https://cv.nanodeus.com"` et la propriété
    `Config.URL_SITE -> str` (`URL_PUBLIQUE or URL_PAR_DEFAUT`) ;
  - `url_version(config, slug: str, lang: str, src: str | None = None) -> str` dans
    `cv/medias.py`, qui donne `"{URL_SITE}[/en]/{slug}[?src=…]"` ;
  - `qr(url: str, format: str) -> bytes`, avec `format` dans `("svg", "png")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_url_version(monkeypatch):
    assert url_version(Config(), "devops", "fr", "qr") == "https://cv.nanodeus.com/devops?src=qr"
    monkeypatch.setenv("CV_URL_PUBLIQUE", "https://exemple.test")
    assert url_version(Config(), "lead-tech", "en") == "https://exemple.test/en/lead-tech"

def test_qr_svg_et_png():
    svg = qr("https://cv.nanodeus.com/devops?src=qr", "svg")
    assert svg.lstrip().startswith(b"<?xml") and b"<svg" in svg and b"<script" not in svg
    assert qr("https://cv.nanodeus.com/devops?src=qr", "png").startswith(b"\x89PNG")
```

`tests/test_admin_qr.py` :

- `GET /admin/versions/<id>/qr.svg` → 200 `image/svg+xml`, sans `Content-Disposition`,
  ce qui permet l'aperçu en `<img>`.
- `?telecharger=1&lang=en` sur `qr.png` → `attachment; filename="qr-lead-tech-en.png"`.
- `qr.gif` et une version inconnue → 404.
- Un brouillon a aussi son QR (préparer l'impression).
- La page de la version montre l'URL encodée, `https://cv.nanodeus.com/devops?src=qr`
  et `…/en/devops?src=qr`, plus l'aperçu `<img src="/admin/versions/<id>/qr.svg">` et
  les quatre liens SVG/PNG × FR/EN.
- Décodage : rien à importer. Le contrôle passe par `segno` lui-même : le test
  compare le SVG servi à `qr(url_attendue, "svg")`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_medias.py tests/test_admin_qr.py`
Expected: FAIL (`ImportError: url_version`)

- [ ] **Step 3: Implement**

- `qr` : `segno.make(url, error="m")`. En SVG, `scale=8, border=4` ; en PNG,
  `scale=12, border=4`. Écrire dans un `BytesIO`.
- Route `GET /admin/versions/<int:id_>/qr.<fmt>`, avec `lang=en` en option.
- Section « QR code » sur `version.html`, entre les actions et le formulaire, avec une
  phrase d'aide : « Pointe vers l'adresse publique avec `?src=qr` : les visites venues
  du papier sont comptées à part. »

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cv templates static_admin tests
git commit -m "FEAT(medias): QR code des versions (SVG et PNG, ?src=qr)"
```

---

### Task 3: PDF public et PDF complet

**Files:**
- Create: `cv/pdf.py`, `templates/pdf.html`, `templates/pdf.css`, `tests/test_pdf.py`
- Modify: `cv/vue.py` (`permis`), `cv/public.py`, `cv/admin/vues_contenu.py`,
  `templates/admin/version.html`
- Test: `tests/test_pdf.py`, `tests/test_public.py` (anti-fuite)

**Interfaces:**
- Consumes : `url_version`, `qr` (Task 2) ; `chemin_photo`, `DOSSIER_CACHE_PDF`
  (Task 1).
- Produces :
  - `VueCV.permis: str` (sert au PDF seulement ; la page web ne l'affiche pas) ;
  - `html_pdf(vue: VueCV, config, photo: bytes | None, coordonnees: tuple[str, str] |
    None = None) -> str` ;
  - `rendre_pdf(html: str) -> bytes` ;
  - `pdf_en_cache(dossier: Path, html: str) -> tuple[bytes, str]`, qui renvoie
    `(pdf, etag)` ;
  - `CACHE_MAX = 40`.

- [ ] **Step 1: Write the failing tests** (`tests/test_pdf.py`)

Utilitaire `_texte(pdf: bytes) -> str` : pypdf, toutes les pages, espaces normalisés.

```python
def test_pdf_public(client):   # GET /devops.pdf
    # 200, application/pdf, inline; filename="cv-devops-fr.pdf", ETag, pas de Set-Cookie
    # texte : nom, titre de la version, « Expériences » (ou intitulé choisi),
    #         « cv.nanodeus.com/devops » ; ≤ 2 pages (len(PdfReader.pages) <= 2)
def test_pdf_anglais(client):  # /en/devops.pdf : filename cv-devops-en.pdf, texte anglais
@pytest.mark.parametrize("url", ["/devops.pdf", "/en/devops.pdf", "/lead-tech.pdf",
                                 "/en/lead-tech.pdf"])
def test_pdf_public_sans_coordonnees(client, url):
    texte = _texte(client.get(url).data)
    assert EMAIL not in texte and "99 88 77 66" not in texte
def test_pdf_complet_admin(admin):   # /admin/versions/<id>/cv.pdf?complet=1
    # attachment; filename="cv-devops-fr-complet.pdf" ; texte contient EMAIL et
    # « 99 88 77 66 » (témoin : l'extraction voit bien les coordonnées) ;
    # aucun fichier ajouté dans DOSSIER_CACHE_PDF
def test_pdf_public_depuis_admin_brouillon(admin):  # cv.pdf sans complet, brouillon → 200, sans coordonnées
@pytest.mark.parametrize("url", ["/brouillon.pdf", "/inconnue.pdf", "/Devops.pdf",
                                 "/devops.PDF", "/devops.pdf/x", "/en/brouillon.pdf"])
def test_pdf_404(client, url): ...
def test_page_reste_la_page(client):  # GET /devops → text/html
def test_pdf_non_liste_noindex(client):   # /lead-tech.pdf → X-Robots-Tag: noindex
def test_pdf_journalise(client):  # avec un User-Agent navigateur → Visite(type="pdf", slug, langue)
def test_cache_reutilise_puis_invalide(fabrique_app):
    # 2 GET → même ETag, 1 seul fichier en cache ; If-None-Match → 304 ;
    # accroche modifiée en base → autre ETag, nouveau texte présent
def test_cache_borne(tmp_path):   # 45 html différents (rendre_pdf remplacé par un faux) → 40 fichiers
def test_aucune_ressource_externe(monkeypatch):
    # html contenant <img src="http://127.0.0.1:9/x.png"> et un @import distant :
    # rendre_pdf réussit sans ouvrir de socket (socket.socket remplacé par une
    # fonction qui lève)
def test_metadonnees_sans_coordonnees(client):  # PdfReader.metadata : titre = nom · titre, pas d'email
```

Le test anti-fuite de `tests/test_public.py` reçoit aussi `/devops.pdf` et
`/en/lead-tech.pdf`. Il ne lit que les en-têtes et ne décode pas le binaire : le texte
est contrôlé par `test_pdf_public_sans_coordonnees`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_pdf.py`
Expected: FAIL (`ModuleNotFoundError: cv.pdf`)

- [ ] **Step 3: Implement**

- **`templates/pdf.html`** : document autonome, sans `base.html`, avec
  `<style>{% include "pdf.css" %}</style>`, `lang`, `<title>`, `<meta name="author">`
  et le nom seul. L'ordre suit la spec et la page web.
  - **En-tête** : photo (data URI) ou initiales, nom, titre, localisation · âge ·
    permis, puis l'accroche et les chiffres clés. PDF complet seulement : téléphone et
    email.
  - **Corps** :
    - expériences, de la plus récente à la plus ancienne, sous la forme ✓ intitulé,
      organisation · via, période · durée, puis les missions en puces ;
    - projets perso ;
    - formations ;
    - soft skills et leur preuve ;
    - compétences par catégorie ;
    - centres d'intérêt.
  - **Pied** : le QR (`url_version(…, "qr")`, en data URI) et le lien
    `url_version(…, "pdf")`. Le texte visible est sans schéma :
    `cv.nanodeus.com/devops`.
  - **Texte du pied** : en public, « Pour me contacter : demandez l'accès sur
    cv.nanodeus.com/devops » (traduit) ; en complet, « Version en ligne : … ».
- **`templates/pdf.css`** :
  - `@page { size: A4; margin: 14mm 14mm 16mm; }` ;
  - texte noir sur blanc, accents en gris, un seul vert pour les ✓, lisible imprimé en
    noir et blanc ;
  - polices `"DejaVu Sans", "Helvetica Neue", Arial, sans-serif`, et la variante mono
    pour les périodes et les durées ;
  - `break-inside: avoid` sur chaque job.
  - Objectif : **2 pages au plus** avec le contenu amorcé, vérifié par le test.
- **`rendre_pdf`** :
  - `HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=("data",))).write_pdf()` ;
  - une alerte de WeasyPrint sur une ressource refusée ne fait pas échouer le rendu.
- **`pdf_en_cache`** :
  - `etag = sha256(html)[:32]` ;
  - si `<dossier>/<etag>.pdf` existe, il est servi (son mtime est rafraîchi) ;
  - sinon, rendu, puis écriture dans un fichier temporaire et `os.replace` ;
  - ensuite, seuls les `CACHE_MAX` fichiers les plus récents sont gardés.
  - Le HTML contient déjà la photo, le QR, la feuille de style et les durées du jour :
    tout changement de contenu change la clé. Aucune invalidation explicite.
- **Public** (`cv/public.py`), `@bp.get("/<slug>.pdf")` et `@bp.get("/en/<slug>.pdf")` :
  - slug validé par `_SLUG`, vue par `assembler_vue`, `None` → 404 ;
  - `pdf_en_cache`, puis `make_conditional` (304) ;
  - en-têtes `Content-Disposition: inline; filename="cv-<slug>-<lang>.pdf"`,
    `Cache-Control: no-cache` et `X-Robots-Tag: noindex` pour une version non listée ;
  - `journaliser(…, "pdf", …)`.
- **Admin**, `GET /admin/versions/<int:id_>/cv.pdf` (options `lang=en` et `complet=1`) :
  - vue rendue avec `apercu=True` ;
  - avec `complet`, `coordonnees=(profil.telephone or "", profil.email or "")` et
    `rendre_pdf` direct, sans cache ;
  - sinon `pdf_en_cache` ;
  - toujours `attachment`, `filename="cv-<slug>-<lang>[-complet].pdf"` ;
  - liens « PDF public FR/EN » et « PDF complet FR/EN » sur `version.html`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS. Ouvrir `/devops.pdf` et `/en/lead-tech.pdf` dans un lecteur PDF. Ils
doivent faire 2 pages au plus et rester lisibles en niveaux de gris. Captures dans le
scratchpad seulement.

- [ ] **Step 5: Commit**

```bash
git add cv templates tests
git commit -m "FEAT(pdf): PDF public et complet, en cache selon le contenu"
```

---

### Task 4: Lien « Artefacts », traductions et vérification navigateur

**Files:**
- Modify: `templates/_pied.html`, `cv/public.py`, `cv/admin/vues_contenu.py`,
  `translations/en/LC_MESSAGES/messages.po`, `static/cv.css` si besoin
- Test: `tests/test_page.py`, `tests/test_i18n_catalogue.py` (existant)

**Interfaces:**
- Consumes : routes PDF (Task 3).
- Produces : variable de template `url_pdf`. En public, elle vaut `"[/en]/<slug>.pdf"` ;
  dans l'aperçu admin, `"/admin/versions/<id>/cv.pdf?lang=<lang>"`.

- [ ] **Step 1: Write the failing tests**

- Un test sur `/devops` : la section Artefacts existe toujours, y compris sans LinkedIn
  ni GitHub, et son premier lien est `href="/devops.pdf"`, libellé « CV · PDF ».
- `/en/devops` donne `href="/en/devops.pdf"` et le libellé anglais.
- Dans l'aperçu admin, le lien PDF mène à `/admin/versions/<id>/cv.pdf?lang=fr`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/test_page.py`
Expected: FAIL

- [ ] **Step 3: Implement**

- `_pied.html` : la section Artefacts n'est plus conditionnelle. Son premier élément
  est 📄 CV · PDF, avec le bouton « Télécharger ». LinkedIn et GitHub suivent comme
  aujourd'hui.
- `.venv/bin/python scripts/i18n.py update`, puis traduire toutes les nouvelles
  entrées (pied, PDF).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: PASS (le catalogue n'a aucune entrée vide ni `fuzzy`).

- [ ] **Step 5: Vérification navigateur (Playwright, script dans le scratchpad)**

- Serveurs public et admin sur une base amorcée, avec une photo de test générée par
  Pillow et envoyée par le formulaire admin.
- Vérifier, à 1280 px puis à 375 px :
  - la photo du bandeau ;
  - le lien PDF, qui répond `application/pdf` ;
  - le profil admin : aperçu de la photo, envoi, suppression ;
  - la section QR de la version.
- Partout : aucune erreur CSP en console, aucun débordement horizontal.

Expected: toutes les vérifications OK.

- [ ] **Step 6: Commit**

```bash
git add templates cv translations static tests
git commit -m "FEAT(public): lien PDF dans les Artefacts"
```

---

## Après ce plan

- **Plan 4 (Dockerfile)** :
  - paquets `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0` et
    `fonts-dejavu-core` dans l'image, sans quoi WeasyPrint ne démarre pas ;
  - le volume de données contient `photos/` et `cache-pdf/`, qu'admin et public
    partagent ;
  - la sauvegarde restic inclut `photos/` ; `cache-pdf/` peut en être exclu.
- La CI devra installer Pango pour les tests du PDF.
