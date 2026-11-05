from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.users.models import Role, User

from ..connexion import connecter
from ..factories import DirectionFactory, make_user

BASE = "/api/v1/user-accounts/"


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
        ("post", BASE, {"username": "nouvel.agent", "role": "AUDITEUR"}, "json"),
        ("post", f"{BASE}{cible}/reset-password/", {}, "json"),
        ("post", f"{BASE}{cible}/disable-otp/", {}, "json"),
        ("post", f"{BASE}{cible}/change-role/", {"role": "RAI"}, "json"),
        ("get", f"{BASE}{cible}/delegation/", {}, "json"),
        ("put", f"{BASE}{cible}/delegation/", {}, "json"),
        ("post", BASE + "import-csv/", {}, "multipart"),
        ("options", BASE, {}, "json"),
        ("options", f"{BASE}{cible}/", {}, "json"),
    ]


@pytest.mark.parametrize("role", ROLES_REFUSES)
def test_droits_admin_seul_toutes_les_routes(api_client: APIClient, user: User, role: str) -> None:
    cible = make_user(Role.AUDITEUR)
    fonction_initiale = cible.fonction
    api_client.force_authenticate(make_user(role))
    for methode, url, corps, fmt in _routes(cible.id):
        r = _appel(api_client, methode, url, corps, fmt)
        assert r.status_code == 403, (methode, url)
        assert set(r.json()) == {"detail", "errors"}, (methode, url)
    cible.refresh_from_db()
    assert cible.is_active and cible.fonction == fonction_initiale


def test_admin_acces_aux_routes(api_client: APIClient, admin: User) -> None:
    cible = make_user(Role.AUDITEUR)
    api_client.force_authenticate(admin)
    assert api_client.get(BASE).status_code == 200
    r = api_client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "x"}, format="json")
    assert r.status_code == 200


def test_anonyme_401_sur_toutes_les_routes(api_client: APIClient, user: User) -> None:
    for methode, url, corps, fmt in _routes(user.id):
        r = _appel(api_client, methode, url, corps, fmt)
        assert r.status_code == 401, (methode, url)
        assert set(r.json()) == {"detail", "errors"}, (methode, url)


# Regression guard: the routes of the former identity provider (Keycloak) stay removed.
@pytest.mark.parametrize(
    "methode,suffixe",
    [
        ("post", "{id}/resync-profile/"),
        ("post", "{id}/retry-keycloak-sync/"),
        ("get", "directory-search/?q=aud"),
        ("post", "import-directory/"),
    ],
)
def test_routes_de_l_ancien_annuaire_supprimees(
    api_client: APIClient, admin: User, methode: str, suffixe: str
) -> None:
    cible = make_user(Role.AUDITEUR)
    api_client.force_authenticate(admin)
    r = getattr(api_client, methode)(BASE + suffixe.format(id=cible.id))
    assert r.status_code in (404, 405)


def test_reactivate(api_client: APIClient, admin: User) -> None:
    cible = make_user(Role.AUDITEUR, is_active=False)
    api_client.force_authenticate(admin)
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
        ("origine", MSG_AUTRE),
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
    assert r.json()["matricule"] == "M1"
    bad = api_client.patch(f"{BASE}{cible.id}/", {"direction_code": "ZZZ"}, format="json")
    assert bad.status_code == 422


def test_direction_inconnue_inchangee_acceptee(api_client: APIClient, admin: User) -> None:
    cible = make_user(Role.AUDITEUR, direction_code="ANCIENNE")
    api_client.force_authenticate(admin)
    r = api_client.patch(
        f"{BASE}{cible.id}/", {"direction_code": "ANCIENNE", "fonction": "X"}, format="json"
    )
    assert r.status_code == 200 and r.json()["direction_libelle"] is None


def test_desactivation_effective_au_prochain_appel(api_client: APIClient, admin: User) -> None:
    cible = make_user(Role.RAI)
    session_cible = connecter(APIClient(), cible)
    assert session_cible.get("/api/v1/me/").status_code == 200
    connecter(api_client, admin)
    r = api_client.post(f"{BASE}{cible.id}/deactivate/", {"motif": "Départ"}, format="json")
    assert r.status_code == 200
    r = session_cible.get("/api/v1/me/")
    assert r.status_code == 401 and set(r.json()) == {"detail", "errors"}
    assert api_client.post(f"{BASE}{cible.id}/reactivate/").status_code == 200
    # The session ended with the deactivation: a reactivation does not revive it.
    assert session_cible.get("/api/v1/me/").status_code == 401
    assert connecter(APIClient(), cible).get("/api/v1/me/").status_code == 200


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

    assert ids("?en_attente_connexion=true&origine=CSV") == [a.id]
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
        "reinitialiser_mot_de_passe": False,
        "desactiver_otp": False,
    }
    # Regression guard: the fields of the former identity provider (Keycloak) stay removed.
    retires = {
        "keycloak_lie",
        "keycloak_sync",
        "keycloak_sync_statut",
        "role_provisoire",
        "profil_gere_localement",
    }
    assert not retires & set(r)


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
