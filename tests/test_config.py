"""Mode production : aucun secret de développement ne doit partir en ligne."""
import pytest

from cv.config import Config

SECRETS = ("SECRET_KEY", "CV_SEL_HMAC")


@pytest.fixture
def prod(monkeypatch):
    """Environnement de production complet ; chaque test en retire un morceau."""
    monkeypatch.setenv("CV_PROD", "1")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("CV_SEL_HMAC", "b" * 64)
    monkeypatch.setenv("CV_URL_PUBLIQUE", "https://cv.nanodeus.com")
    return monkeypatch


@pytest.mark.parametrize("variable", SECRETS)
@pytest.mark.parametrize("valeur", [None, "", "dev-uniquement"], ids=["absente", "vide", "dev"])
def test_prod_refuse_les_secrets_de_dev(prod, variable, valeur):
    if valeur is None:
        prod.delenv(variable)
    else:
        prod.setenv(variable, valeur)
    with pytest.raises(ValueError, match=variable):
        Config()


def test_prod_exige_l_url_publique(prod):
    prod.delenv("CV_URL_PUBLIQUE")
    with pytest.raises(ValueError, match="CV_URL_PUBLIQUE"):
        Config()


def test_prod_complete_demarre(prod):
    config = Config()
    assert config.PROD and config.SECRET_KEY == "a" * 64


def test_hors_prod_les_defauts_restent(monkeypatch):
    for variable in ("CV_PROD", *SECRETS, "CV_URL_PUBLIQUE"):
        monkeypatch.delenv(variable, raising=False)
    config = Config()
    assert not config.PROD
    assert config.SECRET_KEY == config.SEL_HMAC == "dev-uniquement"
