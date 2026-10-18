"""Admin : édition du profil, du stock et des versions."""
from flask import abort, g, redirect, render_template, request
from sqlalchemy import select

from cv.admin import bp
from cv.admin.formulaires import MAX_TEXTE, Champ, appliquer, lire, valeurs_de
from cv.admin.stock import TYPES, supprimer_element
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


def _type_stock(cle: str):
    return TYPES.get(cle) or abort(404)


def _element(type_stock, id_: int):
    return g.db.get(type_stock.modele, id_) or abort(404)


@bp.get("/stock/<cle>")
def stock_liste(cle):
    t = _type_stock(cle)
    elements = g.db.scalars(select(t.modele).order_by(*t.tri)).all()
    return render_template("admin/stock_liste.html", t=t, elements=elements)


def _editer(t, obj):
    """Création (obj None) ou modification d'un élément du stock."""
    if request.method == "POST":
        valeurs, erreurs = lire(request.form, t.champs)
        if not erreurs and t.verifier:
            erreurs = t.verifier(valeurs)
        if not erreurs:
            if obj is None:
                obj = t.modele()
                g.db.add(obj)
            appliquer(obj, valeurs)
            g.db.commit()
            return ok(f"/admin/stock/{t.cle}")
        return render_template("admin/stock_element.html", t=t, obj=obj,
                               valeurs=request.form.to_dict(), erreurs=erreurs), 400
    return render_template("admin/stock_element.html", t=t, obj=obj,
                           valeurs=valeurs_de(obj, t.champs) if obj else {}, erreurs={})


@bp.route("/stock/<cle>/nouveau", methods=["GET", "POST"])
def stock_nouveau(cle):
    return _editer(_type_stock(cle), None)


@bp.route("/stock/<cle>/<int:id_>", methods=["GET", "POST"])
def stock_element(cle, id_):
    t = _type_stock(cle)
    return _editer(t, _element(t, id_))


@bp.post("/stock/<cle>/<int:id_>/supprimer")
def stock_supprimer(cle, id_):
    t = _type_stock(cle)
    supprimer_element(g.db, t, _element(t, id_))
    return ok(f"/admin/stock/{t.cle}", "supprime")
