from typing import Any

import pytest

from apps.analyse.gardes import MSG_VI_NON_VALIDEE
from apps.analyse.models import EvaluationConception, MotifNonTest, ObjectifAudit
from apps.analyse.services import objectifs
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, RisqueMission, StatutEtape
from apps.users.models import User
from tests.factories import LigneMARCFactory, ObjectifAuditFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

LIBELLE_D9 = "S'assurer de l'efficacité et de l'efficience du contrôle : "


@pytest.fixture
def lignes(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, risque_faible_nouveau: RisqueMission
) -> dict[str, Any]:
    """Deux contrôles clés et un contrôle non clé ; VI validée et VII en cours."""
    cle_1 = LigneMARCFactory(
        mission=mission_en_analyse,
        risque=risque_eleve,
        cle=True,
        evaluation=EvaluationConception.ADEQUATE,
        controle_existant="Double validation des paiements",
        ordre=1,
    )
    cle_2 = LigneMARCFactory(
        mission=mission_en_analyse,
        risque=risque_faible_nouveau,
        cle=True,
        evaluation=EvaluationConception.INSUFFISANTE,
        controle_existant="x" * 400,
        ordre=2,
    )
    autre = LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve, cle=False, ordre=3)
    forcer_etapes(
        mission_en_analyse,
        {5: StatutEtape.TERMINEE, 6: StatutEtape.VALIDEE, 7: StatutEtape.EN_COURS},
    )
    return {"cle_1": cle_1, "cle_2": cle_2, "autre": autre}


def test_initialiser_objectifs_un_par_controle_cle(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    crees = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    assert [o.code for o in crees] == ["OA-01", "OA-02"]
    assert [o.ligne_marc_id for o in crees] == [lignes["cle_1"].pk, lignes["cle_2"].pk]
    assert crees[0].libelle == LIBELLE_D9 + "Double validation des paiements"
    assert crees[1].libelle == LIBELLE_D9 + "x" * 300
    assert all(o.retenu and o.created_by == chef for o in crees)
    assert objectifs.initialiser_objectifs(mission_en_analyse, by=chef) == []
    assert ObjectifAudit.objects.filter(mission=mission_en_analyse).count() == 2


def test_objectifs_refuses_si_vi_non_validee(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    forcer_etapes(mission_en_analyse, {6: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    assert exc.value.message == MSG_VI_NON_VALIDEE
    with pytest.raises(RegleMetierError, match="jalon VI"):
        objectifs.ajouter_objectif(mission_en_analyse, ligne_marc=lignes["cle_1"], by=chef)


def test_ecriture_vii_avant_demarrage_refusee(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    forcer_etapes(mission_en_analyse, {7: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as exc:
        objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    assert exc.value.message == "Commencez l'étape VII pour sélectionner les objectifs d'audit."


def test_ajouter_objectif_ligne_non_cle_refusee(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        objectifs.ajouter_objectif(mission_en_analyse, ligne_marc=lignes["autre"], by=chef)
    assert exc.value.errors["ligne_marc"] == ["Seul un contrôle clé porte un objectif d'audit."]


def test_ajouter_objectif_libelle_et_doublon(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = objectifs.ajouter_objectif(
        mission_en_analyse, ligne_marc=lignes["cle_1"], by=chef, libelle="  Mon objectif "
    )
    assert (o.libelle, o.code, o.retenu) == ("Mon objectif", "OA-01", True)
    with pytest.raises(RegleMetierError) as exc:
        objectifs.ajouter_objectif(mission_en_analyse, ligne_marc=lignes["cle_1"], by=chef)
    assert "ligne_marc" in exc.value.errors


def test_ajouter_objectif_ligne_d_une_autre_mission_refusee(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    etrangere = LigneMARCFactory(cle=True)
    with pytest.raises(RegleMetierError) as exc:
        objectifs.ajouter_objectif(mission_en_analyse, ligne_marc=etrangere, by=chef)
    assert exc.value.errors["ligne_marc"] == ["Cette ligne n'appartient pas à la mission."]


def test_non_retenu_motif_et_justification(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)[0]
    with pytest.raises(RegleMetierError) as exc:
        objectifs.modifier_objectif(o, by=chef, retenu=False)
    assert set(exc.value.errors) == {"motif_non_test", "justification"}
    with pytest.raises(RegleMetierError) as exc:
        objectifs.modifier_objectif(
            o, by=chef, retenu=False, motif_non_test=MotifNonTest.CONCEPTION_ADAPTEE
        )
    assert set(exc.value.errors) == {"justification"}
    with pytest.raises(RegleMetierError) as exc:
        objectifs.modifier_objectif(o, by=chef, retenu=False, justification="Raison")
    assert set(exc.value.errors) == {"motif_non_test"}
    with pytest.raises(RegleMetierError) as exc:
        objectifs.modifier_objectif(
            o, by=chef, retenu=False, motif_non_test="INCONNU", justification="Raison"
        )
    assert "motif_non_test" in exc.value.errors
    o.refresh_from_db()
    assert o.retenu is True
    modifie = objectifs.modifier_objectif(
        o,
        by=chef,
        retenu=False,
        motif_non_test=MotifNonTest.AUTRES_CONTROLES,
        justification="Couvert ailleurs.",
    )
    assert not modifie.retenu
    assert modifie.motif_non_test == MotifNonTest.AUTRES_CONTROLES


def test_retenu_efface_le_motif(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)[0]
    objectifs.modifier_objectif(
        o,
        by=chef,
        retenu=False,
        motif_non_test=MotifNonTest.PERIODE_INCOMPATIBLE,
        justification="Calendrier.",
    )
    o = objectifs.modifier_objectif(o, by=chef, retenu=True)
    o.refresh_from_db()
    assert (o.retenu, o.motif_non_test, o.justification) == (True, "", "")


def test_modifier_libelle_vide_refuse(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)[0]
    with pytest.raises(RegleMetierError) as exc:
        objectifs.modifier_objectif(o, by=chef, libelle="  ")
    assert "libelle" in exc.value.errors
    with pytest.raises(ValueError):
        objectifs.modifier_objectif(o, by=chef, numero=9)


def test_numero_objectif_jamais_reattribue(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    premier, second = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    objectifs.retirer_objectif(second, by=chef)
    assert ObjectifAudit.objects.filter(mission=mission_en_analyse).count() == 1
    nouveau = objectifs.ajouter_objectif(mission_en_analyse, ligne_marc=lignes["cle_2"], by=chef)
    assert (premier.code, nouveau.code) == ("OA-01", "OA-03")


def test_objectifs_geles_apres_vii(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)[0]
    forcer_etapes(mission_en_analyse, {7: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        objectifs.modifier_objectif(o, by=chef, libelle="Autre")
    with pytest.raises(RegleMetierError):
        objectifs.retirer_objectif(o, by=chef)
    with pytest.raises(RegleMetierError):
        objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    o.libelle = "Direct"
    with pytest.raises(EtapeCloseError):
        o.save()
    with pytest.raises(EtapeCloseError):
        ObjectifAudit.objects.filter(pk=o.pk).update(libelle="Direct")


def test_numerotation_apres_objectif_cree_hors_service(
    mission_en_analyse: Mission, lignes: dict[str, Any], chef: User
) -> None:
    o = ObjectifAuditFactory(mission=mission_en_analyse, ligne_marc=lignes["cle_1"], numero=7)
    objectifs.retirer_objectif(o, by=chef)
    suivant = objectifs.initialiser_objectifs(mission_en_analyse, by=chef)
    assert [x.code for x in suivant] == ["OA-08", "OA-09"]
