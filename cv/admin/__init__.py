"""Admin du CV : édition du contenu et suivi, joignable depuis le tailnet seulement.

Aucun cookie, ni session ni flash : après une écriture réussie, une redirection 303
porte `?ok=<code>`, et seul le texte fixe de `MESSAGES` est affiché.
"""
from pathlib import Path

from flask import Blueprint, current_app, request

from cv.admin.libelles import libelle

RACINE = Path(__file__).resolve().parent.parent.parent

# Fichiers statiques à part : le site public ne les sert pas.
bp = Blueprint("admin", __name__, url_prefix="/admin",
               static_folder=str(RACINE / "static_admin"), static_url_path="/static")

MESSAGES = {
    "enregistre": "Modifications enregistrées.",
    "supprime": "Élément supprimé.",
    "par-defaut": "Version par défaut changée.",
    "defaut-brouillon": "Un brouillon ne peut pas être la version par défaut.",
    "defaut-protege": "La version par défaut ne peut pas être supprimée : "
                      "choisissez-en d'abord une autre.",
    "renvoyee": "Demande envoyée.",
    "echec-envoi": "L'envoi a encore échoué : voir l'erreur dans la liste.",
    "deja-envoyee": "Cette demande est déjà envoyée ou en cours d'envoi.",
    "test-envoye": "Email de test envoyé.",
    "photo-enregistree": "Photo enregistrée.",
    "photo-supprimee": "Photo supprimée.",
}


bp.add_app_template_filter(libelle, "libelle")


@bp.context_processor
def _contexte():
    return {"message_ok": MESSAGES.get(request.args.get("ok", "")),
            "url_site": current_app.config["CV"].URL_SITE}


from cv.admin import vues_contenu, vues_suivi  # noqa: E402,F401
