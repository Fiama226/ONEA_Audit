import django_filters
from django_filters import rest_framework as rf_filters

from .models import (
    DescriptionProcessus,
    EvaluationConception,
    ForceFaiblesse,
    GrilleSeparation,
    LigneMARC,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    TypeForceFaiblesse,
    TypeQuestionnaire,
)

_MISSION_AIDE = "Obligatoire pour la liste."


class QuestionnaireFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    type = django_filters.ChoiceFilter(choices=TypeQuestionnaire.choices)
    processus = django_filters.UUIDFilter(field_name="processus_id")

    class Meta:
        model = Questionnaire
        fields: list[str] = []


class QuestionFilter(django_filters.FilterSet):
    questionnaire = django_filters.UUIDFilter(
        field_name="questionnaire_id", help_text=_MISSION_AIDE
    )

    class Meta:
        model = QuestionQuestionnaire
        fields: list[str] = []


class DescriptionFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    processus = django_filters.UUIDFilter(field_name="processus_id")

    class Meta:
        model = DescriptionProcessus
        fields: list[str] = []


class GrilleFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    processus = django_filters.UUIDFilter(field_name="processus_id")

    class Meta:
        model = GrilleSeparation
        fields: list[str] = []


class LigneMARCFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    risque = django_filters.UUIDFilter(field_name="risque_id")
    evaluation = django_filters.ChoiceFilter(choices=EvaluationConception.choices)
    cle = rf_filters.BooleanFilter()
    processus = django_filters.UUIDFilter(field_name="risque__processus_id")

    class Meta:
        model = LigneMARC
        fields: list[str] = []


class ForceFaiblesseFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    type = django_filters.ChoiceFilter(choices=TypeForceFaiblesse.choices)

    class Meta:
        model = ForceFaiblesse
        fields: list[str] = []


class ObjectifFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    retenu = rf_filters.BooleanFilter()

    class Meta:
        model = ObjectifAudit
        fields: list[str] = []
