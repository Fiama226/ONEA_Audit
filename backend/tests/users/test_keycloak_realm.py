import json
from pathlib import Path
from typing import Any

from django.conf import settings

ROOT = Path(__file__).resolve().parents[3]


def _realm() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (ROOT / "docker/keycloak/realm-onea.json").read_text(encoding="utf-8")
    )
    return data


def test_realm_client_de_service_minimal() -> None:
    realm = _realm()
    client = next(c for c in realm["clients"] if c["clientId"] == "onea-admin-sync")
    assert client["serviceAccountsEnabled"] and not client["publicClient"]
    assert not (
        client.get("standardFlowEnabled")
        or client.get("directAccessGrantsEnabled")
        or client.get("implicitFlowEnabled")
    )
    assert client["secret"] == "${KEYCLOAK_ADMIN_API_CLIENT_SECRET}"  # noqa: S105
    sa = next(u for u in realm["users"] if u.get("serviceAccountClientId") == "onea-admin-sync")
    assert sa["clientRoles"] == {"realm-management": ["view-users", "manage-users"]}
    assert not sa.get("realmRoles")
    # fullScopeAllowed is off (least privilege), so the roles must be explicitly in the
    # token scope, otherwise Keycloak answers 403 to every admin call.
    assert client["fullScopeAllowed"] is False
    assert realm["clientScopeMappings"]["realm-management"] == [
        {"client": "onea-admin-sync", "roles": ["view-users", "manage-users"]}
    ]
    assert realm["registrationAllowed"] is False and not realm.get("editUsernameAllowed")
    assert "onea-admin-sync" not in settings.OIDC_ALLOWED_AZP


def test_utilisateur_de_dev_preprov1() -> None:
    user = next(u for u in _realm()["users"] if u["username"] == "preprov1")
    assert user["realmRoles"] == ["AUDITE"]
    assert user["attributes"]["direction"] == ["DCM"]
    assert user["attributes"]["fonction"] == ["Chargé de clientèle"]
    assert user["credentials"][0]["value"] == "onea2026"
