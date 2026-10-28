import pytest
from rest_framework.test import APIClient

from tests.factories import make_user
from tests.referentiel.typed import processus as make_processus

from .factories import ligne, programme

MATRICE = [
    ("ADMIN", 200, 403),
    ("RAI", 200, 201),
    ("AUDITEUR", 200, 403),
    ("AUDITE", 403, 403),
    ("DG", 200, 403),
]


@pytest.mark.parametrize(("role", "read", "write"), MATRICE)
def test_droits_sur_les_lignes(
    db: None, api_client: APIClient, role: str, read: int, write: int
) -> None:
    api_client.force_authenticate(make_user(role))
    p, proc = programme(annee=2026), make_processus(code="FEP")
    assert api_client.get("/api/v1/audit-plan-lines/").status_code == read
    body = {
        "programme": str(p.id),
        "titre": "Achats",
        "type": "ASSURANCE",
        "processus": str(proc.id),
        "debut_prevu": "2026-03-02",
        "fin_prevue": "2026-04-30",
    }
    assert api_client.post("/api/v1/audit-plan-lines/", body, format="json").status_code == write


@pytest.mark.parametrize(("role", "read", "write"), MATRICE)
def test_droits_sur_les_programmes(
    db: None, api_client: APIClient, role: str, read: int, write: int
) -> None:
    api_client.force_authenticate(make_user(role))
    assert api_client.get("/api/v1/audit-plans/").status_code == read
    r = api_client.post("/api/v1/audit-plans/", {"annee": 2027}, format="json")
    assert r.status_code == write


@pytest.mark.parametrize(("role", "read", "write"), MATRICE)
def test_droits_validate_et_summary(
    db: None, api_client: APIClient, role: str, read: int, write: int
) -> None:
    api_client.force_authenticate(make_user(role))
    p = programme(annee=2026)
    ligne(programme=p)
    assert api_client.get(f"/api/v1/audit-plans/{p.id}/summary/").status_code == read
    r = api_client.post(f"/api/v1/audit-plans/{p.id}/validate/")
    assert r.status_code == (200 if write == 201 else write)


def test_anonyme_refuse(api_client: APIClient, db: None) -> None:
    assert api_client.get("/api/v1/audit-plans/").status_code in (401, 403)
