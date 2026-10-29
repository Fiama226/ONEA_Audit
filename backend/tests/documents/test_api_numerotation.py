import pytest
from rest_framework.test import APIClient

from apps.documents.models import FormatNumerotation
from apps.documents.moteur.registre import TypeDocument
from apps.users.models import User

pytestmark = pytest.mark.django_db

URL = "/api/v1/numbering-formats/"


def test_lecture_sans_ecriture_en_base(
    api_client: APIClient, rai: User, type_test: TypeDocument
) -> None:
    api_client.force_authenticate(rai)
    r = api_client.get(URL)
    assert r.status_code == 200
    f = next(x for x in r.json() if x["type_document"] == "TEST_DOC")
    assert (f["modele"], f["portee"], f["abreviation"]) == (
        "{mission}/{code}-{sequence}",
        "MISSION",
        "TD",
    )
    assert FormatNumerotation.all_objects.count() == 0  # a read never writes
    assert api_client.get(f"{URL}TEST_DOC/").status_code == 200
    assert api_client.get(f"{URL}INCONNU/").status_code == 404


def test_numbering_patch_et_preview_erreurs(
    api_client: APIClient, admin: User, rai: User, type_test: TypeDocument
) -> None:
    api_client.force_authenticate(rai)
    assert api_client.patch(f"{URL}TEST_DOC/", {"abreviation": "X"}).status_code == 403
    assert api_client.post(f"{URL}preview/", {}, format="json").status_code == 403
    api_client.force_authenticate(admin)
    r = api_client.patch(
        f"{URL}TEST_DOC/",
        {"modele": "{annee}/{code}-{sequence}", "portee": "ANNEE", "abreviation": "TX"},
        format="json",
    )
    assert r.status_code == 200 and r.json()["apercu"] == "2026/TX-01"
    mauvais = api_client.patch(f"{URL}TEST_DOC/", {"modele": "{inconnu}"}, format="json")
    assert mauvais.status_code == 422 and mauvais.json()["errors"]["modele"]
    assert (
        api_client.patch(f"{URL}TEST_DOC/", {"portee": "AUTRE"}, format="json").status_code == 400
    )
    assert api_client.put(f"{URL}TEST_DOC/", {}, format="json").status_code == 405


def test_preview(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    ok = api_client.post(
        f"{URL}preview/",
        {"modele": "{mission}/{code}-{sequence}", "portee": "MISSION", "abreviation": "OM"},
        format="json",
    )
    assert ok.status_code == 200
    assert ok.json() == {"numero": "DAI/2026/M07/OM-01", "errors": {}}
    ko = api_client.post(
        f"{URL}preview/",
        {"modele": "{x}", "portee": "MISSION", "abreviation": "bad code"},
        format="json",
    )
    assert ko.status_code == 200 and ko.json()["numero"] is None
    assert ko.json()["errors"]["modele"] and ko.json()["errors"]["abreviation"]
