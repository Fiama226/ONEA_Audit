import pytest
from rest_framework.test import APIClient

from apps.users.models import Role, User
from tests.factories import make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("role", "statut"),
    [
        (Role.RAI, 200),
        (Role.AUDITEUR, 200),
        (Role.ADMIN, 200),
        (Role.AUDITE, 403),
        (Role.DG, 403),
    ],
)
def test_users_directory_droits(api_client: APIClient, role: str, statut: int) -> None:
    api_client.force_authenticate(make_user(role))
    assert api_client.get("/api/v1/users/").status_code == statut


def test_users_directory_non_authentifie(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/users/").status_code == 401


def test_users_directory_droits_et_filtres(api_client: APIClient) -> None:
    rai = make_user(Role.RAI, last_name="Zongo")
    oued = make_user(Role.AUDITEUR, last_name="Ouedraogo", first_name="Awa", direction_code="DAI")
    make_user(Role.AUDITEUR, last_name="Kabore", direction_code="DEX")
    make_user(Role.AUDITE, last_name="Oued", direction_code="DEX")
    make_user(Role.AUDITEUR, last_name="Oued", is_active=False)
    api_client.force_authenticate(make_user(Role.AUDITE))
    assert api_client.get("/api/v1/users/?role=AUDITEUR&q=oued").status_code == 403

    api_client.force_authenticate(rai)
    r = api_client.get("/api/v1/users/?role=AUDITEUR&q=oued")
    assert r.status_code == 200
    assert [u["id"] for u in r.json()["results"]] == [oued.id]
    assert set(r.json()["results"][0]) == {
        "id",
        "username",
        "nom_complet",
        "role",
        "direction_code",
        "fonction",
    }
    assert r.json()["results"][0]["nom_complet"] == "Awa Ouedraogo"
    r = api_client.get("/api/v1/users/?direction_code=DEX")
    assert {u["role"] for u in r.json()["results"]} == {"AUDITEUR", "AUDITE"}
    # Les comptes désactivés ne sont pas proposés ; tri par nom.
    r = api_client.get("/api/v1/users/?ordering=last_name")
    noms = [u["nom_complet"].split()[-1] for u in r.json()["results"]]
    assert noms == sorted(noms)
    assert api_client.get("/api/v1/users/?role=INCONNU").status_code == 400


def test_page_size_plafonne(api_client: APIClient, rai: User) -> None:
    User.objects.bulk_create(User(username=f"u{i}", role=Role.AUDITEUR) for i in range(210))
    api_client.force_authenticate(rai)
    r = api_client.get("/api/v1/users/?page_size=1000")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 200
    assert r.json()["count"] >= 211
