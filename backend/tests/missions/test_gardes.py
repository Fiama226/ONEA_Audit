import uuid

import pytest
from django.db import transaction
from django.http import Http404

from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.gardes import (
    STATUTS_ETAPE_CLOSE,
    STATUTS_FIGES,
    exiger_etape_ouverte,
    verrouiller_mission,
)
from apps.missions.models import (
    AffectationMission,
    Entretien,
    EtapeMission,
    Mission,
    Reunion,
    RisqueMission,
    StatutEtape,
    StatutMission,
)
from tests.factories import (
    AffectationFactory,
    EntretienFactory,
    ReunionFactory,
    RisqueMissionFactory,
    make_user,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _figer(mission: Mission, statut: str = "SUSPENDUE") -> None:
    Mission.objects.filter(pk=mission.pk).update(
        statut=statut,
        statut_avant_suspension="EN_PLANIFICATION" if statut == "SUSPENDUE" else "",
    )


def test_constantes() -> None:
    assert {
        StatutMission.SUSPENDUE,
        StatutMission.ANNULEE,
        StatutMission.CLOTUREE,
    } == STATUTS_FIGES
    assert {
        StatutEtape.TERMINEE,
        StatutEtape.VALIDEE,
        StatutEtape.A_REVALIDER,
    } == STATUTS_ETAPE_CLOSE


def test_messages() -> None:
    assert str(MissionFigeeError("DAI/2026/M01", "suspendue")) == (
        "La mission DAI/2026/M01 est suspendue : aucune modification n'est possible."
    )
    assert str(EtapeCloseError("II")) == (
        "L'étape II est terminée : rouvrez-la pour modifier ses travaux."
    )


def test_save_direct_refuse_si_etape_close(mission_lancee: Mission) -> None:
    r = ReunionFactory(mission=mission_lancee, type="OUVERTURE")
    forcer_etapes(mission_lancee, {2: "TERMINEE"})
    r.refresh_from_db()
    r.decisions = "contournement"
    with pytest.raises(EtapeCloseError):
        r.save()
    with pytest.raises(EtapeCloseError):
        Reunion.objects.filter(pk=r.pk).update(decisions="x")


def test_mission_suspendue_refuse_save_sauf_reprise(mission_lancee: Mission) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(
        statut="SUSPENDUE", statut_avant_suspension="EN_PLANIFICATION"
    )
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.titre = "x"
    with pytest.raises(MissionFigeeError):
        m.save()
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.statut = m.statut_avant_suspension
    m.statut_avant_suspension = ""
    m.save(update_fields=["statut", "statut_avant_suspension", "updated_by", "updated_at"])
    assert Mission.objects.get(pk=m.pk).statut == "EN_PLANIFICATION"


def test_reprise_ne_peut_pas_modifier_d_autres_champs(mission_lancee: Mission) -> None:
    _figer(mission_lancee)
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.statut = "EN_PLANIFICATION"
    m.titre = "autre"
    with pytest.raises(MissionFigeeError):
        m.save(update_fields=["statut", "titre"])
    with pytest.raises(MissionFigeeError):
        m.save()


@pytest.mark.parametrize("statut", ["ANNULEE", "CLOTUREE"])
def test_annulee_ou_cloturee_jamais_de_reprise(mission_lancee: Mission, statut: str) -> None:
    _figer(mission_lancee, statut)
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.statut = "EN_PLANIFICATION"
    with pytest.raises(MissionFigeeError):
        m.save(update_fields=["statut", "updated_at"])


def test_champs_d17_geles_quand_etape_i_close(mission_lancee: Mission) -> None:
    forcer_etapes(mission_lancee, {1: "TERMINEE"})
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.titre = "nouveau titre"
    with pytest.raises(EtapeCloseError) as exc:
        m.save()
    assert "I " in str(exc.value)
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.objectifs = "x"
    with pytest.raises(EtapeCloseError):
        m.save(update_fields=["objectifs"])
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.budget_jours = 12
    m.save()
    assert Mission.objects.get(pk=m.pk).budget_jours == 12


def test_champs_d17_libres_quand_etape_i_ouverte(mission_lancee: Mission) -> None:
    m = Mission.objects.get(pk=mission_lancee.pk)
    m.titre = "nouveau titre"
    m.save()


def test_enfants_refuses_quand_mission_figee(mission_lancee: Mission) -> None:
    aff = AffectationFactory(mission=mission_lancee, role_mission="AUDITEUR")
    reunion = ReunionFactory(mission=mission_lancee, type="CLOTURE")
    entretien = EntretienFactory(mission=mission_lancee)
    risque = RisqueMissionFactory(mission=mission_lancee)
    etape = EtapeMission.objects.get(mission=mission_lancee, numero=3)
    _figer(mission_lancee)
    for obj in (aff, reunion, entretien, risque, etape):
        obj.refresh_from_db()
        with pytest.raises(MissionFigeeError):
            obj.save()
    with pytest.raises(MissionFigeeError):
        AffectationFactory(mission=mission_lancee, role_mission="AUDITEUR")
    with pytest.raises(MissionFigeeError):
        AffectationMission.objects.filter(pk=aff.pk).update(role_mission="AUDITE")
    with pytest.raises(MissionFigeeError):
        EtapeMission.objects.filter(pk=etape.pk).update(statut="EN_COURS")
    with pytest.raises(MissionFigeeError):
        Entretien.objects.filter(pk=entretien.pk).update(objet="x")
    risque.libelle = "x"
    with pytest.raises(MissionFigeeError):
        RisqueMission.objects.bulk_update([risque], ["libelle"])
    with pytest.raises(MissionFigeeError):
        aff.soft_delete(make_user())


def test_bulk_create_refuse_si_mission_figee(mission_lancee: Mission) -> None:
    _figer(mission_lancee)
    with pytest.raises(MissionFigeeError):
        AffectationMission.objects.bulk_create(
            [
                AffectationMission(
                    mission=mission_lancee, utilisateur=make_user(), role_mission="AUDITEUR"
                )
            ]
        )


def test_entretien_gele_quand_son_etape_est_close(mission_lancee: Mission) -> None:
    etape = EtapeMission.objects.get(mission=mission_lancee, numero=3)
    entretien = EntretienFactory(mission=mission_lancee, etape=etape)
    libre = EntretienFactory(mission=mission_lancee)
    forcer_etapes(mission_lancee, {3: "VALIDEE"})
    entretien.refresh_from_db()
    entretien.compte_rendu = "x"
    with pytest.raises(EtapeCloseError):
        entretien.save()
    with pytest.raises(EtapeCloseError):
        Entretien.objects.filter(pk=entretien.pk).update(compte_rendu="x")
    libre.compte_rendu = "ok"
    libre.save()


def test_risque_mission_gele_quand_etape_iv_close(mission_lancee: Mission) -> None:
    risque = RisqueMissionFactory(mission=mission_lancee)
    forcer_etapes(mission_lancee, {4: "A_REVALIDER"})
    risque.refresh_from_db()
    risque.commentaire = "x"
    with pytest.raises(EtapeCloseError):
        risque.save()
    with pytest.raises(EtapeCloseError):
        RisqueMission.objects.filter(pk=risque.pk).update(commentaire="x")
    with pytest.raises(EtapeCloseError):
        RisqueMissionFactory(mission=mission_lancee)
    with pytest.raises(EtapeCloseError):
        risque.soft_delete(make_user())


def test_reunion_etape_close_refuse_creation(mission_lancee: Mission) -> None:
    forcer_etapes(mission_lancee, {11: "TERMINEE"})
    with pytest.raises(EtapeCloseError):
        ReunionFactory(mission=mission_lancee, type="LANCEMENT")
    reunion = ReunionFactory(mission=mission_lancee, type="OUVERTURE")
    reunion.decisions = "ok"
    Reunion.objects.bulk_update([reunion], ["decisions"])


def test_exiger_etape_ouverte(mission_lancee: Mission) -> None:
    exiger_etape_ouverte(mission_lancee.pk, 2)
    forcer_etapes(mission_lancee, {2: "TERMINEE"})
    with pytest.raises(EtapeCloseError):
        exiger_etape_ouverte(mission_lancee.pk, 2)


def test_verrouiller_mission(mission_lancee: Mission) -> None:
    with transaction.atomic():
        assert verrouiller_mission(mission_lancee).pk == mission_lancee.pk
        assert verrouiller_mission(mission_lancee.pk).pk == mission_lancee.pk
        with pytest.raises(Http404):
            verrouiller_mission(uuid.uuid4())
        _figer(mission_lancee, "ANNULEE")
        with pytest.raises(MissionFigeeError):
            verrouiller_mission(mission_lancee.pk)
