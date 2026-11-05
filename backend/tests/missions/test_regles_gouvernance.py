"""Branchement des règles de gouvernance sur les étapes : ordre (6) et lecture par l'audité (8)."""

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import (
    DeclarationIndependance,
    EtapeMission,
    Mission,
    StatutDeclaration,
    StatutEtape,
)
from apps.missions.services.etapes import demarrer_etape, predecesseurs_ouverts
from apps.users.models import User
from tests.missions.conftest import forcer_etapes
from tests.regles import regler

pytestmark = pytest.mark.django_db

Equipe = tuple[Mission, dict[str, User]]


def _etape(mission: Mission, numero: int) -> EtapeMission:
    return EtapeMission.objects.get(mission=mission, numero=numero)


def test_strict_order_is_the_default(mission_lancee: Mission, auditeur_mission: User) -> None:
    DeclarationIndependance.objects.update(statut=StatutDeclaration.CONFIRMEE)
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        demarrer_etape(_etape(mission_lancee, 3), by=auditeur_mission)


def test_free_order_lets_any_step_start(mission_lancee: Mission, auditeur_mission: User) -> None:
    DeclarationIndependance.objects.update(statut=StatutDeclaration.CONFIRMEE)
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    regler(rg.STEP_ORDER, mode="FREE")
    assert predecesseurs_ouverts(_etape(mission_lancee, 3)) == []
    etape = demarrer_etape(_etape(mission_lancee, 3), by=auditeur_mission)
    assert etape.statut == StatutEtape.EN_COURS


def test_free_order_shows_start_to_contributors(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    DeclarationIndependance.objects.update(statut=StatutDeclaration.CONFIRMEE)
    regler(rg.STEP_ORDER, mode="FREE")
    api_client.force_authenticate(users["auditeur_confirme"])
    liste = api_client.get(f"/api/v1/mission-steps/?mission={m.id}").json()
    assert all(e["predecesseurs_ouverts"] == [] for e in liste)


def test_auditee_reads_steps_when_allowed(api_client: APIClient, equipe_complete: Equipe) -> None:
    m, users = equipe_complete
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/mission-steps/?mission={m.id}").status_code == 200


def test_auditee_cannot_read_steps_when_forbidden(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    m, users = equipe_complete
    regler(rg.AUDITEE_STEP_READ, allowed=False)
    api_client.force_authenticate(users["audite_affecte"])
    assert api_client.get(f"/api/v1/mission-steps/?mission={m.id}").status_code == 403
    etape = _etape(m, 2)
    assert api_client.get(f"/api/v1/mission-steps/{etape.id}/").status_code == 403
    api_client.force_authenticate(users["auditeur_confirme"])
    assert api_client.get(f"/api/v1/mission-steps/?mission={m.id}").status_code == 200
