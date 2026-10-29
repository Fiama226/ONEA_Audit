import pytest

from apps.analyse.models import QuestionQuestionnaire, TypeQuestionnaire
from apps.analyse.services.descriptions import enregistrer_description
from apps.analyse.services.questionnaires import creer_questionnaire
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.users.models import User

pytestmark = pytest.mark.django_db


def _livrables(exc: pytest.ExceptionInfo[RegleMetierError]) -> list[str]:
    return exc.value.errors["livrables"]


def test_terminer_iii_livrables(mission_en_analyse: Mission, chef: User) -> None:
    etape = EtapeMission.objects.get(mission=mission_en_analyse, numero=3)
    code = mission_en_analyse.processus.first().code
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape, by=chef)
    assert _livrables(exc) == [
        f"Description manquante pour les processus : {code}.",
        "Le questionnaire de prise de connaissance n'est pas créé.",
    ]

    enregistrer_description(
        mission_en_analyse,
        processus=mission_en_analyse.processus.first(),
        by=chef,
        description="Achats.",
        objectifs="Livrer.",
    )
    q = creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape, by=chef)
    assert _livrables(exc) == [
        "Questions sans réponse dans le questionnaire de prise de connaissance : 11."
    ]

    for question in QuestionQuestionnaire.objects.filter(questionnaire=q).order_by("ordre")[:10]:
        question.reponse = "Réponse."
        question.save()
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape, by=chef)
    assert _livrables(exc) == [
        "Questions sans réponse dans le questionnaire de prise de connaissance : 1."
    ]

    QuestionQuestionnaire.objects.filter(questionnaire=q, reponse="").update(appreciation="NON")
    etape = terminer_etape(etape, by=chef)
    assert etape.statut == StatutEtape.TERMINEE


def test_description_incomplete_comptee_manquante(mission_en_analyse: Mission, chef: User) -> None:
    p = mission_en_analyse.processus.first()
    enregistrer_description(mission_en_analyse, processus=p, by=chef, description="Seule.")
    etape = EtapeMission.objects.get(mission=mission_en_analyse, numero=3)
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape, by=chef)
    assert f"Description manquante pour les processus : {p.code}." in _livrables(exc)
