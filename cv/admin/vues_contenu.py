"""Admin : édition du profil, du stock et des versions."""
from flask import g, redirect, render_template, request

from cv.admin import bp
from cv.admin.formulaires import MAX_TEXTE, Champ, appliquer, lire, valeurs_de
from cv.models import Profil

PRIVE = "Privé : sert seulement au PDF complet, jamais au site public."

CHAMPS_PROFIL = (
    Champ("nom_complet", "Nom complet", max=120, requis=True),
    Champ("localisation", "Localisation", max=120),
    Champ("date_naissance", "Date de naissance", type="date"),
    Champ("afficher_age", "Afficher l'âge", type="case"),
    Champ("permis", "Permis", max=60),
    Champ("ouvert_opportunites", "Ouvert aux opportunités", type="case"),
    Champ("interets_fr", "Centres d'intérêt (FR)", type="texte", max=MAX_TEXTE,
          aide="Un par ligne."),
    Champ("interets_en", "Centres d'intérêt (EN)", type="texte", max=MAX_TEXTE,
          aide="Un par ligne ; vide = repli sur le français."),
    Champ("linkedin_url", "LinkedIn", type="url", max=300),
    Champ("github_url", "GitHub", type="url", max=300),
    Champ("telephone", "Téléphone", max=40, aide=PRIVE),
    Champ("email", "Email", max=200, aide=PRIVE),
)


def ok(chemin: str, code: str = "enregistre"):
    """Redirection après écriture : le message est choisi par son code (MESSAGES)."""
    separateur = "&" if "?" in chemin else "?"
    ancre = ""
    if "#" in chemin:
        chemin, ancre = chemin.split("#", 1)
        ancre = "#" + ancre
    return redirect(f"{chemin}{separateur}ok={code}{ancre}", 303)


@bp.route("/profil", methods=["GET", "POST"])
def profil():
    actuel = g.db.get(Profil, 1)
    if request.method == "POST":
        valeurs, erreurs = lire(request.form, CHAMPS_PROFIL)
        if not erreurs:
            if actuel is None:
                actuel = Profil(id=1)
                g.db.add(actuel)
            appliquer(actuel, valeurs)
            g.db.commit()
            return ok("/admin/profil")
        return render_template("admin/profil.html", liste=CHAMPS_PROFIL,
                               valeurs=request.form.to_dict(), erreurs=erreurs), 400
    return render_template("admin/profil.html", liste=CHAMPS_PROFIL,
                           valeurs=valeurs_de(actuel, CHAMPS_PROFIL), erreurs={})
