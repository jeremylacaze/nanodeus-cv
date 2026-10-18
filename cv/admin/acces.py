"""Accès à l'admin : adresse source du tailnet et hôte attendu, réponses jamais en cache.

Le bind du port sur l'IP tailnet est la barrière principale ; ces contrôles sont la
défense en profondeur. Le contrôle de l'hôte arrête le DNS rebinding : une page
tierce dont le domaine pointerait vers l'IP de l'admin lirait sinon ses pages depuis
le navigateur de Jeremy, et ses POST passeraient le contrôle d'Origin (même hôte). `TRUST_PROXY` est refusé en rôle admin (cv/config.py) :
`remote_addr` est donc toujours l'adresse vue par le serveur, jamais un en-tête.
"""
from ipaddress import ip_address
from urllib.parse import urlsplit

from flask import abort, current_app, request

from cv.config import RESEAUX_PAR_DEFAUT, lire_reseaux

__all__ = ["RESEAUX_PAR_DEFAUT", "adresse_autorisee", "hote_autorise", "init_acces",
           "lire_reseaux"]


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


def hote_autorise(hote: str, hotes) -> bool:
    """`hote` : l'en-tête Host, port compris (localhost:5011, [::1]:5011)."""
    try:
        nom = urlsplit("//" + hote).hostname
    except ValueError:
        return False
    return nom is not None and nom in hotes


def init_acces(app):
    @app.before_request
    def _controler_acces():
        config = current_app.config["CV"]
        if not (adresse_autorisee(request.remote_addr, config.ADMIN_RESEAUX)
                and hote_autorise(request.host, config.ADMIN_HOTES)):
            abort(403)

    @app.after_request
    def _jamais_en_cache(reponse):
        # Le profil affiché contient le téléphone et l'email.
        reponse.headers["Cache-Control"] = "no-store"
        reponse.headers["X-Robots-Tag"] = "noindex"
        return reponse
