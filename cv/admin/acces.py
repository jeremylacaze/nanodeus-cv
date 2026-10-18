"""Accès à l'admin : adresse source du tailnet seulement, réponses jamais en cache.

Le bind du port sur l'IP tailnet est la barrière principale ; ce contrôle est la
défense en profondeur. `TRUST_PROXY` est refusé en rôle admin (cv/config.py) :
`remote_addr` est donc toujours l'adresse vue par le serveur, jamais un en-tête.
"""
from ipaddress import ip_address

from flask import abort, current_app, request

from cv.config import RESEAUX_PAR_DEFAUT, lire_reseaux

__all__ = ["RESEAUX_PAR_DEFAUT", "adresse_autorisee", "init_acces", "lire_reseaux"]


def adresse_autorisee(adresse: str | None, reseaux) -> bool:
    if not reseaux:
        return True
    try:
        ip = ip_address(adresse or "")
    except ValueError:
        return False
    # ::ffff:100.64.0.7 : une IPv4 vue par une socket IPv6.
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return any(ip.version == r.version and ip in r for r in reseaux)


def init_acces(app):
    @app.before_request
    def _controler_adresse():
        if not adresse_autorisee(request.remote_addr, current_app.config["CV"].ADMIN_RESEAUX):
            abort(403)

    @app.after_request
    def _jamais_en_cache(reponse):
        # Le profil affiché contient le téléphone et l'email.
        reponse.headers["Cache-Control"] = "no-store"
        reponse.headers["X-Robots-Tag"] = "noindex"
        return reponse
