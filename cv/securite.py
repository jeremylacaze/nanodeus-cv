"""En-têtes de sécurité du site : CSP à nonce bloquante, aucun cookie."""
import secrets
from urllib.parse import urlsplit

from flask import abort, g, request
from werkzeug.middleware.proxy_fix import ProxyFix


def _csp(nonce: str) -> str:
    return ("default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


_METHODES_A_EFFET = ("POST", "PUT", "PATCH", "DELETE")


def origine_valide(req) -> bool:
    """`Origin` présent et du même site. Tous les navigateurs actuels l'envoient sur
    un POST : son absence trahit un script, sa différence une page tierce (CSRF)."""
    origine = req.headers.get("Origin", "")
    return origine not in ("", "null") and urlsplit(origine).netloc == req.host


def init_securite(app):
    if app.config["CV"].TRUST_PROXY:
        # Un seul saut : Traefik devant le conteneur.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    public = app.config["CV"].ROLE == "public"

    @app.before_request
    def _poser_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def _controler_origine():
        if request.method in _METHODES_A_EFFET and not origine_valide(request):
            abort(403)

    @app.context_processor
    def _contexte_nonce():
        return {"csp_nonce": g.get("csp_nonce", "")}

    @app.after_request
    def _entetes(reponse):
        nonce = g.get("csp_nonce") or secrets.token_urlsafe(16)
        reponse.headers["Content-Security-Policy"] = _csp(nonce)
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if public and request.is_secure:
            # Un an, sans includeSubDomains ni preload : rien d'irréversible pour le domaine.
            reponse.headers["Strict-Transport-Security"] = "max-age=31536000"
        if public:
            # Filet : le site public ne pose jamais de cookie (pas de bandeau à afficher).
            del reponse.headers["Set-Cookie"]
        return reponse
