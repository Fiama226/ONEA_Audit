import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.users.models import User

URL = "/api/v1/user-accounts/import-csv/"
ENTETE = "identifiant;email;prenom;nom;matricule;direction;fonction;role\n"


def _post(client: APIClient, contenu: bytes, **data: object) -> object:
    fichier = SimpleUploadedFile("comptes.csv", contenu, content_type="text/csv")
    return client.post(URL, {"fichier": fichier, **data}, format="multipart")


@pytest.fixture
def admin_client(api_client: APIClient, admin: User) -> APIClient:
    api_client.force_authenticate(admin)
    return api_client


def test_import_csv_dry_run_par_defaut(admin_client: APIClient) -> None:
    r = _post(admin_client, (ENTETE + "kabore.l;k@onea.bf;;;;;;AUDITEUR\n").encode())
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert r.json() == {  # type: ignore[attr-defined]
        "dry_run": True,
        "crees": ["kabore.l"],
        "mis_a_jour": [],
        "ignores": [],
    }
    assert not User.objects.filter(username="kabore.l").exists()


@pytest.mark.parametrize(
    "contenu,fragment",
    [
        (b"\xff\xfe\x00bad", "UTF-8"),
        (b"a" * (1024 * 1024 + 10), "1 Mo"),
        (b"foo;bar\n1;2\n", "identifiant"),
    ],
)
def test_import_csv_400(admin_client: APIClient, contenu: bytes, fragment: str) -> None:
    r = _post(admin_client, contenu)
    assert r.status_code == 400  # type: ignore[attr-defined]
    assert fragment in r.json()["errors"]["fichier"][0]  # type: ignore[attr-defined]


def test_import_csv_fichier_absent_400(admin_client: APIClient) -> None:
    assert admin_client.post(URL, {}, format="multipart").status_code == 400


def test_import_csv_apply_historise_l_admin(admin_client: APIClient, admin: User) -> None:
    from auditlog.models import LogEntry

    r = _post(admin_client, (ENTETE + "nouveau;n@onea.bf;;;;;;RAI\n").encode(), dry_run="false")
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert r.json()["dry_run"] is False  # type: ignore[attr-defined]
    cree = User.objects.get(username="nouveau")
    assert cree.origine == "CSV"
    entree = LogEntry.objects.filter(object_pk=str(cree.pk), action=LogEntry.Action.CREATE).get()
    assert entree.actor_id == admin.pk
