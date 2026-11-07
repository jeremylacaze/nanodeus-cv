"""Ce qui tourne en ligne : commit et date du build, pour le pied de page."""
from datetime import UTC, datetime, timedelta

from babel.dates import format_timedelta


def deploiement(config, lang: str, maintenant: datetime | None = None) -> dict | None:
    """None hors d'une image construite par la release (développement, tests)."""
    if not config.COMMIT:
        return None
    quand = date = ""
    if config.CONSTRUIT_LE:
        maintenant = maintenant or datetime.now(UTC)
        # Horloges décalées entre la CI et le serveur : jamais « dans 2 minutes ».
        ecart = min(config.CONSTRUIT_LE - maintenant, -timedelta(seconds=1))
        quand = format_timedelta(ecart, add_direction=True, locale=lang)
        date = config.CONSTRUIT_LE.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"court": config.COMMIT[:7], "url": f"{config.URL_DEPOT}/commit/{config.COMMIT}",
            "quand": quand, "date": date}
