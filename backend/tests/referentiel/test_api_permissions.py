"""Matrice des droits (D4) : rôle x endpoint x méthode."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.referentiel.models import StatutCartographie
from apps.referentiel.services import valider_version
from apps.users.models import Role, User
from tests.factories import make_user
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

TOUS = ["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"]
# (rôles en lecture, rôles en écriture)
STRUCTURE = ("ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"), ("ADMIN", "RAI")
CARTO = ("ADMIN", "RAI", "AUDITEUR", "DG"), ("RAI",)


def _statut(role: str, autorises: tuple[str, ...], ok: int) -> int:
    return ok if role in autorises else 403


def _client(role: str) -> APIClient:
    client = APIClient()
    client.force_authenticate(make_user(role))
    return client


def test_anonyme_401() -> None:
    assert APIClient().get("/api/v1/risks/").status_code == 401
    assert APIClient().get("/api/v1/directions/").status_code == 401


@pytest.mark.parametrize("role", TOUS)
def test_droits_directions(role: str) -> None:
    lecture, ecriture = STRUCTURE
    c = _client(role)
    d = typed.direction()
    base = "/api/v1/directions/"
    assert c.get(base).status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{d.id}/").status_code == _statut(role, lecture, 200)
    body = {"code": "NEWD", "libelle": "Nouvelle", "type": "DIRECTION"}
    assert c.post(base, body, format="json").status_code == _statut(role, ecriture, 201)
    assert c.patch(f"{base}{d.id}/", {"libelle": "X"}, format="json").status_code == _statut(
        role, ecriture, 200
    )
    assert c.delete(f"{base}{d.id}/").status_code == _statut(role, ecriture, 204)


@pytest.mark.parametrize("role", TOUS)
def test_droits_processus(role: str) -> None:
    lecture, ecriture = STRUCTURE
    c = _client(role)
    p = typed.processus()
    base = "/api/v1/processes/"
    assert c.get(base).status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{p.id}/").status_code == _statut(role, lecture, 200)
    body = {"code": "NEW", "libelle": "Nouveau", "famille": "SUPPORT"}
    assert c.post(base, body, format="json").status_code == _statut(role, ecriture, 201)
    assert c.patch(f"{base}{p.id}/", {"libelle": "X"}, format="json").status_code == _statut(
        role, ecriture, 200
    )
    assert c.delete(f"{base}{p.id}/").status_code == _statut(role, ecriture, 204)


@pytest.mark.parametrize("role", TOUS)
def test_droits_objets_auditables(role: str) -> None:
    lecture, ecriture = CARTO
    c = _client(role)
    o = typed.objet()
    base = "/api/v1/auditable-objects/"
    assert c.get(base).status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{o.id}/").status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}tree/?processus={o.processus_id}").status_code == _statut(
        role, lecture, 200
    )
    body = {"processus": str(o.processus_id), "nature": "DOMAINE", "libelle": "Dom"}
    assert c.post(base, body, format="json").status_code == _statut(role, ecriture, 201)
    assert c.patch(f"{base}{o.id}/", {"libelle": "X"}, format="json").status_code == _statut(
        role, ecriture, 200
    )
    assert c.delete(f"{base}{o.id}/").status_code == _statut(role, ecriture, 204)


@pytest.mark.parametrize("role", TOUS)
def test_droits_cartographies(role: str) -> None:
    lecture, ecriture = CARTO
    c = _client(role)
    v = typed.version(annee=2030)
    autre = typed.version(annee=2031)
    base = "/api/v1/risk-maps/"
    assert c.get(base).status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{v.id}/").status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{v.id}/matrix/").status_code == _statut(role, lecture, 200)
    assert c.get(f"{base}{v.id}/compare/?with={autre.id}").status_code == _statut(
        role, lecture, 200
    )
    body = {"annee": 2040, "libelle": "Cartographie 2040"}
    assert c.post(base, body, format="json").status_code == _statut(role, ecriture, 201)
    assert c.patch(f"{base}{v.id}/", {"libelle": "X"}, format="json").status_code == _statut(
        role, ecriture, 200
    )
    assert c.delete(f"{base}{v.id}/").status_code == _statut(role, ecriture, 204)


@pytest.mark.parametrize("role", TOUS)
def test_droits_validation(role: str) -> None:
    v = typed.version(annee=2032)
    typed.risque(version=v)
    r = _client(role).post(f"/api/v1/risk-maps/{v.id}/validate/")
    assert r.status_code == _statut(role, ("RAI",), 200)


@pytest.mark.parametrize("role", TOUS)
def test_droits_risques(role: str) -> None:
    lecture, ecriture = CARTO
    c = _client(role)
    v = typed.version(annee=2033)
    p = typed.processus(code="FEP")
    r = typed.risque(version=v, processus=p)
    assert c.get("/api/v1/risks/").status_code == _statut(role, lecture, 200)
    assert c.get(f"/api/v1/risks/{r.id}/").status_code == _statut(role, lecture, 200)
    body: dict[str, Any] = {
        "version": str(v.id),
        "processus": str(p.id),
        "libelle": "Rupture",
        "probabilite": 3,
        "impact": 5,
    }
    assert c.post("/api/v1/risks/", body, format="json").status_code == _statut(role, ecriture, 201)
    assert c.patch(f"/api/v1/risks/{r.id}/", {"impact": 4}, format="json").status_code == _statut(
        role, ecriture, 200
    )
    assert c.delete(f"/api/v1/risks/{r.id}/").status_code == _statut(role, ecriture, 204)


def test_pas_de_put(auth_rai: APIClient) -> None:
    d = typed.direction()
    assert auth_rai.put(f"/api/v1/directions/{d.id}/", {}, format="json").status_code == 405


def test_audite_403_au_format_unique() -> None:
    r = _client("AUDITE").get("/api/v1/risks/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Accès refusé.", "errors": {}}


def test_validee_lisible_par_dg_mais_pas_modifiable(rai: User) -> None:
    v = typed.version(annee=2034)
    typed.risque(version=v)
    valider_version(v, by=rai)
    v.refresh_from_db()
    assert v.statut == StatutCartographie.VALIDEE
    dg = _client(Role.DG)
    assert dg.get(f"/api/v1/risk-maps/{v.id}/").status_code == 200
    r = dg.patch(f"/api/v1/risk-maps/{v.id}/", {"libelle": "x"}, format="json")
    assert r.status_code == 403
