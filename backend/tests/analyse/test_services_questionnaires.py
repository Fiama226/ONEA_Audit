import pytest

from apps.analyse.models import Questionnaire, QuestionQuestionnaire, TypeQuestionnaire
from apps.analyse.services.questionnaires import (
    ajouter_question,
    creer_questionnaire,
    modifier_question,
    modifier_questionnaire,
    retirer_question,
    retirer_questionnaire,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.factories import ProcessusFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_questionnaire_cree_depuis_la_banque(mission_en_analyse: Mission, chef: User) -> None:
    pc = creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    assert pc.questions.count() == 11
    assert pc.titre == "Questionnaire de prise de connaissance"
    assert all(q.mission_id == mission_en_analyse.pk for q in pc.questions.all())
    processus = mission_en_analyse.processus.first()
    qci = creer_questionnaire(
        mission_en_analyse, type=TypeQuestionnaire.QCI, by=chef, processus=processus
    )
    assert qci.questions.count() == 10
    assert qci.titre == f"Questionnaire de contrôle interne — {processus.code}"


def test_sans_banque(mission_en_analyse: Mission, chef: User) -> None:
    q = creer_questionnaire(
        mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef, avec_banque=False
    )
    assert q.questions.count() == 0


def test_questionnaire_doublon_refuse(mission_en_analyse: Mission, chef: User) -> None:
    creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    with pytest.raises(RegleMetierError) as exc:
        creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    assert exc.value.errors["type"] == ["Ce questionnaire existe déjà pour la mission."]


def test_processus_hors_mission_refuse(mission_en_analyse: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_questionnaire(
            mission_en_analyse,
            type=TypeQuestionnaire.QCI,
            by=chef,
            processus=ProcessusFactory(),
        )
    assert exc.value.errors["processus"] == ["Le processus doit être un processus de la mission."]


def test_ecriture_iii_avant_demarrage_refusee(mission_en_analyse: Mission, chef: User) -> None:
    forcer_etapes(mission_en_analyse, {3: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as exc:
        creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    assert exc.value.message == "Commencez l'étape III pour documenter la prise de connaissance."


def test_qci_avant_demarrage_refuse(mission_en_analyse: Mission, chef: User) -> None:
    forcer_etapes(mission_en_analyse, {5: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as exc:
        creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.QCI, by=chef)
    assert exc.value.message == "Commencez l'étape V pour constituer le référentiel d'audit."


def test_qci_ouvert_pendant_vi_en_cours(mission_en_analyse: Mission, chef: User) -> None:
    forcer_etapes(mission_en_analyse, {5: StatutEtape.TERMINEE, 6: StatutEtape.EN_COURS})
    q = creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.QCI, by=chef)
    assert q.questions.count() == 10
    forcer_etapes(mission_en_analyse, {6: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        ajouter_question(q, theme="Autre", libelle="Une question ?", by=chef)


def test_prise_de_connaissance_gelee_apres_iii(mission_en_analyse: Mission, chef: User) -> None:
    q = creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    forcer_etapes(mission_en_analyse, {3: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        modifier_questionnaire(q, by=chef, titre="Autre")


def test_questions_crud(mission_en_analyse: Mission, chef: User) -> None:
    q = creer_questionnaire(
        mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef, avec_banque=False
    )
    q1 = ajouter_question(q, theme="T", libelle="Première ?", by=chef)
    q2 = ajouter_question(q, theme="T", libelle="Seconde ?", by=chef)
    assert (q1.ordre, q2.ordre) == (0, 1)
    assert q1.mission_id == mission_en_analyse.pk
    q1 = modifier_question(q1, by=chef, reponse="Oui, détaillé.", appreciation="OUI")
    assert q1.repondue
    with pytest.raises(RegleMetierError):
        modifier_question(q1, by=chef, appreciation="PEUT-ETRE")
    retirer_question(q2, by=chef)
    assert q.questions.count() == 1
    retirer_questionnaire(q, by=chef)
    assert not Questionnaire.objects.filter(pk=q.pk).exists()
    assert not QuestionQuestionnaire.objects.filter(questionnaire=q).exists()
