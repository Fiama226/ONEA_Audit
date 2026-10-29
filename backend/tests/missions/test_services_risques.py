import pytest
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, RisqueMission, StatutEtape, StatutMission
from apps.missions.services.risques import (
    GARDES_RETRAIT,
    ajouter_risque_mission,
    enregistrer_garde_retrait,
    matrice_mission,
    modifier_risque_mission,
    retirer_risque_mission,
    risques_proposes,
)
from apps.referentiel.models import CartographieVersion, Processus, Risque, StatutCartographie
from apps.users.models import Role, User
from tests.factories import (
    CartographieVersionFactory,
    MissionFactory,
    ProcessusFactory,
    RisqueFactory,
    RisqueMissionFactory,
    make_user,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.fixture
def processus(mission_lancee: Mission) -> Processus:
    p = ProcessusFactory()
    mission_lancee.processus.add(p)
    return p


@pytest.fixture
def risques(mission_lancee: Mission, processus: Processus) -> tuple[Risque, Risque]:
    """(risque d'un processus de la mission, risque d'un autre processus), cartographie validée."""
    version = CartographieVersionFactory()
    risque = RisqueFactory(version=version, processus=processus)
    hors = RisqueFactory(version=version)
    CartographieVersion._base_manager.filter(pk=version.pk).update(
        statut=StatutCartographie.VALIDEE,
        validee_le=timezone.now(),
        validee_par=make_user(Role.RAI),
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(cartographie=version)
    mission_lancee.refresh_from_db()
    return risque, hors


@pytest.fixture
def risque(risques: tuple[Risque, Risque]) -> Risque:
    return risques[0]


@pytest.fixture
def iv_en_cours(mission_lancee: Mission) -> None:
    forcer_etapes(mission_lancee, {4: StatutEtape.EN_COURS})


def test_risque_avant_etape_IV_refuse(mission_lancee: Mission, rai: User, risque: Risque) -> None:
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    assert exc.value.message == "Commencez l'étape IV pour sélectionner les risques."


@pytest.mark.usefixtures("iv_en_cours")
def test_risque_hors_cartographie_ou_processus_refuse(
    mission_lancee: Mission, rai: User, risque: Risque, risques: tuple[Risque, Risque]
) -> None:
    autre = RisqueFactory()  # autre cartographie
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(mission_lancee, by=rai, risque_source=autre)
    assert exc.value.errors["risque_source"] == [
        "Ce risque n'appartient pas à la cartographie de la mission."
    ]
    hors = risques[1]  # processus hors mission
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(mission_lancee, by=rai, risque_source=hors)
    assert exc.value.errors["processus"] == ["Le processus doit être un processus de la mission."]
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(
            mission_lancee, by=rai, processus=hors.processus, libelle="X", probabilite=1, impact=1
        )
    assert "processus" in exc.value.errors


@pytest.mark.usefixtures("iv_en_cours")
def test_risque_deja_selectionne(mission_lancee: Mission, rai: User, risque: Risque) -> None:
    ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    assert exc.value.errors["risque_source"] == ["Ce risque est déjà sélectionné."]


@pytest.mark.usefixtures("iv_en_cours")
def test_risque_nouveau_et_snapshot(
    mission_lancee: Mission, rai: User, risque: Risque, processus: Processus
) -> None:
    copie = ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    assert (copie.code_source, copie.libelle, copie.probabilite, copie.impact) == (
        risque.code,
        risque.libelle,
        3,
        3,
    )
    Risque._base_manager.filter(pk=risque.pk).update(libelle="Modifié", probabilite=5, impact=5)
    copie.refresh_from_db()
    assert (copie.libelle, copie.probabilite, copie.impact) == (risque.libelle, 3, 3)
    assert not copie.nouveau
    copie = modifier_risque_mission(copie, by=rai, probabilite=4, impact=2, commentaire="Réévalué")
    assert (copie.probabilite, copie.impact, copie.score, copie.niveau) == (4, 2, 8, "MOYEN")
    with pytest.raises(RegleMetierError) as exc:
        modifier_risque_mission(copie, by=rai, libelle="Autre")
    assert "libelle" in exc.value.errors

    nouveau = ajouter_risque_mission(
        mission_lancee,
        by=rai,
        processus=processus,
        libelle="Risque inédit",
        probabilite=2,
        impact=2,
    )
    assert nouveau.nouveau
    assert nouveau.code_source == ""
    nouveau = modifier_risque_mission(nouveau, by=rai, libelle="Risque inédit bis")
    assert nouveau.libelle == "Risque inédit bis"
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(mission_lancee, by=rai, processus=processus, libelle="Sans note")
    assert "probabilite" in exc.value.errors
    with pytest.raises(RegleMetierError) as exc:
        ajouter_risque_mission(
            mission_lancee, by=rai, processus=processus, libelle="Hors", probabilite=6, impact=1
        )
    assert "probabilite" in exc.value.errors


@pytest.mark.usefixtures("iv_en_cours")
def test_risques_figes_apres_IV(mission_lancee: Mission, rai: User, risque: Risque) -> None:
    copie = ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    forcer_etapes(mission_lancee, {4: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        modifier_risque_mission(copie, by=rai, impact=1)
    with pytest.raises(EtapeCloseError):
        retirer_risque_mission(copie, by=rai)
    with pytest.raises(EtapeCloseError):
        ajouter_risque_mission(mission_lancee, by=rai, risque_source=RisqueFactory())


@pytest.mark.usefixtures("iv_en_cours")
def test_retirer_risque(mission_lancee: Mission, rai: User, risque: Risque) -> None:
    copie = ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    retirer_risque_mission(copie, by=rai)
    assert not RisqueMission.objects.filter(mission=mission_lancee).exists()
    assert RisqueMission.all_objects.filter(pk=copie.pk, deleted_at__isnull=False).exists()


@pytest.mark.usefixtures("iv_en_cours")
def test_garde_retrait_appelee(mission_lancee: Mission, rai: User, risque: Risque) -> None:
    def garde(rm: RisqueMission) -> None:
        raise RegleMetierError("Risque utilisé par l'analyse.")

    copie = ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    enregistrer_garde_retrait(garde)
    enregistrer_garde_retrait(garde)
    assert GARDES_RETRAIT.count(garde) == 1
    try:
        with pytest.raises(RegleMetierError):
            retirer_risque_mission(copie, by=rai)
    finally:
        GARDES_RETRAIT.remove(garde)
    assert RisqueMission.objects.filter(pk=copie.pk).exists()


@pytest.mark.usefixtures("iv_en_cours")
def test_matrice_mission(
    mission_lancee: Mission, rai: User, risque: Risque, processus: Processus
) -> None:
    ajouter_risque_mission(mission_lancee, by=rai, risque_source=risque)
    long = "L" * 60
    ajouter_risque_mission(
        mission_lancee, by=rai, processus=processus, libelle=long, probabilite=3, impact=3
    )
    cellules = matrice_mission(mission_lancee)
    assert len(cellules) == 25
    cellule = next(c for c in cellules if (c.probabilite, c.impact) == (3, 3))
    assert cellule.nombre == 2
    assert cellule.codes == [risque.code, f"Nouveau : {'L' * 40}"]


def test_risques_proposes_exclut_annulees(db: None) -> None:
    active = MissionFactory(statut=StatutMission.EN_PLANIFICATION, reference="DAI/2026/M01")
    annulee = MissionFactory(statut=StatutMission.EN_PLANIFICATION, reference="DAI/2026/M02")
    nouveau = RisqueMissionFactory(mission=active)
    RisqueMissionFactory(mission=annulee)
    Mission.objects.filter(pk=annulee.pk).update(statut=StatutMission.ANNULEE)
    RisqueMissionFactory(mission=active, risque_source=RisqueFactory(), code_source="1-X-R1")
    assert list(risques_proposes()) == [nouveau]
