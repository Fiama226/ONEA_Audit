import pytest
from rest_framework.test import APIClient

from apps.signatures.models import ParametreSignature
from apps.users.models import User

pytestmark = pytest.mark.django_db
URL = "/api/v1/signature-settings/"


def _client(u: User | None) -> APIClient:
    c = APIClient()
    if u is not None:
        c.force_authenticate(user=u)
    return c


def test_api_parametres_droits(admin: User, rai: User, user: User, audite: User, dg: User) -> None:
    assert _client(admin).get(URL).status_code == 200
    assert _client(rai).get(URL).status_code == 200
    for u in (user, audite, dg):
        assert _client(u).get(URL).status_code == 403
        assert (
            _client(u).patch(f"{URL}VALIDATION_RAPPORT/", {"mode": "CONFIRMATION"}).status_code
            == 403
        )
    assert (
        _client(rai).patch(f"{URL}VALIDATION_RAPPORT/", {"mode": "CONFIRMATION"}).status_code == 403
    )
    assert _client(None).get(URL).status_code in (401, 403)
    assert not ParametreSignature.objects.exists()
    assert (
        _client(admin).patch(f"{URL}VALIDATION_RAPPORT/", {"mode": "CONFIRMATION"}).status_code
        == 200
    )


def test_liste_trois_types_non_paginee(admin: User) -> None:
    corps = _client(admin).get(URL).json()
    assert [r["type_document"] for r in corps] == [
        "ORDRE_MISSION",
        "DECLARATION_INDEPENDANCE",
        "VALIDATION_RAPPORT",
    ]
    assert all(r["mode"] == "CONFIRMATION" and r["modifie_le"] is None for r in corps)


def test_modes_disponibles_expose(admin: User, signataire_factice: object) -> None:
    assert [m["mode"] for m in _client(admin).get(URL).json()[0]["modes_disponibles"]] == [
        "CONFIRMATION",
        "SIGNATURE_ELECTRONIQUE",
        "CONFIRMATION_ET_SIGNATURE",
    ]


def test_modes_disponibles_sans_signataire(admin: User) -> None:
    ligne = _client(admin).get(URL).json()[0]
    assert [m["mode"] for m in ligne["modes_disponibles"]] == ["CONFIRMATION"]


def test_patch_electronique_refuse_422(admin: User) -> None:
    r = _client(admin).patch(f"{URL}VALIDATION_RAPPORT/", {"mode": "SIGNATURE_ELECTRONIQUE"})
    assert r.status_code == 422
    assert "pas encore disponible" in r.json()["detail"]


def test_patch_puis_trace(admin: User, signataire_factice: object) -> None:
    r = _client(admin).patch(
        f"{URL}VALIDATION_RAPPORT/", {"mode": "CONFIRMATION_ET_SIGNATURE"}, format="json"
    )
    assert r.status_code == 200
    assert r.json()["mode_libelle"] == "Confirmation et signature électronique"
    assert r.json()["modifie_par"]["id"] == admin.pk
    ligne = next(
        x for x in _client(admin).get(URL).json() if x["type_document"] == "VALIDATION_RAPPORT"
    )
    assert ligne["mode"] == "CONFIRMATION_ET_SIGNATURE" and ligne["modifie_le"]


def test_type_hors_liste_422_et_mode_invalide_400(admin: User) -> None:
    r = _client(admin).patch(f"{URL}REPONSE_CONSTAT/", {"mode": "CONFIRMATION"})
    assert r.status_code == 422
    assert "pas de mode de signature paramétrable" in r.json()["detail"]
    assert _client(admin).patch(f"{URL}VALIDATION_RAPPORT/", {"mode": "PAPIER"}).status_code == 400


def test_ni_creation_ni_suppression(admin: User) -> None:
    c = _client(admin)
    assert c.post(URL, {}).status_code == 405
    assert c.delete(f"{URL}VALIDATION_RAPPORT/").status_code == 405
    assert c.put(f"{URL}VALIDATION_RAPPORT/", {"mode": "CONFIRMATION"}).status_code == 405
