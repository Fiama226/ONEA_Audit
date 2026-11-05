"""Règle de gouvernance « approbation du programme annuel » (Normes IIA 9.4)."""

from datetime import date

import pytest
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import EvenementDeclencheur, RoleMission, StatutMission
from apps.missions.services.missions import lancer_mission
from apps.notifications.models import Notification
from apps.programmation.models import ApprobationProgramme, ProgrammeAnnuel
from apps.programmation.services import (
    approuver_programme,
    etat_approbation,
    valider_programme,
)
from apps.users.models import Role, User
from tests.factories import AffectationFactory, MissionFactory, make_user
from tests.regles import regler

from .factories import ligne, programme

pytestmark = pytest.mark.django_db


def _approuver_tout(prog: ProgrammeAnnuel, dg: User) -> None:
    approuver_programme(prog, niveau="DG", by=dg)
    approuver_programme(
        prog, niveau="BOARD", by=dg, reference="Délibération n° 2026-03", date_decision=date.today()
    )


def test_default_requires_dg_and_board(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    etat = etat_approbation(programme_valide)
    assert etat["requise"] is True
    assert etat["approuve"] is False
    assert etat["manquantes"] == ["DG", "BOARD"]
    approuver_programme(programme_valide, niveau="DG", by=dg, commentaire="Vu.")
    assert etat_approbation(programme_valide)["manquantes"] == ["BOARD"]
    approuver_programme(
        programme_valide,
        niveau="BOARD",
        by=dg,
        reference="Délibération n° 2026-03",
        date_decision=date(2026, 1, 20),
    )
    etat = etat_approbation(programme_valide)
    assert etat["approuve"] is True
    assert [a["niveau"] for a in etat["approbations"]] == ["DG", "BOARD"]


def test_only_the_dg_records_an_approval(programme_valide: ProgrammeAnnuel, rai: User) -> None:
    with pytest.raises(PermissionDenied):
        approuver_programme(programme_valide, niveau="DG", by=rai)


def test_draft_programme_cannot_be_approved(dg: User) -> None:
    brouillon = programme()
    with pytest.raises(RegleMetierError):
        approuver_programme(brouillon, niveau="DG", by=dg)


def test_board_after_dg_and_with_a_reference(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    with pytest.raises(RegleMetierError):
        approuver_programme(programme_valide, niveau="BOARD", by=dg, reference="D-1")
    approuver_programme(programme_valide, niveau="DG", by=dg)
    with pytest.raises(RegleMetierError) as exc:
        approuver_programme(programme_valide, niveau="BOARD", by=dg, reference=" ")
    assert "reference" in exc.value.errors


def test_approval_is_recorded_once(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    approuver_programme(programme_valide, niveau="DG", by=dg)
    with pytest.raises(RegleMetierError):
        approuver_programme(programme_valide, niveau="DG", by=dg)


def test_no_approver_rule(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    regler(rg.PROGRAM_APPROVAL, approver="NONE")
    etat = etat_approbation(programme_valide)
    assert etat == {**etat, "requise": False, "approuve": True, "manquantes": []}
    with pytest.raises(RegleMetierError):
        approuver_programme(programme_valide, niveau="DG", by=dg)


def test_dg_only_rule(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    regler(rg.PROGRAM_APPROVAL, approver="DG")
    approuver_programme(programme_valide, niveau="DG", by=dg)
    assert etat_approbation(programme_valide)["approuve"] is True
    with pytest.raises(RegleMetierError):
        approuver_programme(programme_valide, niveau="BOARD", by=dg, reference="D-1")


def test_approval_cannot_be_changed_or_deleted(programme_valide: ProgrammeAnnuel, dg: User) -> None:
    approuver_programme(programme_valide, niveau="DG", by=dg)
    approbation = ApprobationProgramme.objects.get()
    approbation.commentaire = "Modifié"
    with pytest.raises(RegleMetierError):
        approbation.save()
    with pytest.raises(RegleMetierError):
        approbation.soft_delete(dg)


def test_validation_notifies_the_dg(rai: User, dg: User) -> None:
    prog = programme()
    ligne(programme=prog, numero=1)
    valider_programme(prog, by=rai)
    assert Notification.objects.filter(destinataire=dg, type="PROGRAMME_A_APPROUVER").exists()


def _mission_planifiee(annee: int, rai: User) -> object:
    mission = MissionFactory(
        statut=StatutMission.PLANIFIEE,
        reference=f"DAI/{annee}/M01",
        annee=annee,
        numero=1,
        evenement_declencheur=EvenementDeclencheur.PROGRAMME_ANNUEL,
    )
    from apps.missions.models import EtapeMission

    for numero in range(1, 19):
        EtapeMission.objects.create(mission=mission, numero=numero)
    AffectationFactory(
        mission=mission, utilisateur=make_user(Role.AUDITEUR), role_mission=RoleMission.CHEF_MISSION
    )
    return mission


def test_launch_requires_an_approved_programme(
    programme_valide: ProgrammeAnnuel, rai: User, dg: User
) -> None:
    mission = _mission_planifiee(programme_valide.annee, rai)
    with pytest.raises(RegleMetierError) as exc:
        lancer_mission(mission, by=rai)
    assert "approuv" in exc.value.message
    _approuver_tout(programme_valide, dg)
    assert lancer_mission(mission, by=rai).statut == StatutMission.EN_PLANIFICATION


def test_launch_without_programme_of_the_year_is_refused(rai: User) -> None:
    mission = _mission_planifiee(2031, rai)
    with pytest.raises(RegleMetierError):
        lancer_mission(mission, by=rai)


def test_launch_not_required_when_rule_says_so(
    programme_valide: ProgrammeAnnuel, rai: User
) -> None:
    regler(rg.PROGRAM_APPROVAL, required_before_launch=False)
    mission = _mission_planifiee(programme_valide.annee, rai)
    assert lancer_mission(mission, by=rai).statut == StatutMission.EN_PLANIFICATION


def test_mission_outside_the_programme_launches_freely(rai: User) -> None:
    mission = _mission_planifiee(2031, rai)
    type(mission).objects.filter(pk=mission.pk).update(
        evenement_declencheur=EvenementDeclencheur.DEMANDE_MANAGEMENT
    )
    mission.refresh_from_db()
    assert lancer_mission(mission, by=rai).statut == StatutMission.EN_PLANIFICATION


# --------------------------------------------------------------------------- API


def test_dg_approves_through_the_api(
    api_client: APIClient, programme_valide: ProgrammeAnnuel, dg: User
) -> None:
    api_client.force_authenticate(dg)
    url = f"/api/v1/audit-plans/{programme_valide.pk}/approve/"
    reponse = api_client.post(
        url, {"niveau": "DG", "commentaire": "Vu et approuvé."}, format="json"
    )
    assert reponse.status_code == 200, reponse.json()
    approbation = reponse.json()["approbation"]
    assert approbation["manquantes"] == ["BOARD"]
    assert approbation["approbations"][0]["approuve_par"]["id"] == dg.pk
    reponse = api_client.post(
        url,
        {"niveau": "BOARD", "reference": "Délibération 12", "date_decision": "2026-01-20"},
        format="json",
    )
    assert reponse.status_code == 200, reponse.json()
    assert reponse.json()["approbation"]["approuve"] is True


@pytest.mark.parametrize("role", [Role.RAI, Role.ADMIN, Role.AUDITEUR])
def test_other_roles_cannot_approve(
    api_client: APIClient, programme_valide: ProgrammeAnnuel, role: str
) -> None:
    api_client.force_authenticate(make_user(role))
    reponse = api_client.post(
        f"/api/v1/audit-plans/{programme_valide.pk}/approve/", {"niveau": "DG"}, format="json"
    )
    assert reponse.status_code == 403


def test_programme_read_shows_the_approval_state(
    api_client: APIClient, programme_valide: ProgrammeAnnuel, rai: User
) -> None:
    api_client.force_authenticate(rai)
    corps = api_client.get(f"/api/v1/audit-plans/{programme_valide.pk}/").json()
    assert corps["approbation"]["requise"] is True
    assert corps["approbation"]["approbateur"] == "DG_AND_BOARD"
