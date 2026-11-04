import uuid
from typing import Any
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.users.keycloak_admin import (
    KeycloakAdminError,
    KeycloakIndisponible,
    KeycloakIntrouvable,
    KeycloakRefus,
)
from apps.users.models import Role, User
from apps.users.oidc import OneaOIDCBackend

from ..conftest import FakeKeycloakAdmin
from ..factories import DirectionFactory, make_user
from .test_oidc import _bearer, claims

BASE = "/api/v1/user-accounts/"
ANNUAIRE_503 = "L'annuaire (Keycloak) est momentanément indisponible. Réessayez plus tard."


ROLES_REFUSES = ["RAI", "AUDITEUR", "AUDITE", "DG"]


def _appel(client: APIClient, methode: str, url: str, corps: dict[str, Any], fmt: str) -> Any:
    if methode in ("get", "options"):
        return getattr(client, methode)(url)
    return getattr(client, methode)(url, corps, format=fmt)


def _routes(cible: int) -> list[tuple[str, str, dict[str, Any], str]]:
    return [
        ("get", BASE, {}, "json"),
        ("get", f"{BASE}{cible}/", {}, "json"),
        ("patch", f"{BASE}{cible}/", {"fonction": "X"}, "json"),
        ("post", f"{BASE}{cible}/deactivate/", {"motif": "x"}, "json"),
        ("post", f"{BASE}{cible}/reactivate/", {}, "json"),
        ("post", f"{BASE}{cible}/resync-profile/", {}, "json"),
        ("post", f"{BASE}{cible}/retry-keycloak-sync/", {}, "json"),
        ("post", BASE, {"username": "nouvel.agent", "role": "AUDITEUR"}, "json"),
        ("post", f"{BASE}{cible}/reset-password/", {}, "json"),
        ("post", f"{BASE}{cible}/disable-otp/", {}, "json"),
        ("post", f"{BASE}{cible}/change-role/", {"role": "RAI"}, "json"),
        ("get", f"{BASE}{cible}/delegation/", {}, "json"),
        ("put", f"{BASE}{cible}/delegation/", {}, "json"),
        ("get", BASE + "directory-search/?q=aud", {}, "json"),
        ("post", BASE + "import-directory/", {"keycloak_ids": [str(uuid.uuid4())]}, "json"),
        ("post", BASE + "import-csv/", {}, "multipart"),
        ("options", BASE, {}, "json"),
        ("options", f"{BASE}{cible}/", {}, "json"),
    ]


@pytest.mark.parametrize("role", ROLES_REFUSES)
def test_droits_admin_seul_toutes_les_routes(
    api_client: APIClient, user: User, role: str, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = make_user(Role.AUDITEUR)
    fonction_initiale = cible.fonction
    api_client.force_authenticate(make_user(role))
    for methode, url, corps, fmt in _routes(cible.id):
        r = _appel(api_client, methode, url, corps, fmt)
        assert r.status_code == 403, (methode, url)
        assert set(r.json()) == {"detail", "errors"}, (methode, url)
    cible.refresh_from_db()
    assert cible.is_active and cible.fonction == fonction_initiale


def test_admin_acces_aux_routes(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = make_user(Role.AUDITEUR)
    api_client.force_authenticate(admin)
    assert api_client.get(BASE).status_code == 200
    assert api_client.get(BASE + "directory-search/?q=aud").status_code == 200
    r = api_client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "x"}, format="json")
    assert r.status_code == 200


def test_anonyme_401_sur_toutes_les_routes(api_client: APIClient, user: User) -> None:
    for methode, url, corps, fmt in _routes(user.id):
        r = _appel(api_client, methode, url, corps, fmt)
        assert r.status_code == 401, (methode, url)
        assert set(r.json()) == {"detail", "errors"}, (methode, url)


def test_deactivate_keycloak_echec_200(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin, settings: Any
) -> None:
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = "s3cr3t-de-test"  # noqa: S105
    cible = make_user(Role.AUDITEUR, keycloak_id=fake_keycloak.add_user("auditeur2"))
    fake_keycloak.fail_with(
        KeycloakRefus(
            "Keycloak a refusé l'opération (HTTP 403) : vérifiez les droits du client de service.",
            403,
        )
    )
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "Départ"}, format="json")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert r.json()["keycloak_sync"]["statut"] == "ECHEC"
    assert r.json()["keycloak_sync"]["manuel"] is True
    assert r.json()["actions"]["relancer_synchro_keycloak"]
    assert settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET not in r.content.decode()


def test_reactivate_et_resync_profile(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = make_user(Role.AUDITEUR, is_active=False, profil_gere_localement=True)
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{cible.id}/resync-profile/")
    assert r.status_code == 200 and r.json()["profil_gere_localement"] is False
    assert api_client.post(f"{BASE}{cible.id}/resync-profile/").status_code == 422
    r = api_client.post(f"{BASE}{cible.id}/reactivate/")
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert api_client.post(f"{BASE}{cible.id}/reactivate/").status_code == 422


MSG_ROLE = "Utilisez l'action « Changer le rôle »."
MSG_IDENTIFIANT = "L'identifiant ne peut pas être modifié."
MSG_ACTIF = "Utilisez les actions « Désactiver » et « Réactiver »."
MSG_AUTRE = "Champ non modifiable."


@pytest.mark.parametrize(
    "champ,message",
    [
        ("role", MSG_ROLE),
        ("username", MSG_IDENTIFIANT),
        ("is_active", MSG_ACTIF),
        ("id", MSG_AUTRE),
        ("keycloak_id", MSG_AUTRE),
    ],
)
def test_patch_champs_refuses(api_client: APIClient, admin: User, champ: str, message: str) -> None:
    cible = make_user(Role.AUDITEUR)
    avant = User.objects.values().get(pk=cible.pk)
    api_client.force_authenticate(admin)
    r = api_client.patch(f"{BASE}{cible.id}/", {champ: "x", "fonction": "Chef"}, format="json")
    assert r.status_code == 400 and r.json()["errors"] == {champ: [message]}
    assert User.objects.values().get(pk=cible.pk) == avant


def test_patch_profil(api_client: APIClient, admin: User) -> None:
    DirectionFactory(code="DIRX", libelle="Direction audit")
    cible = make_user(Role.AUDITEUR)
    api_client.force_authenticate(admin)
    r = api_client.patch(
        f"{BASE}{cible.id}/", {"direction_code": "DIRX", "matricule": "M1"}, format="json"
    )
    assert r.status_code == 200
    assert r.json()["direction_libelle"] == "Direction audit"
    assert r.json()["profil_gere_localement"] is True
    bad = api_client.patch(f"{BASE}{cible.id}/", {"direction_code": "ZZZ"}, format="json")
    assert bad.status_code == 422


def test_direction_inconnue_inchangee_acceptee(api_client: APIClient, admin: User) -> None:
    cible = make_user(Role.AUDITEUR, direction_code="ANCIENNE")
    api_client.force_authenticate(admin)
    r = api_client.patch(
        f"{BASE}{cible.id}/", {"direction_code": "ANCIENNE", "fonction": "X"}, format="json"
    )
    assert r.status_code == 200 and r.json()["direction_libelle"] is None


def test_desactivation_effective_au_prochain_appel(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    sub = uuid.uuid4()
    cible = make_user(Role.RAI, keycloak_id=sub)
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "Départ"}, format="json")
    assert r.status_code == 200
    api_client.force_authenticate(None)
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(sub=str(sub))):
        r = _bearer(api_client).get("/api/v1/me/")
        assert r.status_code == 403
        assert r.json() == {"detail": "Compte désactivé.", "errors": {}}
    api_client.force_authenticate(admin)
    assert api_client.post(f"{BASE}{cible.id}/reactivate/").status_code == 200
    api_client.force_authenticate(None)
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=claims(sub=str(sub))):
        assert _bearer(api_client).get("/api/v1/me/").status_code == 200


def test_desactiver_soi_meme_422(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{admin.id}/deactivate/", {"motif": "x"}, format="json")
    assert r.status_code == 422


@pytest.mark.parametrize("corps", [{}, {"motif": ""}, {"motif": "   "}])
def test_motif_vide_400(
    api_client: APIClient, admin: User, user: User, corps: dict[str, str]
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{user.id}/deactivate/", corps, format="json")
    assert r.status_code == 400 and r.json()["errors"]["motif"] == ["Le motif est obligatoire."]


def test_filtres_et_tri(api_client: APIClient, admin: User) -> None:
    a = make_user(
        Role.AUDITEUR,
        username="zed",
        last_name="Zongo",
        origine="CSV",
        keycloak_sync_statut="ECHEC",
        matricule="M-9",
        email="zed@onea.bf",
        first_name="Zoe",
        direction_code="DIRQ",
    )
    b = make_user(
        Role.RAI, username="amy", last_name="Alpha", premiere_connexion_le="2026-01-01T00:00:00Z"
    )
    api_client.force_authenticate(admin)

    def ids(qs: str) -> list[int]:
        return [x["id"] for x in api_client.get(BASE + qs).json()["results"]]

    assert ids("?en_attente_connexion=true&origine=CSV&keycloak_sync=ECHEC") == [a.id]
    assert ids("?role=RAI") == [b.id]
    for terme in ("zon", "ZED", "m-9", "zed@onea", "Zo"):
        assert ids(f"?q={terme}") == [a.id], terme
    assert ids("?direction_code=DIRQ") == [a.id]
    assert ids("?en_attente_connexion=false") == [b.id]
    assert ids("?is_active=false") == []
    for champ in ("username", "last_name"):
        croissant = ids(f"?ordering={champ}")
        assert croissant.index(b.id) < croissant.index(a.id), champ
        decroissant = ids(f"?ordering=-{champ}")
        assert decroissant.index(a.id) < decroissant.index(b.id), champ
    assert api_client.get(BASE + "?q=" + "x" * 101).status_code == 400


@pytest.mark.parametrize("qs", ["?is_active=peut-etre", "?en_attente_connexion=x", "?role=NOPE"])
def test_filtre_invalide_400(api_client: APIClient, admin: User, qs: str) -> None:
    api_client.force_authenticate(admin)
    assert api_client.get(BASE + qs).status_code == 400


def test_actions_dans_le_detail(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    r = api_client.get(f"{BASE}{admin.id}/").json()
    assert r["actions"] == {
        "modifier_profil": True,
        "modifier_courriel": True,
        "modifier_direction": True,
        "changer_role": False,
        "desactiver": False,
        "reactiver": False,
        "resynchroniser_profil": False,
        "relancer_synchro_keycloak": False,
        "reinitialiser_mot_de_passe": False,
        "desactiver_otp": False,
    }
    assert r["keycloak_lie"] is False


def test_id_inconnu_404_et_non_numerique_404(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    assert api_client.get(f"{BASE}999999/").status_code == 404
    assert api_client.get(f"{BASE}abc/").status_code == 404


def test_creation_vide_400_et_suppression_405(
    api_client: APIClient, admin: User, user: User
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.post(BASE, {}, format="json")
    assert r.status_code == 400
    assert {"username", "role"} <= set(r.json()["errors"])
    assert api_client.delete(f"{BASE}{user.id}/").status_code == 405
    assert api_client.put(f"{BASE}{user.id}/", {}, format="json").status_code == 405


def test_liste_requetes_bornees(api_client: APIClient, admin: User) -> None:
    DirectionFactory(code="DAI")
    for i in range(30):
        make_user(Role.AUDITEUR, direction_code="DAI", username=f"u{i}")
    api_client.force_authenticate(admin)
    with CaptureQueriesContext(connection) as liste:
        assert api_client.get(BASE + "?page_size=50").status_code == 200
    assert len(liste) <= 4
    with CaptureQueriesContext(connection) as detail:
        assert api_client.get(f"{BASE}{admin.id}/").status_code == 200
    assert len(detail) <= 6


def test_page_size_plafonne_a_200(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    r = api_client.get(BASE + "?page_size=1000")
    assert r.status_code == 200 and len(r.json()["results"]) <= 200


def test_retry_keycloak_sync(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = make_user(
        Role.AUDITEUR,
        keycloak_id=fake_keycloak.add_user("x"),
        keycloak_sync_statut="ECHEC",
        keycloak_sync_manuel=True,
    )
    api_client.force_authenticate(admin)
    r = api_client.post(f"{BASE}{cible.id}/retry-keycloak-sync/")
    assert r.status_code == 200 and r.json()["keycloak_sync"]["statut"] == "A_JOUR"
    assert r.json()["keycloak_sync"]["manuel"] is False
    r = api_client.post(f"{BASE}{cible.id}/retry-keycloak-sync/")
    assert r.status_code == 422 and "déjà synchronisé" in r.json()["detail"]


@pytest.mark.parametrize("q", ["", "a", "x" * 101])
def test_directory_search_q_invalide_400(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin, q: str
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.get(BASE + "directory-search/", {"q": q})
    assert r.status_code == 400 and "q" in r.json()["errors"]


def test_directory_search(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.add_user("auditeur9", email="a9@onea.bf", firstName="A", lastName="Neuf")
    api_client.force_authenticate(admin)
    r = api_client.get(BASE + "directory-search/?q=auditeur")
    assert r.status_code == 200 and r.json()[0]["username"] == "auditeur9"


def test_directory_search_503(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.fail_with(KeycloakIndisponible("down", 503))
    api_client.force_authenticate(admin)
    r = api_client.get(BASE + "directory-search/?q=aud")
    assert r.status_code == 503
    assert r.json() == {
        "detail": "L'annuaire (Keycloak) est momentanément indisponible. Réessayez plus tard.",
        "errors": {},
    }


def test_import_directory_plus_de_50_400(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    ids = [str(uuid.uuid4()) for _ in range(51)]
    assert (
        api_client.post(
            BASE + "import-directory/", {"keycloak_ids": ids}, format="json"
        ).status_code
        == 400
    )
    assert (
        api_client.post(BASE + "import-directory/", {"keycloak_ids": []}, format="json").status_code
        == 400
    )


def test_import_directory_rapport(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    kid = fake_keycloak.add_user(
        "nouveau", email="n@onea.bf", firstName="N", lastName="O", roles={"AUDITEUR"}
    )
    api_client.force_authenticate(admin)
    r = api_client.post(BASE + "import-directory/", {"keycloak_ids": [str(kid)]}, format="json")
    assert r.status_code == 200
    assert r.json() == {
        "dry_run": False,
        "crees": ["nouveau"],
        "mis_a_jour": [],
        "ignores": [],
        "fichier_mots_de_passe_id": None,
    }
    assert User.objects.get(username="nouveau").origine == "ANNUAIRE"


def test_import_directory_503(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    fake_keycloak.fail_with(KeycloakIndisponible("down", 503), times=5)
    api_client.force_authenticate(admin)
    r = api_client.post(
        BASE + "import-directory/", {"keycloak_ids": [str(uuid.uuid4())]}, format="json"
    )
    assert r.status_code == 503


@pytest.mark.parametrize(
    "exc,statut,detail",
    [
        (KeycloakIndisponible("down", 503), 503, ANNUAIRE_503),
        (
            KeycloakRefus("Keycloak a refusé l'opération (HTTP 403) : vérifiez les droits.", 403),
            502,
            "Keycloak a refusé l'opération (HTTP 403) : vérifiez les droits.",
        ),
        (
            KeycloakIntrouvable("Compte introuvable dans Keycloak.", 404),
            502,
            "Compte introuvable dans Keycloak.",
        ),
        (KeycloakAdminError("Erreur Keycloak."), 502, "Erreur Keycloak."),
    ],
)
def test_annuaire_erreurs_formatees(
    api_client: APIClient,
    admin: User,
    fake_keycloak: FakeKeycloakAdmin,
    settings: Any,
    exc: KeycloakAdminError,
    statut: int,
    detail: str,
) -> None:
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = "s3cr3t-de-test"  # noqa: S105
    api_client.force_authenticate(admin)
    fake_keycloak.fail_with(exc)
    r = api_client.get(BASE + "directory-search/?q=aud")
    assert r.status_code == statut and r.json() == {"detail": detail, "errors": {}}
    if isinstance(exc, KeycloakIntrouvable):
        return  # an import reports a missing directory entry as an ignored line (T4)
    fake_keycloak.fail_with(exc, times=5)
    r = api_client.post(
        BASE + "import-directory/", {"keycloak_ids": [str(uuid.uuid4())]}, format="json"
    )
    assert r.status_code == statut and r.json() == {"detail": detail, "errors": {}}
    assert "s3cr3t" not in r.content.decode()
