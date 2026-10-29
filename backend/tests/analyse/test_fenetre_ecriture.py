import pytest

from apps.analyse.models import ForceFaiblesse, LigneMARC
from apps.analyse.services import forces_faiblesses as ffa
from apps.analyse.services import marc
from apps.analyse.services.referentiel import deposer_avis, referentiel_valide
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, RisqueMission
from apps.missions.services.etapes import valider_etape
from apps.users.models import User
from tests.factories import ProcessusFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "statuts", [{5: "A_FAIRE", 6: "A_FAIRE"}, {5: "NON_APPLICABLE", 6: "A_FAIRE"}]
)
def test_ecriture_marc_refusee_avant_v(
    mission_en_analyse: Mission,
    risque_eleve: RisqueMission,
    chef: User,
    statuts: dict[int, str],
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    forcer_etapes(mission_en_analyse, statuts)
    msg = "Commencez l'étape V pour constituer le référentiel d'audit."
    appels = [
        lambda: marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef),
        lambda: marc.initialiser_marc(mission_en_analyse, by=chef),
        lambda: marc.modifier_ligne_marc(ligne, by=chef, commentaire="x"),
        lambda: marc.retirer_ligne_marc(ligne, by=chef),
        lambda: ffa.ajouter_force_faiblesse(mission_en_analyse, type="FORCE", libelle="x", by=chef),
    ]
    for appel in appels:
        with pytest.raises(RegleMetierError) as e:
            appel()
        assert e.value.message == msg


def test_ecriture_possible_quand_vi_renvoyee(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    forcer_etapes(mission_en_analyse, {5: "TERMINEE", 6: "RENVOYEE"})
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)


def test_cycle_d8_ancienne_ligne_reste_supprimee(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="ADEQUATE",
    )
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="")
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="ADEQUATE")
    toutes = ForceFaiblesse.all_objects.filter(ligne_marc=ligne)
    assert toutes.count() == 2
    assert toutes.filter(deleted_at__isnull=True).count() == 1


def test_ffa_manuelle_processus_hors_mission_refuse(
    mission_en_analyse: Mission, chef: User
) -> None:
    with pytest.raises(RegleMetierError) as e:
        ffa.ajouter_force_faiblesse(
            mission_en_analyse, type="FORCE", libelle="x", by=chef, processus=ProcessusFactory()
        )
    assert "processus" in e.value.errors


def test_libelle_absence_sans_objectif(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse, risque=risque_eleve, by=chef, evaluation="ABSENTE"
    )
    LigneMARC.objects.filter(pk=ligne.pk).update(objectif_controle="")
    ligne.refresh_from_db()
    assert ffa.libelle_automatique(ligne) == "Absence de contrôle"


def test_avis_refuse_message_d4(mission_en_analyse: Mission, audite_affecte: User) -> None:
    with pytest.raises(RegleMetierError, match="n'est pas soumis à l'avis des audités"):
        deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=audite_affecte)


def test_echec_du_snapshot_laisse_vi_terminee(
    mission_en_analyse: Mission,
    risque_eleve: RisqueMission,
    chef: User,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    forcer_etapes(mission_en_analyse, {5: "TERMINEE", 6: "TERMINEE"})

    def echec(*args: object, **kwargs: object) -> None:
        raise RuntimeError("snapshot")

    monkeypatch.setattr("apps.analyse.recepteurs.figer_referentiel", echec)
    with pytest.raises(RuntimeError):
        valider_etape(mission_en_analyse.etapes.get(numero=6), by=rai)
    assert mission_en_analyse.etapes.get(numero=6).statut == "TERMINEE"
    assert referentiel_valide(mission_en_analyse) is None
