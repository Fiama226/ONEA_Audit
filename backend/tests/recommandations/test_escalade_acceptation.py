"""Règle de gouvernance « escalade d'une acceptation de risque » (Normes IIA 11.5)."""

import pytest
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.constats.models import Constat, Recommandation
from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import Mission, StatutEtape
from apps.notifications.models import Notification
from apps.recommandations.controles import _recommandations_couvertes
from apps.recommandations.models import AcceptationRisque, ValidationAcceptation
from apps.recommandations.services.acceptations import (
    acceptations_a_valider,
    accepter_risque,
    decider_acceptation,
)
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes
from tests.regles import regler

pytestmark = pytest.mark.django_db


def _niveau(reco: Recommandation, probabilite: int, impact: int) -> None:
    Constat._base_manager.filter(pk=reco.constat_id).update(  # noqa: SLF001
        probabilite=probabilite, impact=impact
    )


def _couverte(mission: Mission, reco: Recommandation) -> bool:
    etape = mission.etapes.get(numero=16)
    return not any(
        f"{reco.constat.reference}-{reco.ordre} " in m for m in _recommandations_couvertes(etape)
    )


def test_acceptance_snapshots_the_required_validator(
    recommandations: list[Recommandation], audite_entite_b: User
) -> None:
    reco = recommandations[2]
    _niveau(reco, 5, 4)  # score 20 : élevé
    acceptation = accepter_risque(reco, justification="Coût disproportionné", by=audite_entite_b)
    assert acceptation.niveau_risque == "ELEVE"
    assert acceptation.validation_requise == "DG"


def test_pending_acceptance_does_not_cover_the_recommendation(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_b: User,
    rai: User,
) -> None:
    reco = recommandations[2]
    _niveau(reco, 1, 2)  # faible : RAI par défaut
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_b)
    assert acceptation.validation_requise == "RAI"
    assert not _couverte(mission_en_communication, reco)
    etape = mission_en_communication.etapes.get(numero=16)
    assert any("attend la validation" in m for m in _recommandations_couvertes(etape))
    decider_acceptation(acceptation, decision="VALIDEE", motif="Risque toléré", by=rai)
    assert _couverte(mission_en_communication, reco)


def test_refusal_withdraws_the_acceptance(
    recommandations: list[Recommandation], audite_entite_b: User, rai: User
) -> None:
    reco = recommandations[2]
    _niveau(reco, 1, 2)
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_b)
    decider_acceptation(acceptation, decision="REFUSEE", motif="Risque inacceptable", by=rai)
    assert not AcceptationRisque.objects.filter(pk=acceptation.pk).exists()
    validation = ValidationAcceptation.objects.get(acceptation_id=acceptation.pk)
    assert validation.motif == "Risque inacceptable"
    assert Notification.objects.filter(
        destinataire=audite_entite_b, type="ACCEPTATION_DECIDEE"
    ).exists()


def test_only_the_designated_authority_decides(
    recommandations: list[Recommandation], audite_entite_b: User, rai: User, dg: User
) -> None:
    reco = recommandations[2]
    _niveau(reco, 5, 4)
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_b)
    with pytest.raises(PermissionDenied):
        decider_acceptation(acceptation, decision="VALIDEE", motif="ok", by=rai)
    decider_acceptation(acceptation, decision="VALIDEE", motif="ok", by=dg)
    with pytest.raises(RegleMetierError):
        decider_acceptation(acceptation, decision="VALIDEE", motif="ok", by=dg)


def test_board_decision_is_recorded_by_the_dg_with_a_reference(
    recommandations: list[Recommandation], audite_entite_b: User, dg: User
) -> None:
    regler(rg.RISK_ACCEPTANCE, high="BOARD")
    reco = recommandations[2]
    _niveau(reco, 5, 4)
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_b)
    assert acceptation.validation_requise == "BOARD"
    with pytest.raises(RegleMetierError) as exc:
        decider_acceptation(acceptation, decision="VALIDEE", motif="ok", by=dg)
    assert "reference_conseil" in exc.value.errors
    decider_acceptation(
        acceptation, decision="VALIDEE", motif="ok", by=dg, reference_conseil="Délibération 7"
    )


def test_reason_is_required(
    recommandations: list[Recommandation], audite_entite_b: User, rai: User
) -> None:
    _niveau(recommandations[2], 1, 2)
    acceptation = accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    with pytest.raises(RegleMetierError) as exc:
        decider_acceptation(acceptation, decision="VALIDEE", motif=" ", by=rai)
    assert "motif" in exc.value.errors


def test_no_validation_when_rule_says_none(
    mission_en_communication: Mission, recommandations: list[Recommandation], audite_entite_b: User
) -> None:
    regler(rg.RISK_ACCEPTANCE, low="NONE", medium="NONE")
    reco = recommandations[2]
    _niveau(reco, 1, 2)
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_b)
    assert acceptation.validation_requise == ""
    assert _couverte(mission_en_communication, reco)


def test_rule_change_is_not_retroactive(
    mission_en_communication: Mission, recommandations: list[Recommandation], audite_entite_b: User
) -> None:
    regler(rg.RISK_ACCEPTANCE, low="NONE", medium="NONE")
    reco = recommandations[2]
    _niveau(reco, 1, 2)
    accepter_risque(reco, justification="x", by=audite_entite_b)
    regler(rg.RISK_ACCEPTANCE, low="DG", medium="DG")
    assert _couverte(mission_en_communication, reco)


def test_validators_are_notified_and_see_their_queue(
    recommandations: list[Recommandation], audite_entite_b: User, rai: User, dg: User
) -> None:
    _niveau(recommandations[2], 5, 4)
    acceptation = accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    assert Notification.objects.filter(destinataire=dg, type="ACCEPTATION_A_VALIDER").exists()
    assert [a.pk for a in acceptations_a_valider(dg)] == [acceptation.pk]
    assert list(acceptations_a_valider(rai)) == []


def test_decision_requires_step_xvi_open(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_b: User,
    rai: User,
) -> None:
    _niveau(recommandations[2], 1, 2)
    acceptation = accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        decider_acceptation(acceptation, decision="VALIDEE", motif="ok", by=rai)


# --------------------------------------------------------------------------- API


def test_pending_queue_and_decision_through_the_api(
    api_client: APIClient, recommandations: list[Recommandation], audite_entite_b: User, dg: User
) -> None:
    _niveau(recommandations[2], 5, 4)
    acceptation = accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    api_client.force_authenticate(dg)
    liste = api_client.get("/api/v1/risk-acceptance-validations/")
    assert liste.status_code == 200, liste.content
    assert [a["id"] for a in liste.json()] == [str(acceptation.pk)]
    assert liste.json()[0]["validation_requise"] == "DG"
    reponse = api_client.post(
        f"/api/v1/risk-acceptance-validations/{acceptation.pk}/decide/",
        {"decision": "VALIDEE", "motif": "Accepté par la DG"},
        format="json",
    )
    assert reponse.status_code == 204, reponse.content
    assert api_client.get("/api/v1/risk-acceptance-validations/").json() == []


@pytest.mark.parametrize("role", [Role.AUDITEUR, Role.AUDITE, Role.ADMIN])
def test_queue_is_closed_to_other_roles(api_client: APIClient, role: str) -> None:
    api_client.force_authenticate(make_user(role))
    assert api_client.get("/api/v1/risk-acceptance-validations/").status_code == 403


def test_acceptance_read_shows_the_validation_state(
    api_client: APIClient,
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_b: User,
    rai: User,
) -> None:
    _niveau(recommandations[2], 1, 2)
    acceptation = accepter_risque(recommandations[2], justification="x", by=audite_entite_b)
    api_client.force_authenticate(rai)
    corps = api_client.get(f"/api/v1/risk-acceptances/{acceptation.pk}/").json()
    assert corps["validation_requise"] == "RAI"
    assert corps["validation"] is None
