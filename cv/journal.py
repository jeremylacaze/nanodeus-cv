"""Journal des visites du site public, sans IP ni cookie.

Un visiteur est représenté par une empreinte HMAC dont la clé combine le secret
serveur et un sel aléatoire du jour. Le sel de la veille est supprimé : on compte
les visiteurs uniques d'une journée sans pouvoir suivre quelqu'un d'un jour à
l'autre ni retrouver une IP.
"""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from cv.models import SelJournalier, Visite

logger = logging.getLogger(__name__)

CONSERVATION = timedelta(days=183)
_ROBOT = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|curl|wget|"
                    r"python|httpx|go-http|okhttp|java/|scrapy|headless|monitor|uptime", re.I)
_MOBILE = re.compile(r"Mobi|Android|iPhone|iPad|iPod")
_SRC_INTERDIT = re.compile(r"[^a-z0-9._-]")


def maintenant_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _lire_sel(session, jour: date) -> bytes | None:
    return session.scalar(select(SelJournalier.valeur).where(SelJournalier.jour == jour))


def sel_du_jour(session, maintenant: datetime) -> bytes:
    """Sel du jour (UTC), créé au premier besoin. Sa création jette les sels
    précédents et purge les visites de plus de 6 mois : une fois par jour, sans cron."""
    jour = maintenant.date()
    sel = _lire_sel(session, jour)
    if sel is not None:
        return sel
    sel = secrets.token_bytes(32)
    try:
        session.add(SelJournalier(jour=jour, valeur=sel))
        session.flush()
        session.execute(delete(SelJournalier).where(SelJournalier.jour < jour))
        session.execute(delete(Visite).where(Visite.horodatage < maintenant - CONSERVATION))
        session.commit()
    except IntegrityError:
        # Un autre processus l'a créé entre-temps : on reprend le sien.
        session.rollback()
        sel = _lire_sel(session, jour)
    return sel


def empreinte(session, secret: str, *parties: str, maintenant: datetime) -> str:
    cle = secret.encode() + sel_du_jour(session, maintenant)
    return hmac.new(cle, "\x1f".join(parties).encode(), hashlib.sha256).hexdigest()[:32]


def classer(user_agent: str) -> str | None:
    """Type de visite d'après le User-Agent ; None pour un robot (ignoré)."""
    if "LinkedInBot" in user_agent:
        return "apercu_linkedin"
    if not user_agent or _ROBOT.search(user_agent):
        return None
    return "page"


def appareil(user_agent: str) -> str:
    return "mobile" if _MOBILE.search(user_agent) else "ordinateur"


def source(req) -> str:
    """`?src=` s'il est donné (le QR code), sinon le domaine du Referer."""
    src = _SRC_INTERDIT.sub("", req.args.get("src", "").lower())[:40]
    if src:
        return src
    hote = urlsplit(req.referrer or "").hostname
    if not hote:
        return "direct"
    if hote == urlsplit("//" + req.host).hostname:
        return "interne"
    return hote.removeprefix("www.")[:100]


def _prechargement(req) -> bool:
    entetes = (req.headers.get("Purpose", "") + req.headers.get("Sec-Purpose", "")).lower()
    return "prefetch" in entetes


def journaliser(session, req, config, type: str, version_slug: str, langue: str,
                maintenant: datetime | None = None) -> None:
    """Note une visite. N'échoue jamais : un journal en panne ne casse pas la page."""
    if req.method == "HEAD" or _prechargement(req):
        return
    ua = req.user_agent.string or ""
    classe = classer(ua)
    if classe is None:
        return
    if classe == "apercu_linkedin":
        type = classe
    maintenant = maintenant or maintenant_utc()
    try:
        session.add(Visite(
            horodatage=maintenant, type=type, version_slug=version_slug, langue=langue,
            source=source(req), appareil=appareil(ua),
            empreinte=empreinte(session, config.SEL_HMAC, req.remote_addr or "", ua,
                                maintenant=maintenant)))
        session.commit()
    except Exception as exc:  # noqa: BLE001 — le journal ne doit jamais casser la page
        session.rollback()
        # Le nom de l'exception seulement : son message pourrait contenir une valeur.
        logger.warning("journal des visites : %s", exc.__class__.__name__)
