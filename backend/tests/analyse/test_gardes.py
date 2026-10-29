from collections.abc import Callable
from typing import Any

import pytest

from apps.analyse.gardes import (
    exiger_actives,
    exiger_vi_validee,
    statuts_etapes,
)
from apps.analyse.models import (
    AvisAudite,
    DescriptionProcessus,
    ForceFaiblesse,
    GrilleSeparation,
    LigneMARC,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    RapportOrientation,
    TypeQuestionnaire,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import Mission, RisqueMission
from tests.factories import (
    AvisAuditeFactory,
    DescriptionProcessusFactory,
    ForceFaiblesseFactory,
    GrilleSeparationFactory,
    LigneMARCFactory,
    ObjectifAuditFactory,
    QuestionFactory,
    QuestionnaireFactory,
    RapportOrientationFactory,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("v", "vi", "refuse"),
    [
        ("EN_COURS", "A_FAIRE", None),
        ("TERMINEE", "EN_COURS", None),
        ("TERMINEE", "RENVOYEE", None),
        ("TERMINEE", "A_FAIRE", "V"),
        ("TERMINEE", "TERMINEE", "VI"),
        ("EN_COURS", "VALIDEE", "VI"),
        ("TERMINEE", "A_REVALIDER", "VI"),
    ],
)
def test_gel_marc_selon_v_et_vi(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, v: str, vi: str, refuse: str | None
) -> None:
    ligne = LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve)
    forcer_etapes(mission_en_analyse, {5: v, 6: vi})
    ligne.refresh_from_db()
    ligne.commentaire = "x"
    if refuse is None:
        ligne.save()
    else:
        with pytest.raises(EtapeCloseError, match=f"L'étape {refuse} "):
            ligne.save()
        with pytest.raises(EtapeCloseError):
            LigneMARC.objects.filter(pk=ligne.pk).update(commentaire="y")


def test_gel_ffa_et_qci_suivent_la_fenetre_marc(
    mission_en_analyse: Mission, risque_eleve: RisqueMission
) -> None:
    ff = ForceFaiblesseFactory(mission=mission_en_analyse)
    qci = QuestionnaireFactory(mission=mission_en_analyse, type=TypeQuestionnaire.QCI)
    question = QuestionFactory(questionnaire=qci)
    forcer_etapes(mission_en_analyse, {5: "TERMINEE", 6: "TERMINEE"})
    for objet in (ff, qci, question):
        objet.refresh_from_db()
        with pytest.raises(EtapeCloseError):
            objet.save()


def test_gel_prise_de_connaissance_apres_iii(mission_en_analyse: Mission) -> None:
    questionnaire = QuestionnaireFactory(mission=mission_en_analyse)
    question = QuestionFactory(questionnaire=questionnaire)
    description = DescriptionProcessusFactory(mission=mission_en_analyse)
    grille = GrilleSeparationFactory(mission=mission_en_analyse)
    forcer_etapes(mission_en_analyse, {3: "TERMINEE"})
    for objet in (questionnaire, question, description, grille):
        objet.refresh_from_db()
        with pytest.raises(EtapeCloseError, match="L'étape III "):
            objet.save()
    # Le QCI n'est pas concerné par la fin de III.
    qci = QuestionnaireFactory(mission=mission_en_analyse, type=TypeQuestionnaire.QCI)
    qci.titre = "QCI"
    qci.save()


def test_gel_objectifs_apres_vii(mission_en_analyse: Mission, risque_eleve: RisqueMission) -> None:
    ligne = LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve)
    objectif = ObjectifAuditFactory(mission=mission_en_analyse, ligne_marc=ligne)
    rapport = RapportOrientationFactory(mission=mission_en_analyse)
    forcer_etapes(mission_en_analyse, {7: "TERMINEE"})
    for objet in (objectif, rapport):
        objet.refresh_from_db()
        with pytest.raises(EtapeCloseError, match="L'étape VII "):
            objet.save()
    with pytest.raises(EtapeCloseError):
        ObjectifAudit.objects.filter(pk=objectif.pk).update(libelle="z")


def test_gel_avis_apres_validation_de_vi(mission_en_analyse: Mission) -> None:
    forcer_etapes(mission_en_analyse, {6: "TERMINEE"})
    AvisAuditeFactory(mission=mission_en_analyse)
    forcer_etapes(mission_en_analyse, {6: "VALIDEE"})
    with pytest.raises(EtapeCloseError, match="L'étape VI "):
        AvisAuditeFactory(mission=mission_en_analyse)
    forcer_etapes(mission_en_analyse, {6: "A_REVALIDER"})
    with pytest.raises(EtapeCloseError):
        AvisAuditeFactory(mission=mission_en_analyse)


def _cree(modele: type, mission: Mission, risque: RisqueMission) -> Any:
    fabriques: dict[type, Callable[[], Any]] = {
        Questionnaire: lambda: QuestionnaireFactory(mission=mission),
        QuestionQuestionnaire: lambda: QuestionFactory(
            questionnaire=QuestionnaireFactory(mission=mission)
        ),
        DescriptionProcessus: lambda: DescriptionProcessusFactory(mission=mission),
        GrilleSeparation: lambda: GrilleSeparationFactory(mission=mission),
        LigneMARC: lambda: LigneMARCFactory(mission=mission, risque=risque),
        ForceFaiblesse: lambda: ForceFaiblesseFactory(mission=mission),
        AvisAudite: lambda: AvisAuditeFactory(mission=mission),
        ObjectifAudit: lambda: ObjectifAuditFactory(
            mission=mission, ligne_marc=LigneMARCFactory(mission=mission, risque=risque)
        ),
        RapportOrientation: lambda: RapportOrientationFactory(mission=mission),
    }
    return fabriques[modele]()


MODELES = [
    Questionnaire,
    QuestionQuestionnaire,
    DescriptionProcessus,
    GrilleSeparation,
    LigneMARC,
    ForceFaiblesse,
    AvisAudite,
    ObjectifAudit,
    RapportOrientation,
]


@pytest.mark.parametrize("modele", MODELES)
def test_mission_suspendue_gele_tout_objet_analyse(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, modele: type
) -> None:
    objet = _cree(modele, mission_en_analyse, risque_eleve)
    Mission.objects.filter(pk=mission_en_analyse.pk).update(
        statut="SUSPENDUE", statut_avant_suspension="EN_PLANIFICATION"
    )
    objet.refresh_from_db()
    with pytest.raises(MissionFigeeError):
        objet.save()
    with pytest.raises(MissionFigeeError):
        modele.objects.filter(pk=objet.pk).update(updated_by=None)


def test_statuts_etapes_une_requete(
    mission_en_analyse: Mission, django_assert_num_queries: Any
) -> None:
    with django_assert_num_queries(1):
        assert statuts_etapes(mission_en_analyse.pk, [3, 5, 6]) == {
            3: "EN_COURS",
            5: "EN_COURS",
            6: "A_FAIRE",
        }


def test_exiger_actives(mission_en_analyse: Mission) -> None:
    exiger_actives(mission_en_analyse.pk, une_de=[5, 6], message="non")
    with pytest.raises(RegleMetierError, match="^non$"):
        exiger_actives(mission_en_analyse.pk, une_de=[6, 7], message="non")


def test_exiger_vi_validee(mission_en_analyse: Mission) -> None:
    with pytest.raises(RegleMetierError, match="jalon VI"):
        exiger_vi_validee(mission_en_analyse.pk)
    forcer_etapes(mission_en_analyse, {6: "VALIDEE"})
    exiger_vi_validee(mission_en_analyse.pk)
