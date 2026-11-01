"""SEC-01 : un UUID envoyé comme entier JSON ne doit pas contourner les gardes de création."""

from uuid import uuid4

import pytest
from django.http import QueryDict
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.identifiants import uuid_du_corps, uuid_strict
from apps.missions.models import Mission
from apps.users.models import User

Equipe = tuple[Mission, dict[str, User]]


def test_uuid_strict_chaine_valide_et_illisible() -> None:
    u = uuid4()
    assert uuid_strict(str(u)) == u
    assert uuid_strict("pas-un-uuid") is None
    assert uuid_strict(None) is None


@pytest.mark.parametrize("brut", [uuid4().int, True, 0, 1.5, [str(uuid4())], {"a": 1}])
def test_uuid_strict_refuse_les_types_non_chaine(brut: object) -> None:
    with pytest.raises(ValidationError):
        uuid_strict(brut, champ="mission")


def test_uuid_du_corps_formulaire_chaine() -> None:
    class Req:
        data = QueryDict("mission=" + str(uuid4()))

    assert uuid_du_corps(Req(), "mission") is not None  # type: ignore[arg-type]


# (route, champ du corps, rôle) : chaque app qui lit un identifiant du corps avant le sérialiseur
SITES = [
    ("/api/v1/meetings/", "mission", "auditeur_non_confirme"),
    ("/api/v1/interviews/", "mission", "auditeur_non_confirme"),
    ("/api/v1/mission-risks/", "mission", "auditeur_non_confirme"),
    ("/api/v1/mission-assignments/", "mission", "rai"),
    ("/api/v1/analysis-questions/", "questionnaire", "auditeur_non_confirme"),
    ("/api/v1/reports/", "mission", "auditeur_non_confirme"),
    ("/api/v1/report-recipients/", "rapport", "rai"),
    ("/api/v1/corrective-actions/", "recommandation", "auditeur_non_confirme"),
    ("/api/v1/risk-acceptances/", "recommandation", "audite_affecte"),
    ("/api/v1/action-plan-commitments/", "mission", "audite_affecte"),
    ("/api/v1/finding-responses/", "constat", "audite_affecte"),
    ("/api/v1/planned-tests/", "programme", "auditeur_non_confirme"),
    ("/api/v1/test-sheets/", "test", "auditeur_non_confirme"),
    ("/api/v1/follow-up/extension-requests/", "action", "audite_affecte"),
]


@pytest.mark.parametrize(("route", "champ", "qui"), SITES)
def test_post_uuid_entier_refuse_400(
    api_client: APIClient, equipe_complete: Equipe, route: str, champ: str, qui: str
) -> None:
    mission, users = equipe_complete
    api_client.force_authenticate(users[qui])
    r = api_client.post(route, {champ: mission.id.int}, format="json")
    assert r.status_code == 400, (route, r.status_code, r.content[:200])
    assert champ in r.json()["errors"], r.json()


def test_sec01_entier_ne_cree_rien(api_client: APIClient, equipe_complete: Equipe) -> None:
    """Le cas exact du banc : l'auditeur à déclaration non levée ne crée plus de réunion."""
    from apps.missions.models import Reunion

    mission, users = equipe_complete
    api_client.force_authenticate(users["auditeur_non_confirme"])
    corps = {"type": "OUVERTURE", "date": "2026-03-02T09:00:00Z"}
    r = api_client.post("/api/v1/meetings/", {"mission": mission.id.int, **corps}, format="json")
    assert r.status_code == 400
    assert not Reunion.objects.filter(mission=mission).exists()
