"""Contrôles de livrables de l'étape III (D13 du plan du lot 5)."""

from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from ..models import DescriptionProcessus, Questionnaire, QuestionQuestionnaire, TypeQuestionnaire


def _descriptions(etape: EtapeMission) -> str | None:
    complets = {
        d.processus_id
        for d in DescriptionProcessus.objects.filter(mission_id=etape.mission_id)
        if d.description.strip() and d.objectifs.strip()
    }
    manquants = [
        p.code for p in etape.mission.processus.order_by("ordre", "code") if p.pk not in complets
    ]
    if manquants:
        return f"Description manquante pour les processus : {', '.join(manquants)}."
    return None


def _questionnaire_cree(etape: EtapeMission) -> str | None:
    existe = Questionnaire.objects.filter(
        mission_id=etape.mission_id, type=TypeQuestionnaire.PRISE_CONNAISSANCE
    ).exists()
    return None if existe else "Le questionnaire de prise de connaissance n'est pas créé."


def _questions_repondues(etape: EtapeMission) -> str | None:
    questions = QuestionQuestionnaire.objects.filter(
        mission_id=etape.mission_id, questionnaire__type=TypeQuestionnaire.PRISE_CONNAISSANCE
    )
    sans_reponse = sum(1 for q in questions if not q.repondue)
    if sans_reponse:
        return (
            "Questions sans réponse dans le questionnaire de prise de connaissance : "
            f"{sans_reponse}."
        )
    return None


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    3: [_descriptions, _questionnaire_cree, _questions_repondues]
}
