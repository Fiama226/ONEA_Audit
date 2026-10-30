"""Keycloak admin API client: HTTP behaviour, error mapping, secret hygiene, settings."""

import base64
import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import requests
import yaml
from django.conf import settings
from pytest import MonkeyPatch
from rest_framework.test import APIClient

from apps.users import keycloak_admin
from apps.users.keycloak_admin import (
    HttpKeycloakAdmin,
    KeycloakAdminError,
    KeycloakIndisponible,
    KeycloakIntrouvable,
    KeycloakNonConfigure,
    KeycloakRefus,
    get_keycloak_admin,
)

ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
KC_ID = "11111111-2222-3333-4444-555555555555"
SECRET = "super-secret-value-xyz"  # noqa: S105
TOKEN_URL = settings.OIDC_OP_TOKEN_ENDPOINT
ADMIN = settings.OIDC_OP_BASE_URL.replace("/realms/", "/admin/realms/", 1)
USER_URL = f"{ADMIN}/users/{KC_ID}"


class Call:
    def __init__(self, method: str, url: str, kwargs: dict[str, Any]) -> None:
        self.method = method
        self.url = url
        self.kwargs = kwargs

    @property
    def json(self) -> Any:
        return self.kwargs.get("json")


class Route:
    def __init__(self) -> None:
        self.queue: list[tuple[int, Any, Exception | None]] = []
        self.calls: list[Call] = []

    @property
    def last_json(self) -> Any:
        return self.calls[-1].json


class HttpMock:
    """Replaces `requests.Session.request`; one FIFO of responses per (method, url)."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Route] = {}
        self.calls: list[Call] = []

    def add(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        status: int = 200,
        raises: Exception | None = None,
    ) -> Route:
        route = self.routes.setdefault((method, url), Route())
        route.queue.append((status, json, raises))
        return route

    def get(self, url: str, **kw: Any) -> Route:
        return self.add("GET", url, **kw)

    def put(self, url: str, **kw: Any) -> Route:
        return self.add("PUT", url, **kw)

    def post(self, url: str, **kw: Any) -> Route:
        return self.add("POST", url, **kw)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        call = Call(method, url, kwargs)
        self.calls.append(call)
        route = self.routes.get((method, url))
        assert route is not None, f"unexpected request {method} {url}"
        route.calls.append(call)
        status, body, raises = route.queue.pop(0) if len(route.queue) > 1 else route.queue[0]
        if raises is not None:
            raise raises
        resp = requests.Response()
        resp.status_code = status
        resp._content = json.dumps(body).encode() if body is not None else b""
        resp.url = url
        return resp

    def count(self, method: str, url: str) -> int:
        route = self.routes.get((method, url))
        return len(route.calls) if route else 0


@pytest.fixture
def http_mock(monkeypatch: MonkeyPatch, settings: Any) -> Iterator[HttpMock]:
    settings.KEYCLOAK_ADMIN_API_CLIENT_ID = "onea-admin-sync"
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = SECRET
    keycloak_admin._reset_token_cache()
    mock = HttpMock()

    def fake_request(self: requests.Session, method: str, url: str, **kw: Any) -> requests.Response:
        return mock.request(method, url, **kw)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    mock.post(TOKEN_URL, json={"access_token": "tok-1", "expires_in": 300})
    yield mock
    keycloak_admin._reset_token_cache()


def test_set_enabled_relit_puis_ecrit_la_representation_complete(http_mock: HttpMock) -> None:
    rep = {
        "id": KC_ID,
        "username": "auditeur2",
        "enabled": True,
        "attributes": {"direction": ["DAI"]},
    }
    http_mock.get(USER_URL, json=rep)
    put = http_mock.put(USER_URL, status=204)
    HttpKeycloakAdmin().set_enabled(UUID(KC_ID), False)
    assert put.last_json == {**rep, "enabled": False}
    assert [c.method for c in http_mock.calls] == ["POST", "GET", "PUT"]
    assert http_mock.calls[1].kwargs["headers"]["Authorization"] == "Bearer tok-1"


def test_jeton_mis_en_cache_et_renouvele_sur_401(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    client = HttpKeycloakAdmin()
    client.get_user(UUID(KC_ID))
    client.get_user(UUID(KC_ID))
    assert http_mock.count("POST", TOKEN_URL) == 1  # cached across calls...
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert http_mock.count("POST", TOKEN_URL) == 1  # ...and across instances

    # token rejected once by the server -> renewed -> request retried
    http_mock.routes[("GET", USER_URL)].queue[:] = [(401, None, None), (200, {"id": KC_ID}, None)]
    http_mock.routes[("POST", TOKEN_URL)].queue[:] = [
        (200, {"access_token": "tok-2", "expires_in": 300}, None)
    ]
    assert client.get_user(UUID(KC_ID)) == {"id": KC_ID}
    assert http_mock.count("POST", TOKEN_URL) == 2
    last = http_mock.routes[("GET", USER_URL)].calls[-1]
    assert last.kwargs["headers"]["Authorization"] == "Bearer tok-2"


def test_jeton_expire_est_renouvele(http_mock: HttpMock, monkeypatch: MonkeyPatch) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    now = [1000.0]
    monkeypatch.setattr("apps.users.keycloak_admin.time.monotonic", lambda: now[0])
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    now[0] += 290  # inside the 30 s safety margin of a 300 s token
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert http_mock.count("POST", TOKEN_URL) == 2


@pytest.mark.parametrize(
    "outcome",
    [
        {"raises": requests.Timeout("slow")},
        {"raises": requests.ConnectionError("down")},
    ],
)
def test_timeout_et_5xx_donnent_keycloak_indisponible(
    http_mock: HttpMock, outcome: dict[str, Any]
) -> None:
    http_mock.get(USER_URL, **outcome)
    with pytest.raises(KeycloakIndisponible) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == "Keycloak injoignable."
    assert exc.value.status is None


@pytest.mark.parametrize("status", [500, 502, 503])
def test_5xx_donne_indisponible_avec_le_code(http_mock: HttpMock, status: int) -> None:
    http_mock.get(USER_URL, status=status)
    with pytest.raises(KeycloakIndisponible) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == f"Keycloak a répondu HTTP {status}."
    assert exc.value.status == status


def test_404_donne_introuvable(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, status=404)
    with pytest.raises(KeycloakIntrouvable) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == "Compte introuvable dans Keycloak."
    assert exc.value.status == 404


def test_403_donne_refus(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, status=403)
    with pytest.raises(KeycloakRefus) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == (
        "Keycloak a refusé l'opération (HTTP 403) : vérifiez les droits du client de service."
    )
    assert exc.value.status == 403


def test_401_persistant_donne_refus_apres_un_seul_renouvellement(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, status=401)
    with pytest.raises(KeycloakRefus):
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert http_mock.count("GET", USER_URL) == 2
    assert http_mock.count("POST", TOKEN_URL) == 2


def test_secret_refuse_par_le_endpoint_de_jeton_donne_refus(http_mock: HttpMock) -> None:
    http_mock.routes[("POST", TOKEN_URL)].queue[:] = [(401, None, None)]
    with pytest.raises(KeycloakRefus):
        HttpKeycloakAdmin().get_user(UUID(KC_ID))


def test_secret_vide_non_configure(http_mock: HttpMock, settings: Any) -> None:
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = ""
    with pytest.raises(KeycloakNonConfigure) as exc:
        get_keycloak_admin()
    assert exc.value.message == "Synchronisation Keycloak non configurée."
    assert http_mock.calls == []


def test_get_keycloak_admin_retourne_le_client_http(http_mock: HttpMock) -> None:
    assert isinstance(get_keycloak_admin(), HttpKeycloakAdmin)


def test_erreurs_sans_secret(http_mock: HttpMock, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    http_mock.get(USER_URL, raises=requests.ConnectionError(f"boom {SECRET} tok-1"))
    http_mock.post(f"{USER_URL}/logout", status=403)
    client = HttpKeycloakAdmin()
    with pytest.raises(KeycloakAdminError) as exc1:
        client.get_user(UUID(KC_ID))
    with pytest.raises(KeycloakAdminError) as exc2:
        client.logout(UUID(KC_ID))
    for exc in (exc1.value, exc2.value):
        assert SECRET not in str(exc)
        assert "tok-1" not in str(exc)
        assert exc.__cause__ is None
    assert SECRET not in caplog.text
    assert "tok-1" not in caplog.text


def test_logout_appelle_la_route(http_mock: HttpMock) -> None:
    route = http_mock.post(f"{USER_URL}/logout", status=204)
    HttpKeycloakAdmin().logout(UUID(KC_ID))
    assert len(route.calls) == 1


def test_search_users(http_mock: HttpMock) -> None:
    route = http_mock.get(f"{ADMIN}/users", json=[{"username": "auditeur1"}])
    assert HttpKeycloakAdmin().search_users("audit", max_results=5) == [{"username": "auditeur1"}]
    assert route.calls[0].kwargs["params"] == {"search": "audit", "max": 5}


def test_iter_users_pagine(http_mock: HttpMock) -> None:
    url = f"{ADMIN}/users"
    pages = [
        [{"id": str(i)} for i in range(100)],
        [{"id": str(i)} for i in range(100, 200)],
        [{"id": "200"}],
    ]
    route = Route()
    route.queue = [(200, p, None) for p in pages]
    http_mock.routes[("GET", url)] = route
    users = list(HttpKeycloakAdmin().iter_users())
    assert len(users) == 201
    assert [c.kwargs["params"]["first"] for c in route.calls] == [0, 100, 200]
    assert all(c.kwargs["params"]["max"] == 100 for c in route.calls)


def test_effective_realm_roles(http_mock: HttpMock) -> None:
    http_mock.get(
        f"{USER_URL}/role-mappings/realm/composite",
        json=[{"name": "AUDITEUR"}, {"name": "default-roles-onea"}],
    )
    assert HttpKeycloakAdmin().effective_realm_roles(UUID(KC_ID)) == {
        "AUDITEUR",
        "default-roles-onea",
    }


def test_requetes_avec_delai_et_verification_tls(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    for call in http_mock.calls:
        assert call.kwargs["timeout"] == settings.OIDC_TIMEOUT
        assert call.kwargs["verify"] == settings.OIDC_VERIFY_SSL
    assert http_mock.calls[0].kwargs["data"] == {
        "grant_type": "client_credentials",
        "client_id": "onea-admin-sync",
        "client_secret": SECRET,
    }


def _jwt(**payload: Any) -> str:
    def enc(obj: Any) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return f"{enc({'alg': 'RS256'})}.{enc(payload)}.sig"


@pytest.mark.django_db
def test_jeton_du_client_de_service_refuse(api_client: APIClient) -> None:
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_jwt(azp='onea-admin-sync')}")
    assert api_client.get("/api/v1/me/").status_code == 401


def _load_prod(overrides: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "x" * 64,
        "DATABASE_URL": "postgres://u:p@db:5432/onea",
        "EMAIL_URL": "smtp://user:pw@smtp.onea.bf:587",
        "ALLOWED_HOSTS": "audit.onea.bf",
        "CORS_ALLOWED_ORIGINS": "https://audit.onea.bf",
        "CSRF_TRUSTED_ORIGINS": "https://audit.onea.bf",
        "OIDC_OP_BASE_URL": "https://sso.onea.bf/realms/onea",
        # Required in production since lot 4 (document storage).
        "DOCUMENTS_ROOT": "/var/lib/onea/documents",
        # Required in production since lot 8 (links in reminder e-mails).
        "PLATEFORME_URL": "https://audit.onea.bf",
    }
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_prod_exige_le_secret() -> None:
    missing = _load_prod({"KEYCLOAK_ADMIN_API_CLIENT_SECRET": None})
    assert missing.returncode != 0
    assert "ImproperlyConfigured" in missing.stderr
    assert "KEYCLOAK_ADMIN_API_CLIENT_SECRET" in missing.stderr
    assert _load_prod({"KEYCLOAK_ADMIN_API_CLIENT_SECRET": ""}).returncode != 0
    ok = _load_prod({"KEYCLOAK_ADMIN_API_CLIENT_SECRET": "s3cret-prod"})
    assert ok.returncode == 0, ok.stderr


@pytest.mark.parametrize("secret", ["CHANGE_ME_keycloak_admin_sync_secret", "onea-dev-sync-secret"])
def test_prod_refuse_les_secrets_d_exemple(secret: str) -> None:
    result = _load_prod({"KEYCLOAK_ADMIN_API_CLIENT_SECRET": secret})
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr


def test_aucune_redirection_suivie(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert len(http_mock.calls) == 2
    assert all(c.kwargs["allow_redirects"] is False for c in http_mock.calls)


def test_redirection_sur_appel_admin_donne_indisponible(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, status=307)
    with pytest.raises(KeycloakIndisponible) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == "Keycloak a répondu HTTP 307."


def test_redirection_sur_le_jeton_donne_indisponible(http_mock: HttpMock) -> None:
    http_mock.routes[("POST", TOKEN_URL)].queue[:] = [(308, None, None)]
    with pytest.raises(KeycloakIndisponible) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.status == 308


def test_jeton_404_n_est_pas_injoignable(http_mock: HttpMock) -> None:
    http_mock.routes[("POST", TOKEN_URL)].queue[:] = [(404, None, None)]
    with pytest.raises(KeycloakAdminError) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert not isinstance(exc.value, KeycloakIndisponible)
    assert exc.value.status == 404
    assert "404" in exc.value.message


def test_jeton_5xx_donne_indisponible(http_mock: HttpMock) -> None:
    http_mock.routes[("POST", TOKEN_URL)].queue[:] = [(503, None, None)]
    with pytest.raises(KeycloakIndisponible) as exc:
        HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert exc.value.message == "Keycloak a répondu HTTP 503."


@pytest.mark.parametrize("bad", ["auditeur1", "../../master/users", "", None])
def test_identifiant_non_uuid_refuse_avant_toute_requete(http_mock: HttpMock, bad: Any) -> None:
    client = HttpKeycloakAdmin()
    with pytest.raises(ValueError):  # noqa: PT011
        client.get_user(bad)
    with pytest.raises(ValueError):  # noqa: PT011
        client.set_enabled(bad, False)
    with pytest.raises(ValueError):  # noqa: PT011
        client.logout(bad)
    with pytest.raises(ValueError):  # noqa: PT011
        client.effective_realm_roles(bad)
    assert http_mock.calls == []


def test_identifiant_uuid_en_chaine_accepte(http_mock: HttpMock) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    assert HttpKeycloakAdmin().get_user(KC_ID)["id"] == KC_ID  # type: ignore[arg-type]


def test_cache_de_jeton_lie_au_client(http_mock: HttpMock, settings: Any) -> None:
    http_mock.get(USER_URL, json={"id": KC_ID})
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    settings.KEYCLOAK_ADMIN_API_CLIENT_ID = "autre-client"
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert http_mock.count("POST", TOKEN_URL) == 2
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = "autre-secret"  # noqa: S105
    HttpKeycloakAdmin().get_user(UUID(KC_ID))
    assert http_mock.count("POST", TOKEN_URL) == 3


def test_session_http_partagee() -> None:
    assert HttpKeycloakAdmin()._session is HttpKeycloakAdmin()._session


def test_iter_users_plafonne(http_mock: HttpMock, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(keycloak_admin, "_MAX_PAGES", 3)
    route = http_mock.get(f"{ADMIN}/users", json=[{"id": "a"}, {"id": "b"}])  # never ends
    with pytest.raises(KeycloakAdminError):
        list(HttpKeycloakAdmin().iter_users(page_size=2))
    assert len(route.calls) == 3


def test_deploy_doc_decrit_le_client_de_service() -> None:
    text = (ROOT / "docs/deploy.md").read_text(encoding="utf-8")
    for needle in (
        "onea-admin-sync",
        "view-users",
        "manage-users",
        "KEYCLOAK_ADMIN_API_CLIENT_SECRET",
    ):
        assert needle in text


def test_env_example_secret_marque_dev_only() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("KEYCLOAK_ADMIN_API_CLIENT_SECRET"))
    assert "DEV-ONLY" in lines[idx - 1]


def test_fake_keycloak_fidelite(fake_keycloak: Any) -> None:
    uid = fake_keycloak.add_user(
        "jdoe", email="jean.dupont@onea.test", firstName="Jean", lastName="Dupont"
    )
    for i in range(5):
        fake_keycloak.add_user(f"extra{i}")
    for q in ("JDOE", "dupont@onea", "jean", "DUPONT"):
        assert [u["id"] for u in fake_keycloak.search_users(q)] == [str(uid)]
    found = fake_keycloak.search_users("jdoe")[0]
    found["enabled"] = False
    assert fake_keycloak.enabled(uid)  # a copy, not the live dict
    assert len(fake_keycloak.search_users("e", max_results=2)) == 2
    assert fake_keycloak.calls[-1] == ("search_users", "e", 2)
    assert len(list(fake_keycloak.iter_users(page_size=4))) == 6
    assert fake_keycloak.calls[-1] == ("iter_users", 4)
    with pytest.raises(ValueError):  # noqa: PT011
        list(fake_keycloak.iter_users(page_size=0))
    err = KeycloakIndisponible("Keycloak injoignable.")
    fake_keycloak.fail_with(err, times=2)
    raised = []
    for _ in range(2):
        with pytest.raises(KeycloakIndisponible) as exc:
            fake_keycloak.get_user(uid)
        raised.append(exc.value)
    assert raised[0] is not raised[1]
    assert raised[0].message == raised[1].message


def test_fixture_fake_keycloak(fake_keycloak: Any) -> None:
    uid = fake_keycloak.add_user("auditeur9", roles={"AUDITEUR"})
    seen: list[bool] = []
    fake_keycloak.on_set_enabled(lambda _id, enabled: seen.append(enabled))
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."))
    admin = keycloak_admin.get_keycloak_admin()  # consumers must go through the module
    with pytest.raises(KeycloakIndisponible):
        admin.set_enabled(uid, False)
    admin.set_enabled(uid, False)
    assert not fake_keycloak.enabled(uid) and seen == [False]
    assert admin.effective_realm_roles(uid) == {"AUDITEUR"}
    assert [u["username"] for u in admin.search_users("audit")] == ["auditeur9"]
    with pytest.raises(KeycloakIntrouvable):
        admin.get_user(UUID(KC_ID))


def test_compose_dev_transmet_le_secret() -> None:
    compose = yaml.safe_load((ROOT / "docker/compose.dev.yml").read_text(encoding="utf-8"))
    assert "KEYCLOAK_ADMIN_API_CLIENT_SECRET" in compose["services"]["keycloak"]["environment"]


def test_compose_prod_transmet_le_secret() -> None:
    text = (ROOT / "docker/compose.prod.yml").read_text(encoding="utf-8")
    assert "KEYCLOAK_ADMIN_API_CLIENT_SECRET: ${KEYCLOAK_ADMIN_API_CLIENT_SECRET:?" in text
