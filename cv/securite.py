"""En-têtes de sécurité du site : CSP à nonce bloquante, aucun cookie."""
import secrets

from flask import g
from werkzeug.middleware.proxy_fix import ProxyFix


def _csp(nonce: str) -> str:
    return ("default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


def init_securite(app):
    if app.config["CV"].TRUST_PROXY:
        # Un seul saut : Traefik devant le conteneur.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    public = app.config["CV"].ROLE == "public"

    @app.before_request
    def _poser_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

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
        if public:
            # Filet : le site public ne pose jamais de cookie (pas de bandeau à afficher).
            del reponse.headers["Set-Cookie"]
        return reponse
