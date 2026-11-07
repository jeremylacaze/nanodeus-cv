"""Régénère les icônes matricielles du site à partir du dessin de static/favicon.svg.

    python scripts/icones.py

Pillow ne lit pas le SVG : le même dessin (✓ blanc sur disque vert, façon job réussi)
est retracé ici, suréchantillonné puis réduit pour des bords lisses. Les fichiers
produits sont versionnés ; ce script ne sert qu'à les refaire.
"""
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "static"
VERT, BLANC, FOND = (31, 136, 61, 255), (255, 255, 255, 255), (13, 17, 23, 255)
# Coordonnées du SVG (viewBox 32×32).
COCHE = [(9.5, 16.5), (14, 21), (22.5, 11.5)]


def dessiner(taille: int, fond: tuple | None = None, marge: float = 0.0) -> Image.Image:
    """Icône carrée ; `marge` (fraction de la taille) laisse de l'air autour du disque."""
    sur = 8
    cote = taille * sur
    img = Image.new("RGBA", (cote, cote), fond or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    echelle = cote * (1 - 2 * marge) / 32
    decalage = cote * marge

    def point(x, y):
        return decalage + x * echelle, decalage + y * echelle

    d.ellipse([point(1, 1), point(31, 31)], fill=VERT)
    trait = round(3.4 * echelle)
    points = [point(x, y) for x, y in COCHE]
    d.line(points, fill=BLANC, width=trait, joint="curve")
    for x, y in (points[0], points[-1]):  # extrémités arrondies (stroke-linecap)
        d.ellipse([x - trait / 2, y - trait / 2, x + trait / 2, y + trait / 2], fill=BLANC)
    return img.resize((taille, taille), Image.Resampling.LANCZOS)


def main() -> None:
    dessiner(48).save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # iOS arrondit lui-même les coins et refuse la transparence : fond plein.
    dessiner(180, fond=FOND, marge=0.14).convert("RGB").save(
        STATIC / "apple-touch-icon.png", optimize=True)


if __name__ == "__main__":
    main()
