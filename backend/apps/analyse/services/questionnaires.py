"""Questionnaires (prise de connaissance, QCI) et leurs questions (D5)."""

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.referentiel.models import Processus
from apps.users.models import User

from ..banque_questions import QUESTIONS
from ..models import Questionnaire, QuestionQuestionnaire, TypeQuestionnaire
from ._fenetres import ouvrir_pour_type

_MODIFIABLES_Q = {"titre"}
_MODIFIABLES_QUESTION = {"theme", "libelle", "reponse", "appreciation", "ordre"}


def _prochain_ordre(questionnaire: Questionnaire) -> int:
    maxi = QuestionQuestionnaire.objects.filter(questionnaire=questionnaire).aggregate(
        m=Max("ordre")
    )["m"]
    return 0 if maxi is None else int(maxi) + 1


@transaction.atomic
def creer_questionnaire(
    mission: Mission,
    *,
    type: str,  # noqa: A002
    by: User,
    processus: Processus | None = None,
    titre: str = "",
    avec_banque: bool = True,
) -> Questionnaire:
    if type not in TypeQuestionnaire.values:
        message = "Type de questionnaire inconnu."
        raise refuser(message, type=message)
    mission = ouvrir_pour_type(mission, type)
    if processus is not None and not mission.processus.filter(pk=processus.pk).exists():
        message = "Le processus doit être un processus de la mission."
        raise refuser(message, processus=message)
    if Questionnaire.objects.filter(mission=mission, type=type, processus=processus).exists():
        message = "Ce questionnaire existe déjà pour la mission."
        raise refuser(message, type=message)
    if not titre.strip():
        titre = str(TypeQuestionnaire(type).label)
        if processus is not None:
            titre = f"{titre} — {processus.code}"
    questionnaire = Questionnaire(mission=mission, type=type, processus=processus, titre=titre)
    enregistrer(questionnaire, by=by, creation=True)
    if avec_banque:
        for ordre, (theme, libelle) in enumerate(QUESTIONS[TypeQuestionnaire(type)]):
            question = QuestionQuestionnaire(
                mission=mission,
                questionnaire=questionnaire,
                theme=theme,
                libelle=libelle,
                ordre=ordre,
            )
            enregistrer(question, by=by, creation=True)
    return questionnaire


@transaction.atomic
def modifier_questionnaire(
    questionnaire: Questionnaire, *, by: User, **changes: Any
) -> Questionnaire:
    ouvrir_pour_type(questionnaire.mission, questionnaire.type)
    questionnaire = relire(questionnaire)
    appliquer(questionnaire, changes, _MODIFIABLES_Q)
    enregistrer(questionnaire, by=by)
    return questionnaire


@transaction.atomic
def retirer_questionnaire(questionnaire: Questionnaire, *, by: User) -> None:
    ouvrir_pour_type(questionnaire.mission, questionnaire.type)
    questionnaire = relire(questionnaire)
    for question in QuestionQuestionnaire.objects.filter(questionnaire=questionnaire):
        question.soft_delete(by)
    questionnaire.soft_delete(by)


@transaction.atomic
def ajouter_question(
    questionnaire: Questionnaire,
    *,
    theme: str,
    libelle: str,
    by: User,
    ordre: int | None = None,
) -> QuestionQuestionnaire:
    mission = ouvrir_pour_type(questionnaire.mission, questionnaire.type)
    questionnaire = relire(questionnaire)
    question = QuestionQuestionnaire(
        mission=mission,
        questionnaire=questionnaire,
        theme=theme,
        libelle=libelle,
        ordre=_prochain_ordre(questionnaire) if ordre is None else ordre,
    )
    enregistrer(question, by=by, creation=True)
    return question


@transaction.atomic
def modifier_question(
    question: QuestionQuestionnaire, *, by: User, **changes: Any
) -> QuestionQuestionnaire:
    ouvrir_pour_type(question.mission, question.questionnaire.type)
    question = relire(question)
    appliquer(question, changes, _MODIFIABLES_QUESTION)
    enregistrer(question, by=by)
    return question


@transaction.atomic
def retirer_question(question: QuestionQuestionnaire, *, by: User) -> None:
    ouvrir_pour_type(question.mission, question.questionnaire.type)
    relire(question).soft_delete(by)
