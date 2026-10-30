"""Limitation de débit par utilisateur : clé, 429 au format unique, ouverture si cache en panne."""

import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.users.models import Role, User
from tests.factories import make_user

GENERER = "/api/v1/documents/generate/"
APERCU_FORMAT = "/api/v1/numbering-formats/preview/"


class Horloge:
    """Horloge contrôlée : aucune attente réelle, aucun test dépendant du temps."""

    def __init__(self) -> None:
        self.maintenant = 1_000_000.0

    def __call__(self) -> float:
        return self.maintenant


@pytest.fixture
def horloge(monkeypatch: pytest.MonkeyPatch) -> Horloge:
    h = Horloge()
    monkeypatch.setattr(SimpleRateThrottle, "timer", staticmethod(h))
    return h


@pytest.fixture(autouse=True)
def _cache_propre() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


def _taux(**taux: str) -> Any:
    base: dict[str, Any] = settings.REST_FRAMEWORK
    return override_settings(
        REST_FRAMEWORK={
            **base,
            "DEFAULT_THROTTLE_RATES": {**base["DEFAULT_THROTTLE_RATES"], **taux},
        }
    )


def _client(utilisateur: User, adresse: str = "198.51.100.9") -> APIClient:
    client = APIClient(REMOTE_ADDR=adresse)
    client.force_authenticate(user=utilisateur)
    return client


def _apercu(client: APIClient) -> int:
    return client.post(APERCU_FORMAT, {}, format="json").status_code


def test_taux_par_defaut_conformes_a_d3() -> None:
    taux = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert taux == {
        "generation": "20/min",
        "apercu": "30/min",
        "televersement": "30/hour",
        "import": "10/hour",
        "export": "30/min",
        "anonyme": "30/min",
        "annuaire": "60/min",
    }


@pytest.mark.django_db
def test_21e_generation_dans_la_minute_429(rai: User, horloge: Horloge) -> None:
    client = _client(rai)
    for _ in range(20):
        assert client.post(GENERER, {}, format="json").status_code != 429
    reponse = client.post(GENERER, {}, format="json")
    assert reponse.status_code == 429
    assert reponse.json() == {
        "detail": "Trop de requêtes : réessayez dans 60 secondes.",
        "errors": {},
    }
    assert reponse["Retry-After"] == "60"


@pytest.mark.django_db
def test_retry_after_decroit_et_la_fenetre_se_libere(admin: User, horloge: Horloge) -> None:
    client = _client(admin)
    with _taux(apercu="2/min"):
        assert _apercu(client) != 429
        assert _apercu(client) != 429
        horloge.maintenant += 10.2
        reponse = client.post(APERCU_FORMAT, {}, format="json")
        assert reponse.status_code == 429
        assert reponse["Retry-After"] == "50"
        assert "50 secondes" in reponse.json()["detail"]
        horloge.maintenant += 50
        assert _apercu(client) != 429


@pytest.mark.django_db
def test_deux_utilisateurs_derriere_la_meme_adresse_ne_se_genent_pas(
    admin: User, horloge: Horloge
) -> None:
    autre = make_user(Role.ADMIN)
    c1, c2 = _client(admin, "203.0.113.5"), _client(autre, "203.0.113.5")
    with _taux(apercu="1/min"):
        assert _apercu(c1) != 429
        assert _apercu(c1) == 429
        assert _apercu(c2) != 429


@pytest.mark.django_db
def test_meme_utilisateur_changeant_d_adresse_reste_limite(admin: User, horloge: Horloge) -> None:
    with _taux(apercu="1/min"):
        assert _apercu(_client(admin, "203.0.113.5")) != 429
        assert _apercu(_client(admin, "203.0.113.6")) == 429


@pytest.mark.django_db
def test_portees_independantes(admin: User, horloge: Horloge) -> None:
    client = _client(admin)
    with _taux(apercu="1/min"):
        assert _apercu(client) != 429
        assert _apercu(client) == 429
        assert client.post(GENERER, {}, format="json").status_code != 429


@pytest.mark.django_db
def test_cache_en_panne_la_requete_passe_et_avertit(
    rai: User, horloge: Horloge, caplog: pytest.LogCaptureFixture
) -> None:
    class CachePanne:
        def get(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("redis injoignable")

        set = get

    client = _client(rai)
    with (
        patch.object(SimpleRateThrottle, "cache", CachePanne()),
        caplog.at_level(logging.WARNING, logger="apps.core.throttling"),
    ):
        reponse = client.post(GENERER, {}, format="json")
    assert reponse.status_code == 400  # ni 429 ni 500
    avertissements = [r for r in caplog.records if r.name == "apps.core.throttling"]
    assert avertissements
    assert "generation" in avertissements[0].getMessage()


@pytest.mark.django_db
def test_sante_jamais_limitee(horloge: Horloge) -> None:
    client = APIClient()
    with _taux(anonyme="1/min"):
        for _ in range(5):
            assert client.get("/api/v1/health/").status_code != 429


@pytest.mark.django_db
def test_portees_des_actions_couteuses() -> None:
    from apps.documents.views import DocumentViewSet, FormatNumerotationViewSet, GabaritViewSet
    from apps.programmation.views import ProgrammeAnnuelViewSet
    from apps.referentiel.views import CartographieVersionViewSet

    def portee(classe: Any, action: str) -> str | None:
        vue = classe()
        vue.action = action
        return vue.throttle_scope  # type: ignore[no-any-return]

    assert portee(GabaritViewSet, "create") == "televersement"
    assert portee(GabaritViewSet, "preview") == "apercu"
    assert portee(GabaritViewSet, "list") is None
    assert portee(FormatNumerotationViewSet, "preview") == "apercu"
    assert portee(DocumentViewSet, "generate") == "generation"
    assert portee(ProgrammeAnnuelViewSet, "export") == "export"
    assert portee(CartographieVersionViewSet, "export") == "export"

    from apps.users.account_views import UserAccountViewSet

    assert portee(UserAccountViewSet, "import_csv") == "import"
    assert portee(UserAccountViewSet, "import_directory") == "import"
    assert portee(UserAccountViewSet, "directory_search") == "annuaire"


def test_openapi_documente_429() -> None:
    from drf_spectacular.generators import SchemaGenerator

    schema = dict(SchemaGenerator().get_schema(request=None, public=True))  # type: ignore[no-untyped-call]
    chemins = schema["paths"]
    for chemin, methode in [
        ("/api/v1/documents/generate/", "post"),
        ("/api/v1/numbering-formats/preview/", "post"),
        ("/api/v1/templates/{id}/preview/", "get"),
        ("/api/v1/templates/", "post"),
        ("/api/v1/audit-plans/{id}/export/", "get"),
        ("/api/v1/risk-maps/{id}/export/", "get"),
        ("/api/v1/user-accounts/import-csv/", "post"),
        ("/api/v1/user-accounts/import-directory/", "post"),
        ("/api/v1/user-accounts/directory-search/", "get"),
    ]:
        assert "429" in chemins[chemin][methode]["responses"], chemin


def test_toute_portee_declaree_a_un_taux() -> None:
    from django.conf import settings

    from apps.core.throttling import ThrottleParActionMixin

    taux = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    import importlib

    for module in ("documents", "programmation", "referentiel", "users.account_views"):
        nom = module if "." in module else f"{module}.views"
        mod = importlib.import_module(f"apps.{nom}")
        for obj in vars(mod).values():
            if isinstance(obj, type) and issubclass(obj, ThrottleParActionMixin):
                for portee in obj.throttle_scopes.values():
                    assert portee in taux, (obj.__name__, portee)


def test_compose_prod_transmet_les_taux_et_isole_nginx() -> None:
    import ipaddress
    from pathlib import Path

    import yaml
    from django.conf import settings

    racine = Path(settings.BASE_DIR).parent
    compose = yaml.safe_load((racine / "docker" / "compose.prod.yml").read_text(encoding="utf-8"))
    env = compose["x-backend-env"]
    for portee in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]:
        assert f"THROTTLE_RATE_{portee.upper()}" in env, portee
    ipam = compose["networks"]["web"]["ipam"]["config"][0]
    assert "ip_range" in ipam
    plage = ipaddress.ip_network("172.30.10.8/29")
    assert ipaddress.ip_address("172.30.10.2") not in plage
    assert plage.subnet_of(ipaddress.ip_network("172.30.10.0/28"))
