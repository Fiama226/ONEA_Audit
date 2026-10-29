from collections.abc import Callable

import pytest
from django.db import IntegrityError, transaction

from apps.analyse.banque_questions import QUESTIONS
from apps.analyse.models import (
    AvisAudite,
    EvaluationConception,
    LigneMARC,
    MotifNonTest,
    ObjectifAudit,
    RapportOrientation,
    StatutReferentiel,
    TypeAvis,
    TypeForceFaiblesse,
    TypeQuestionnaire,
    statut_referentiel,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, RisqueMission, StatutEtape
from apps.users.models import User
from tests.factories import (
    AvisAuditeFactory,
    DescriptionProcessusFactory,
    ForceFaiblesseFactory,
    LigneMARCFactory,
    MissionFactory,
    ObjectifAuditFactory,
    ProcessusFactory,
    QuestionFactory,
    QuestionnaireFactory,
    RapportOrientationFactory,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_ffa_liee_retirer_puis_recreer(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, rai: User
) -> None:
    """Cycle D8 : évaluation effacée (FFA retirée) puis ressaisie, sans IntegrityError."""
    ligne = LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve)
    premiere = ForceFaiblesseFactory(mission=mission_en_analyse, ligne_marc=ligne)
    _viole(lambda: ForceFaiblesseFactory(mission=mission_en_analyse, ligne_marc=ligne))
    premiere.soft_delete(rai)
    seconde = ForceFaiblesseFactory(mission=mission_en_analyse, ligne_marc=ligne)
    assert list(ligne.forces_faiblesses.all()) == [seconde]
    # Plusieurs lignes manuelles (sans ligne MARC) restent permises.
    ForceFaiblesseFactory(mission=mission_en_analyse)
    ForceFaiblesseFactory(mission=mission_en_analyse)


def test_categories_objectifs_verifiees_en_base(mission_en_analyse: Mission) -> None:
    DescriptionProcessusFactory(
        mission=mission_en_analyse, categories_objectifs=["OPERATIONNELS", "CONFORMITE"]
    )
    _viole(
        lambda: DescriptionProcessusFactory(
            mission=mission_en_analyse, categories_objectifs=["INCONNU"]
        )
    )


def test_question_de_la_mission_de_son_questionnaire(mission_en_analyse: Mission) -> None:
    questionnaire = QuestionnaireFactory(mission=mission_en_analyse)
    autre = MissionFactory()
    with pytest.raises(RegleMetierError, match="mission de son questionnaire"):
        QuestionFactory(questionnaire=questionnaire, mission=autre)


def test_avis_update_et_bulk_update_refuses(mission_en_analyse: Mission) -> None:
    forcer_etapes(mission_en_analyse, {6: "EN_COURS"})
    avis = AvisAuditeFactory(mission=mission_en_analyse, avis=TypeAvis.REMARQUES, commentaire="a")
    with pytest.raises(RegleMetierError, match="ne peut pas être modifié"):
        AvisAudite.objects.filter(pk=avis.pk).update(commentaire="b")
    avis.commentaire = "c"
    with pytest.raises(RegleMetierError, match="ne peut pas être modifié"):
        AvisAudite.objects.bulk_update([avis], ["commentaire"])
    with pytest.raises(RegleMetierError, match="ne peut pas être modifié"):
        AvisAudite.all_objects.filter(pk=avis.pk).update(avis="ACCORD")
    avis.refresh_from_db()
    assert avis.commentaire == "a"
    # La création en masse reste permise (ajout seul).
    AvisAudite.objects.bulk_create(
        [AvisAudite(mission=avis.mission, auteur=avis.auteur, avis=TypeAvis.ACCORD)]
    )


def _viole(action: Callable[[], object]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        action()


def test_cle_exige_controle_present(
    mission_en_analyse: Mission, risque_eleve: RisqueMission
) -> None:
    _viole(
        lambda: LigneMARCFactory(
            mission=mission_en_analyse,
            risque=risque_eleve,
            cle=True,
            evaluation=EvaluationConception.ABSENTE,
        )
    )
    LigneMARCFactory(
        mission=mission_en_analyse,
        risque=risque_eleve,
        cle=True,
        evaluation=EvaluationConception.INSUFFISANTE,
        controle_existant="Visa.",
    )


@pytest.mark.parametrize(
    "evaluation", [EvaluationConception.ADEQUATE, EvaluationConception.INSUFFISANTE]
)
def test_evaluation_exige_controle_existant(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, evaluation: str
) -> None:
    _viole(
        lambda: LigneMARCFactory(
            mission=mission_en_analyse, risque=risque_eleve, evaluation=evaluation
        )
    )
    LigneMARCFactory(
        mission=mission_en_analyse,
        risque=risque_eleve,
        evaluation=EvaluationConception.ABSENTE,
    )


def test_appreciation_derivee(mission_en_analyse: Mission, risque_eleve: RisqueMission) -> None:
    def ligne(evaluation: str) -> LigneMARC:
        return LigneMARCFactory.build(
            mission=mission_en_analyse, risque=risque_eleve, evaluation=evaluation
        )

    assert ligne("ADEQUATE").appreciation == TypeForceFaiblesse.FORCE
    assert ligne("INSUFFISANTE").appreciation == TypeForceFaiblesse.FAIBLESSE
    assert ligne("ABSENTE").appreciation == TypeForceFaiblesse.FAIBLESSE
    assert ligne("").appreciation is None


def test_objectif_non_retenu_exige_motif_et_justification(
    mission_en_analyse: Mission, risque_eleve: RisqueMission
) -> None:
    ligne = LigneMARCFactory(mission=mission_en_analyse, risque=risque_eleve)
    motif = MotifNonTest.AUTRES_CONTROLES

    def creer(numero: int, **kw: object) -> ObjectifAudit:
        return ObjectifAuditFactory(
            mission=mission_en_analyse, ligne_marc=ligne, numero=numero, **kw
        )

    _viole(lambda: creer(1, retenu=False))
    _viole(lambda: creer(2, retenu=False, motif_non_test=motif))
    _viole(lambda: creer(3, retenu=False, justification="x"))
    _viole(lambda: creer(4, retenu=True, motif_non_test=motif))
    objectif = creer(5, retenu=False, motif_non_test=motif, justification="Couvert ailleurs.")
    assert objectif.code == "OA-05"


def test_couverture_partielle_exige_justification(mission_en_analyse: Mission) -> None:
    _viole(
        lambda: RapportOrientationFactory(mission=mission_en_analyse, couverture_ordre="PARTIELLE")
    )
    RapportOrientationFactory(
        mission=mission_en_analyse,
        couverture_ordre="PARTIELLE",
        justification_couverture="Exclusion justifiée.",
    )
    assert RapportOrientation.objects.count() == 1
    _viole(lambda: RapportOrientationFactory(mission=mission_en_analyse))


def test_avis_ajout_seul(mission_en_analyse: Mission) -> None:
    avis = AvisAuditeFactory(mission=mission_en_analyse)
    avis.commentaire = "modifié"
    with pytest.raises(RegleMetierError, match="ne peut pas être modifié"):
        avis.save()
    _viole(lambda: AvisAuditeFactory(mission=mission_en_analyse, avis=TypeAvis.REMARQUES))
    AvisAuditeFactory(mission=mission_en_analyse, avis=TypeAvis.REMARQUES, commentaire="Voir note.")


@pytest.mark.parametrize(
    ("statut_vi", "attendu"),
    [
        (StatutEtape.A_FAIRE, StatutReferentiel.BROUILLON),
        (StatutEtape.EN_COURS, StatutReferentiel.BROUILLON),
        (StatutEtape.TERMINEE, StatutReferentiel.SOUMIS),
        (StatutEtape.RENVOYEE, StatutReferentiel.RENVOYE),
        (StatutEtape.VALIDEE, StatutReferentiel.VALIDE),
        (StatutEtape.A_REVALIDER, StatutReferentiel.A_REVALIDER),
        (StatutEtape.NON_APPLICABLE, StatutReferentiel.BROUILLON),
    ],
)
def test_statut_referentiel_derive_de_vi(statut_vi: str, attendu: str) -> None:
    assert statut_referentiel(statut_vi) == attendu


def test_questionnaire_unique_par_type_et_processus_null_compris(
    mission_en_analyse: Mission,
) -> None:
    QuestionnaireFactory(mission=mission_en_analyse)
    _viole(lambda: QuestionnaireFactory(mission=mission_en_analyse))
    QuestionnaireFactory(mission=mission_en_analyse, type=TypeQuestionnaire.QCI)
    processus = ProcessusFactory()
    QuestionnaireFactory(mission=mission_en_analyse, processus=processus)
    _viole(lambda: QuestionnaireFactory(mission=mission_en_analyse, processus=processus))


def test_question_repondue_et_appreciation_valide(mission_en_analyse: Mission) -> None:
    questionnaire = QuestionnaireFactory(mission=mission_en_analyse)
    assert not QuestionFactory(questionnaire=questionnaire).repondue
    assert QuestionFactory(questionnaire=questionnaire, reponse="Oui, écrit.").repondue
    assert QuestionFactory(questionnaire=questionnaire, appreciation="NON").repondue
    _viole(lambda: QuestionFactory(questionnaire=questionnaire, appreciation="PEUT-ETRE"))


def test_banque_questions_non_vide_par_type() -> None:
    for type_ in TypeQuestionnaire:
        questions = QUESTIONS[type_]
        assert questions
        assert all(theme and libelle.endswith("?") for theme, libelle in questions)
    assert len(QUESTIONS[TypeQuestionnaire.PRISE_CONNAISSANCE]) == 11
    assert len(QUESTIONS[TypeQuestionnaire.QCI]) == 10
