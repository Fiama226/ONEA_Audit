"""Règle de gouvernance « réponse de l'audité » : contrôles de clôture (XIII, XIV, XVI),
dérogation motivée, délai de réponse au provisoire."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accomplissement.models import AccordResultats
from apps.accomplissement.services.accords import donner_accord_resultats
from apps.communication.models import Rapport, RapportProvisoire
from apps.communication.services.provisoire import transmettre_provisoire
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.gouvernance import regles_gouvernance as rg
from apps.missions.models import (
    EtapeMission,
    EvenementEtape,
    Mission,
    RoleMission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
    TypeReunion,
)
from apps.missions.services.derogations import deroger, etapes_a_deroger, manquants_audite
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import Role, User
from tests.communication.factories import (
    RapportFactory,
    RapportProvisoireFactory,
    ReponseRapportFactory,
)
from tests.constats.factories import ConstatFactory, ReponseFactory
from tests.factories import DirectionFactory, ReunionFactory, make_user
from tests.missions.conftest import affecter, forcer_etapes
from tests.regles import regler

pytestmark = pytest.mark.django_db


def _etape(mission: Mission, numero: int) -> EtapeMission:
    return EtapeMission.objects.get(mission=mission, numero=numero)


def _valider(constat: Constat) -> Constat:
    constat.soumettre()
    constat.save()
    constat.valider()
    constat.save()
    return constat


# --------------------------------------------------------------------------- XIII


@pytest.fixture
def mission_en_xiii(mission_lancee: Mission) -> Mission:
    entite = DirectionFactory(code="DEX", libelle="Direction de l'exploitation")
    mission_lancee.entites.add(entite)
    forcer_etapes(
        mission_lancee,
        {**{n: StatutEtape.VALIDEE for n in range(1, 13)}, 13: StatutEtape.EN_COURS},
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(
        statut=StatutMission.EN_ACCOMPLISSEMENT, ordre_mission_emis_le=timezone.now()
    )
    mission_lancee.refresh_from_db()
    return mission_lancee


@pytest.fixture
def responsable_dex(mission_en_xiii: Mission) -> User:
    audite = make_user(Role.AUDITE, direction_code="DEX")
    affecter(mission_en_xiii, audite, RoleMission.AUDITE, responsable_entite=True)
    return audite


def test_xiii_requires_the_entity_agreement(
    mission_en_xiii: Mission, responsable_dex: User
) -> None:
    manquants = livrables_manquants(_etape(mission_en_xiii, 13))
    assert any("Direction de l'exploitation" in m for m in manquants)
    entite = mission_en_xiii.entites.get()
    donner_accord_resultats(
        mission_en_xiii, entite=entite, position="ACCORD", commentaire="", by=responsable_dex
    )
    assert livrables_manquants(_etape(mission_en_xiii, 13)) == []


def test_disagreement_needs_a_comment_and_still_counts(
    mission_en_xiii: Mission, responsable_dex: User
) -> None:
    entite = mission_en_xiii.entites.get()
    with pytest.raises(RegleMetierError) as exc:
        donner_accord_resultats(
            mission_en_xiii,
            entite=entite,
            position="DESACCORD",
            commentaire=" ",
            by=responsable_dex,
        )
    assert "commentaire" in exc.value.errors
    donner_accord_resultats(
        mission_en_xiii,
        entite=entite,
        position="DESACCORD",
        commentaire="Échantillon non représentatif.",
        by=responsable_dex,
    )
    assert livrables_manquants(_etape(mission_en_xiii, 13)) == []


def test_only_the_entity_head_agrees(mission_en_xiii: Mission, responsable_dex: User) -> None:
    autre = make_user(Role.AUDITE, direction_code="DEX")
    affecter(mission_en_xiii, autre, RoleMission.AUDITE, responsable_entite=False)
    with pytest.raises(PermissionDenied):
        donner_accord_resultats(
            mission_en_xiii,
            entite=mission_en_xiii.entites.get(),
            position="ACCORD",
            commentaire="",
            by=autre,
        )


def test_agreement_is_append_only(mission_en_xiii: Mission, responsable_dex: User) -> None:
    accord = donner_accord_resultats(
        mission_en_xiii,
        entite=mission_en_xiii.entites.get(),
        position="ACCORD",
        commentaire="",
        by=responsable_dex,
    )
    accord.commentaire = "modifié"
    with pytest.raises(RegleMetierError):
        accord.save()
    assert AccordResultats.objects.count() == 1


def test_xiii_control_off(mission_en_xiii: Mission, responsable_dex: User) -> None:
    regler(rg.AUDITEE_RESPONSE, evidence_agreement=False)
    assert livrables_manquants(_etape(mission_en_xiii, 13)) == []


def test_agreement_through_the_api(
    api_client: APIClient, mission_en_xiii: Mission, responsable_dex: User
) -> None:
    api_client.force_authenticate(responsable_dex)
    entite = mission_en_xiii.entites.get()
    reponse = api_client.post(
        "/api/v1/test-results-agreements/",
        {"mission": str(mission_en_xiii.pk), "entite": str(entite.pk), "position": "ACCORD"},
        format="json",
    )
    assert reponse.status_code == 201, reponse.content
    liste = api_client.get(f"/api/v1/test-results-agreements/?mission={mission_en_xiii.pk}")
    assert liste.status_code == 200
    assert [a["position"] for a in liste.json()] == ["ACCORD"]


# --------------------------------------------------------------------------- XIV


@pytest.fixture
def constat_xiv(mission_lancee: Mission) -> Constat:
    constat: Constat = ConstatFactory(mission=mission_lancee)
    forcer_etapes(
        mission_lancee,
        {**{n: StatutEtape.VALIDEE for n in range(1, 14)}, 14: StatutEtape.EN_COURS},
    )
    return _valider(constat)


def test_xiv_requires_the_auditee_position(constat_xiv: Constat) -> None:
    etape = _etape(constat_xiv.mission, 14)
    assert any(constat_xiv.reference in m for m in livrables_manquants(etape))
    ReponseFactory(constat=constat_xiv, cycle=constat_xiv.cycle)
    assert livrables_manquants(etape) == []


def test_xiv_response_of_an_older_cycle_does_not_count(constat_xiv: Constat) -> None:
    ReponseFactory(constat=constat_xiv, cycle=constat_xiv.cycle)
    Constat._base_manager.filter(pk=constat_xiv.pk).update(  # noqa: SLF001
        cycle=constat_xiv.cycle + 1
    )
    assert manquants_audite(_etape(constat_xiv.mission, 14))


# --------------------------------------------------------------------------- dérogation


def test_rai_waives_with_a_logged_reason(constat_xiv: Constat, rai: User) -> None:
    etape = _etape(constat_xiv.mission, 14)
    with pytest.raises(RegleMetierError) as exc:
        deroger(etape, motif="  ", by=rai)
    assert "motif" in exc.value.errors
    deroger(etape, motif="Audité absent, relancé trois fois.", by=rai)
    assert livrables_manquants(etape) == []
    evenement = EvenementEtape.objects.get(etape=etape, type=TypeEvenementEtape.DEROGATION)
    assert "relancé trois fois" in evenement.motif
    assert evenement.statut_avant == evenement.statut_apres == StatutEtape.EN_COURS


def test_only_the_designated_role_waives(constat_xiv: Constat, rai: User, dg: User) -> None:
    etape = _etape(constat_xiv.mission, 14)
    with pytest.raises(PermissionDenied):
        deroger(etape, motif="x", by=make_user(Role.AUDITEUR))
    with pytest.raises(PermissionDenied):
        deroger(etape, motif="x", by=dg)
    regler(rg.AUDITEE_RESPONSE, waiver_by="DG")
    with pytest.raises(PermissionDenied):
        deroger(etape, motif="x", by=rai)
    deroger(etape, motif="Décision de la DG", by=dg)


def test_reason_optional_when_the_rule_says_so(constat_xiv: Constat, rai: User) -> None:
    regler(rg.AUDITEE_RESPONSE, reason_required=False)
    deroger(_etape(constat_xiv.mission, 14), motif="", by=rai)


def test_waiver_only_when_something_is_missing(constat_xiv: Constat, rai: User) -> None:
    ReponseFactory(constat=constat_xiv, cycle=constat_xiv.cycle)
    with pytest.raises(RegleMetierError):
        deroger(_etape(constat_xiv.mission, 14), motif="x", by=rai)


def test_waiver_is_lost_when_the_step_is_reopened(constat_xiv: Constat, rai: User) -> None:
    etape = _etape(constat_xiv.mission, 14)
    deroger(etape, motif="x", by=rai)
    EvenementEtape.objects.create(
        etape=etape,
        type=TypeEvenementEtape.ROUVERTE,
        par=rai,
        le=timezone.now() + timedelta(seconds=1),
        statut_avant=StatutEtape.VALIDEE,
        statut_apres=StatutEtape.EN_COURS,
    )
    assert livrables_manquants(etape)


def test_waiver_queue_for_the_designated_role(constat_xiv: Constat, rai: User, dg: User) -> None:
    attendues = etapes_a_deroger(rai)
    assert [(e["etape"].pk, e["etape"].numero) for e in attendues] == [
        (_etape(constat_xiv.mission, 14).pk, 14)
    ]
    assert etapes_a_deroger(dg) == []


def test_waiver_queue_and_waiver_through_the_api(
    api_client: APIClient, constat_xiv: Constat, dg: User
) -> None:
    regler(rg.AUDITEE_RESPONSE, waiver_by="DG")
    api_client.force_authenticate(dg)
    liste = api_client.get("/api/v1/auditee-response-waivers/")
    assert liste.status_code == 200, liste.content
    [ligne] = liste.json()
    assert ligne["numero"] == 14 and ligne["manquants"]
    reponse = api_client.post(
        f"/api/v1/auditee-response-waivers/{ligne['etape']}/waive/",
        {"motif": "Audité injoignable"},
        format="json",
    )
    assert reponse.status_code == 204, reponse.content
    assert api_client.get("/api/v1/auditee-response-waivers/").json() == []


@pytest.mark.parametrize("role", [Role.AUDITEUR, Role.AUDITE, Role.ADMIN])
def test_waiver_queue_is_closed_to_other_roles(api_client: APIClient, role: str) -> None:
    api_client.force_authenticate(make_user(role))
    assert api_client.get("/api/v1/auditee-response-waivers/").status_code == 403


# --------------------------------------------------------------------------- XVI


def _provisoire(mission_lancee: Mission, *, dans_jours: int) -> RapportProvisoire:
    constat = _valider(ConstatFactory(mission=mission_lancee))
    forcer_etapes(
        mission_lancee,
        {
            **{n: StatutEtape.VALIDEE for n in range(1, 15)},
            15: StatutEtape.TERMINEE,
            16: StatutEtape.EN_COURS,
        },
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    rapport = RapportFactory(mission=mission_lancee)
    provisoire: RapportProvisoire = RapportProvisoireFactory(
        rapport=rapport,
        instantane={"constats": [{"reference": constat.reference}]},
        date_limite_reponses=timezone.localdate() + timedelta(days=dans_jours),
    )
    return provisoire


@pytest.fixture
def provisoire_xvi(mission_lancee: Mission) -> RapportProvisoire:
    return _provisoire(mission_lancee, dans_jours=5)


def _messages_xvi(provisoire: RapportProvisoire) -> list[str]:
    return manquants_audite(_etape(provisoire.mission, 16))


def test_xvi_waits_for_a_response_until_the_deadline(provisoire_xvi: RapportProvisoire) -> None:
    assert any("réponse" in m for m in _messages_xvi(provisoire_xvi))


def test_xvi_passes_once_the_deadline_is_over(mission_lancee: Mission) -> None:
    provisoire = _provisoire(mission_lancee, dans_jours=-1)
    assert _messages_xvi(provisoire) == []


def test_xvi_response_received(provisoire_xvi: RapportProvisoire) -> None:
    constat = Constat.objects.get(mission=provisoire_xvi.mission)
    ReponseRapportFactory(provisoire=provisoire_xvi, constat=constat)
    assert _messages_xvi(provisoire_xvi) == []


def test_xvi_control_off(provisoire_xvi: RapportProvisoire) -> None:
    regler(rg.AUDITEE_RESPONSE, response_or_deadline=False)
    assert all("réponse" not in m for m in livrables_manquants(_etape(provisoire_xvi.mission, 16)))


# --------------------------------------------------------------------------- délai


def test_provisional_report_uses_the_rule_delay(mission_lancee: Mission, rai: User) -> None:
    _valider(ConstatFactory(mission=mission_lancee))
    forcer_etapes(
        mission_lancee,
        {**{n: StatutEtape.VALIDEE for n in range(1, 15)}, 15: StatutEtape.EN_COURS},
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.EN_COMMUNICATION)
    ReunionFactory(mission=mission_lancee, type=TypeReunion.CLOTURE, tenue_le=timezone.now())
    regler(rg.AUDITEE_RESPONSE, delay_days=21)
    rapport: Rapport = RapportFactory(mission=mission_lancee)
    provisoire = transmettre_provisoire(rapport, by=rai)
    assert provisoire.date_limite_reponses == timezone.localdate() + timedelta(days=21)
