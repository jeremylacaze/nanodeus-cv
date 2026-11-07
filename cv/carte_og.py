"""Carte d'aperçu (og:image) 1200×630 : nom, titre, accroche et le parcours en
pipeline, comme la page. Rendue avec Pillow, en cache selon son contenu.

Les polices sont les DejaVu de l'image (celles du PDF) ; ailleurs, la police
intégrée à Pillow, pour que la carte se rende toujours, même moins jolie.
"""
import hashlib
import json
import os
from functools import cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from cv.medias import ecrire_atomiquement

LARGEUR, HAUTEUR = 1200, 630
MARGE = 72
CACHE_MAX = 40
# Toute retouche du dessin change cette valeur, donc la clé du cache.
DESSIN = "1"

FOND, CARTE, BORD = "#0d1117", "#161b22", "#30363d"
TEXTE, MUTED, OK, RUN = "#e6edf3", "#8b949e", "#3fb950", "#d29922"

DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
POLICES = {"gras": "DejaVuSans-Bold.ttf", "normal": "DejaVuSans.ttf", "mono": "DejaVuSansMono.ttf"}


@cache
def _police(style: str, taille: int) -> ImageFont.FreeTypeFont:
    chemin = DEJAVU / POLICES[style]
    if chemin.exists():
        return ImageFont.truetype(str(chemin), taille)
    return ImageFont.load_default(taille)


def _largeur(texte: str, police) -> float:
    return police.getlength(texte)


def _tronquer(texte: str, police, largeur: float) -> str:
    if _largeur(texte, police) <= largeur:
        return texte
    while texte and _largeur(texte + "…", police) > largeur:
        texte = texte[:-1]
    return texte.rstrip() + "…"


def _lignes(texte: str, police, largeur: float, maximum: int) -> list[str]:
    """Coupe aux espaces ; la dernière ligne gardée finit par « … » s'il en reste."""
    lignes, courante = [], ""
    for mot in texte.split():
        essai = f"{courante} {mot}".strip()
        if _largeur(essai, police) <= largeur or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    if len(lignes) > maximum:
        lignes = lignes[:maximum]
        lignes[-1] = _tronquer(lignes[-1] + " …", police, largeur)
    return [_tronquer(ligne, police, largeur) for ligne in lignes]


def _coche(dessin: ImageDraw.ImageDraw, cx: float, cy: float, rayon: float, couleur: str) -> None:
    dessin.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), fill=couleur)
    r = rayon
    dessin.line([(cx - .45 * r, cy + .03 * r), (cx - .12 * r, cy + .36 * r),
                 (cx + .48 * r, cy - .32 * r)], fill=FOND, width=max(3, round(r * .24)),
                joint="curve")


def _en_cours(dessin: ImageDraw.ImageDraw, cx: float, cy: float, rayon: float) -> None:
    dessin.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), outline=RUN,
                   width=max(3, round(rayon * .22)))
    p = rayon * .38
    dessin.ellipse((cx - p, cy - p, cx + p, cy + p), fill=RUN)


def _portrait(photo: bytes | None, initiales: str, diametre: int) -> Image.Image:
    """Photo ronde, ou les initiales sur un disque si elle manque ou est illisible."""
    masque = Image.new("L", (diametre * 4, diametre * 4), 0)
    ImageDraw.Draw(masque).ellipse((0, 0, diametre * 4 - 1, diametre * 4 - 1), fill=255)
    masque = masque.resize((diametre, diametre), Image.Resampling.LANCZOS)
    rond = Image.new("RGBA", (diametre, diametre), (0, 0, 0, 0))
    image = None
    if photo:
        try:
            image = ImageOps.fit(Image.open(BytesIO(photo)).convert("RGB"),
                                 (diametre, diametre), Image.Resampling.LANCZOS)
        except (OSError, ValueError):
            image = None
    if image is None:
        image = Image.new("RGB", (diametre, diametre), CARTE)
        dessin = ImageDraw.Draw(image)
        police = _police("gras", diametre // 3)
        dessin.text((diametre / 2, diametre / 2), initiales, font=police, fill=MUTED, anchor="mm")
    rond.paste(image, (0, 0), masque)
    return rond


def contenu_carte(vue, adresse: str) -> dict:
    """Tout ce que dessine la carte, et rien d'autre : c'est aussi la clé du cache."""
    etapes = [job.organisation or job.intitule for job in vue.formations + vue.postes][-4:]
    return {"dessin": DESSIN, "nom": vue.nom, "titre": vue.titre, "accroche": vue.accroche,
            "etapes": etapes, "prochaine": vue.prochaine_mission, "adresse": adresse,
            "initiales": (("".join(m[0] for m in vue.nom.split())).upper())[:2]}


def dessiner_carte(contenu: dict, photo: bytes | None) -> bytes:
    image = Image.new("RGB", (LARGEUR, HAUTEUR), FOND)
    dessin = ImageDraw.Draw(image)
    dessin.rounded_rectangle((24, 24, LARGEUR - 24, HAUTEUR - 24), radius=18,
                             fill=CARTE, outline=BORD, width=2)

    diametre = 172
    x_portrait = LARGEUR - MARGE - diametre
    portrait = _portrait(photo, contenu["initiales"], diametre)
    image.paste(portrait, (x_portrait, MARGE + 8), portrait)
    dessin.ellipse((x_portrait - 3, MARGE + 5, x_portrait + diametre + 2, MARGE + diametre + 10),
                   outline=BORD, width=3)
    largeur_texte = x_portrait - MARGE - 40

    y = MARGE + 4
    _coche(dessin, MARGE + 14, y + 16, 14, OK)
    dessin.text((MARGE + 40, y + 16), _tronquer(contenu["adresse"], _police("mono", 24),
                largeur_texte - 40), font=_police("mono", 24), fill=MUTED, anchor="lm")
    y += 58
    police_nom = _police("gras", 62)
    for ligne in _lignes(contenu["nom"], police_nom, largeur_texte, 2):
        dessin.text((MARGE, y), ligne, font=police_nom, fill=TEXTE)
        y += 74
    if contenu["titre"]:
        police_titre = _police("normal", 34)
        dessin.text((MARGE, y + 4), _tronquer(contenu["titre"], police_titre, largeur_texte),
                    font=police_titre, fill=OK)
        y += 56
    if contenu["accroche"]:
        police_accroche = _police("normal", 26)
        for ligne in _lignes(contenu["accroche"], police_accroche, LARGEUR - 2 * MARGE, 2):
            dessin.text((MARGE, y + 10), ligne, font=police_accroche, fill=MUTED)
            y += 36

    # Le parcours en pipeline : les dernières étapes réussies, puis celle en cours.
    noeuds = [(nom, "ok") for nom in contenu["etapes"]]
    if contenu["prochaine"]:
        noeuds.append((contenu["prochaine"], "run"))
    if noeuds:
        y_ligne, rayon = HAUTEUR - MARGE - 50, 15
        # La prochaine mission a un libellé plus long que le nom d'une organisation :
        # plus de place, et deux lignes.
        poids = [1 if etat == "ok" else 1.5 for _nom, etat in noeuds]
        unite = (LARGEUR - 2 * MARGE) / sum(poids)
        debuts = [MARGE + unite * sum(poids[:i]) for i in range(len(noeuds))]
        centres = [debut + rayon for debut in debuts]
        if len(centres) > 1:
            dessin.line([(centres[0], y_ligne), (centres[-1], y_ligne)], fill=BORD, width=4)
        police_etape = _police("normal", 22)
        for (nom, etat), cx, p in zip(noeuds, centres, poids, strict=True):
            if etat == "ok":
                _coche(dessin, cx, y_ligne, rayon, OK)
            else:
                _en_cours(dessin, cx, y_ligne, rayon)
            lignes = (_lignes(nom, police_etape, unite * p - 16, 2) if etat == "run"
                      else [_tronquer(nom, police_etape, unite * p - 16)])
            for n, ligne in enumerate(lignes):
                dessin.text((cx - rayon, y_ligne + rayon + 14 + 28 * n), ligne, font=police_etape,
                            fill=TEXTE if etat == "ok" else RUN)

    tampon = BytesIO()
    image.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


def _date(chemin: Path) -> int:
    try:
        return chemin.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def carte_en_cache(dossier: Path, contenu: dict, photo: bytes | None) -> tuple[bytes, str]:
    """PNG de cette carte, dessiné une seule fois ; renvoie aussi son ETag."""
    empreinte = hashlib.sha256(json.dumps(contenu, sort_keys=True).encode())
    empreinte.update(hashlib.sha256(photo or b"").digest())
    etag = empreinte.hexdigest()[:32]
    chemin = dossier / f"{etag}.png"
    try:
        png = chemin.read_bytes()
    except FileNotFoundError:
        pass
    else:
        try:
            os.utime(chemin)  # récent : l'élagage le garde
        except FileNotFoundError:
            pass
        return png, etag
    png = dessiner_carte(contenu, photo)
    ecrire_atomiquement(chemin, png)
    for ancien in sorted(dossier.glob("*.png"), key=_date, reverse=True)[CACHE_MAX:]:
        if ancien != chemin:
            ancien.unlink(missing_ok=True)
    return png, etag
